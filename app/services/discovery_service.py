"""
Discovery Service - Enhanced with Skills-Based Discovery

Implements three-pronged discovery:
1. Knowledge Base Search (Priority) - Exact match detection
2. Skills Navigation - Keyword-based data group matching
3. Value Index Search - Entity-to-table mapping (fallback merge)
"""

from typing import List, Dict, Optional, Set, Any
from collections import defaultdict
import logging

from app.models.schemas import (
    DiscoveryRequest, DiscoveryResponse, DiscoveryContext,
    TableSchema, RankedTable, ThresholdDecision, SelectionPrompt,
    SkillsDiscoveryResult, ThreeProngedResult
)
from app.services.vector_store import get_vector_store
from app.services.skills_service import get_skills_service
from app.services.llm_service import LLMServiceBase
from app.services.relationship_graph import get_relationship_graph

# Configuration Constants
KNOWLEDGE_BASE_EXACT_MATCH_THRESHOLD = 0.1  # L2 distance threshold for exact match
SKILLS_HIGH_SCORE_THRESHOLD = 15  # Minimum score to consider skills match as high-confidence
USER_SELECTION_TOP_K = 20  # Number of top candidates to present to user

# Relationship tracing constants
MAX_RELATED_TABLES_PER_HIT = 3  # Cap related tables added per value index hit
RELATIONSHIP_TRACE_HOPS = 2      # Max FK hops to traverse


def perform_discovery(request: DiscoveryRequest) -> DiscoveryResponse:
    """
    Legacy discovery function - kept for backward compatibility
    Uses Milvus schema_index (deprecated)
    """
    vector_store = get_vector_store()
    # Search for relevant tables
    schemas = vector_store.search_schemas(request.query, request.top_k)

    # Search for similar queries (specifically SQL examples)
    raw_few_shots = vector_store.search_fewshots(request.query, top_k=3, knowledge_type="sql_query")

    # Transform fewshot results to a simpler format
    similar_queries = []
    for fs in raw_few_shots:
        if isinstance(fs, dict):
            entity = fs.get('entity', {})
            similar_query = {
                "question": entity.get("question", ""),
                "sql": entity.get("sql_query", "")
            }
            similar_queries.append(similar_query)

    context = DiscoveryContext(
        relevant_tables=schemas,
        similar_queries=similar_queries
    )

    return DiscoveryResponse(
        query=request.query,
        reasoning=f"Identified {len(schemas)} relevant tables and {len(similar_queries)} similar queries.",
        context=context
    )


def perform_skills_based_discovery(query: str, llm_service: Optional[LLMServiceBase] = None) -> SkillsDiscoveryResult:
    """
    Stage 2A: Skills Navigation (Primary Discovery)
    
    Args:
        query: User's natural language query
        llm_service: LLM service for validation (optional)
        
    Returns:
        SkillsDiscoveryResult with matched data groups and candidate tables
    """
    skills_service = get_skills_service()
    
    # Keyword-based search across all data groups
    result = skills_service.search_data_groups_by_keywords(query)
    
    # Optional: LLM validation of matched groups
    if llm_service and result.matched_groups:
        validated_groups = validate_groups_with_llm(
            query, 
            result.matched_groups, 
            llm_service
        )
        result.matched_groups = validated_groups
    
    return result


def perform_value_index_search(query: str, top_k: int = 5) -> List[RankedTable]:
    """
    Stage 2B: Value Index Search (Entity Mapping) with Relationship Tracing
    
    After finding direct value matches, traces FK relationships to discover
    related data/fact tables (up to RELATIONSHIP_TRACE_HOPS hops, capped at
    MAX_RELATED_TABLES_PER_HIT per direct hit).
    
    Args:
        query: User's natural language query
        top_k: Number of top results to return from value index
        
    Returns:
        List of RankedTable objects (direct matches + traced related tables)
    """
    vector_store = get_vector_store()
    
    # Phase 1: Direct value index search
    value_results = vector_store.search_values(query, top_k=top_k)
    
    ranked_tables = []
    seen_keys = set()  # (schema_lower, table_lower) for deduplication
    
    for result in value_results:
        if isinstance(result, dict):
            entity = result.get('entity', {})
            schema_name = entity.get('schema_name', 'dbo')
            table_name = entity.get('table_name', '')
            
            if not table_name:
                continue
                
            key = (schema_name.lower(), table_name.lower())
            if key in seen_keys:
                continue
            seen_keys.add(key)
            
            ranked_tables.append(RankedTable(
                schema_name=schema_name,
                table_name=table_name,
                score=8,  # Value index score
                matched_by=['value_index'],
                data_source=None,
                data_group=None
            ))
    
    if not ranked_tables:
        return ranked_tables
    
    # Phase 2: Relationship tracing for each direct hit
    try:
        graph = get_relationship_graph()
        
        for direct_hit in list(ranked_tables):  # iterate over copy
            related = graph.trace_related_tables(
                direct_hit.schema_name,
                direct_hit.table_name,
                max_hops=RELATIONSHIP_TRACE_HOPS,
                max_tables=MAX_RELATED_TABLES_PER_HIT
            )
            
            for rel_schema in related:
                rel_key = (rel_schema.schema_name.lower(), rel_schema.table_name.lower())
                if rel_key in seen_keys:
                    continue
                seen_keys.add(rel_key)
                
                ranked_tables.append(RankedTable(
                    schema_name=rel_schema.schema_name,
                    table_name=rel_schema.table_name,
                    score=8,  # Same weight as direct value match
                    matched_by=['relationship_traced'],
                    data_source=None,
                    data_group=None
                ))
                
                logging.info(
                    f"[Value Index] Relationship traced: "
                    f"{direct_hit.schema_name}.{direct_hit.table_name} -> "
                    f"{rel_schema.schema_name}.{rel_schema.table_name}"
                )
    except Exception as e:
        logging.warning(f"[Value Index] Relationship tracing failed (non-fatal): {e}")
    
    return ranked_tables


def perform_knowledge_base_search(query: str, llm_service: Optional[LLMServiceBase] = None, top_k: int = 3) -> List[RankedTable]:
    """
    Stage 2C: Knowledge Base Search (Query Pattern Matching)
    
    Args:
        query: User's natural language query
        llm_service: LLM service for table extraction
        top_k: Number of similar queries to find
        
    Returns:
        List of RankedTable objects extracted from similar queries
    """
    vector_store = get_vector_store()
    
    # Search knowledge base for similar queries
    raw_few_shots = vector_store.search_fewshots(query, top_k=top_k, knowledge_type="sql_query")
    
    ranked_tables = []
    
    # Extract tables from SQL queries
    for fs in raw_few_shots:
        if isinstance(fs, dict):
            entity = fs.get('entity', {})
            sql_query = entity.get('sql_query', '')
            
            if sql_query and llm_service:
                # Use LLM to extract table names from SQL
                tables = llm_service.extract_tables_from_sql(sql_query)
                
                for table_name in tables:
                    # Parse schema.table format
                    if '.' in table_name:
                        parts = table_name.replace('[', '').replace(']', '').split('.')
                        schema_name = parts[0] if len(parts) > 1 else 'dbo'
                        table = parts[1] if len(parts) > 1 else parts[0]
                    else:
                        schema_name = 'dbo'
                        table = table_name.replace('[', '').replace(']', '')
                    
                    ranked_tables.append(RankedTable(
                        schema_name=schema_name,
                        table_name=table,
                        score=5,  # Knowledge base score
                        matched_by=['knowledge_base'],
                        data_source=None,
                        data_group=None
                    ))
    
    return ranked_tables


def extract_tables_from_match(matched_query: Dict[str, Any], llm_service: Optional[LLMServiceBase] = None) -> List[RankedTable]:
    """
    Extract table names from a matched SQL query and return as RankedTable objects
    
    Args:
        matched_query: Dict with 'sql_query' key containing the SQL
        llm_service: LLM service for table extraction
        
    Returns:
        List of RankedTable objects extracted from the SQL
    """
    ranked_tables = []
    sql_query = matched_query.get('sql_query', '')
    
    if not sql_query or not llm_service:
        return ranked_tables
    
    # Use LLM to extract table names from SQL
    tables = llm_service.extract_tables_from_sql([sql_query])
    
    for table_name in tables:
        # Parse schema.table format
        if '.' in table_name:
            parts = table_name.replace('[', '').replace(']', '').split('.')
            schema_name = parts[0] if len(parts) > 1 else 'dbo'
            table = parts[1] if len(parts) > 1 else parts[0]
        else:
            schema_name = 'dbo'
            table = table_name.replace('[', '').replace(']', '')
        
        ranked_tables.append(RankedTable(
            schema_name=schema_name,
            table_name=table,
            score=100,  # Exact match gets highest score
            matched_by=['knowledge_base_exact_match'],
            data_source=None,
            data_group=None
        ))
    
    return ranked_tables


def check_knowledge_base_exact_match(
    query: str, 
    llm_service: Optional[LLMServiceBase] = None,
    top_k: int = 3
) -> Optional[Dict[str, Any]]:
    """
    Stage 1: Check knowledge base for exact query match
    
    Strategy:
    1. Search knowledge base for similar queries
    2. Check if top result score meets threshold (L2 distance < 0.1)
    3. If threshold met, ask LLM to validate if SQL can be reused
    4. Return match with SQL, question, tables, and score if validated
    
    Args:
        query: User's natural language query
        llm_service: LLM service for validation and table extraction
        top_k: Number of similar queries to retrieve
        
    Returns:
        Dict with keys: question, sql_query, tables, score
        None if no exact match found
    """
    if not llm_service:
        return None
    
    vector_store = get_vector_store()
    
    # Search knowledge base for similar queries
    raw_few_shots = vector_store.search_fewshots(query, top_k=top_k, knowledge_type="sql_query")
    
    if not raw_few_shots:
        logging.info(f"[Knowledge Base] No similar queries found for: {query}")
        return None
    
    # Check top result
    top_result = raw_few_shots[0]
    score = top_result.get('score', float('inf'))
    
    logging.info(f"[Knowledge Base] Top result score: {score}")
    
    # Check score threshold (L2 distance - lower is better)
    if score > KNOWLEDGE_BASE_EXACT_MATCH_THRESHOLD:
        logging.info(f"[Knowledge Base] Score {score} exceeds threshold {KNOWLEDGE_BASE_EXACT_MATCH_THRESHOLD}")
        return None
    
    # Extract query details
    if isinstance(top_result, dict):
        entity = top_result.get('entity', top_result)
        question = entity.get('question', '')
        sql_query = entity.get('sql_query', '')
        
        if not sql_query:
            return None
        
        # Ask LLM to validate if this SQL can answer the user's query
        validation_prompt = f"""You are a SQL expert. Compare these two questions:

EXISTING QUESTION: {question}
EXISTING SQL: {sql_query}

USER'S NEW QUESTION: {query}

Can the EXISTING SQL query directly answer the USER'S NEW QUESTION without any modifications?
Consider:
- Are the data requirements the same?
- Are the filters/conditions compatible?
- Does it return the information the user is asking for?

Respond with only: YES or NO"""

        try:
            llm_response = llm_service.chat(validation_prompt, temperature=0).strip().upper()
            
            if 'YES' in llm_response:
                logging.info(f"[Knowledge Base] EXACT MATCH FOUND! LLM validated SQL can be reused")
                
                # Extract tables from SQL
                tables = llm_service.extract_tables_from_sql([sql_query])
                
                return {
                    'question': question,
                    'sql_query': sql_query,
                    'tables': tables,
                    'score': score
                }
            else:
                logging.info(f"[Knowledge Base] LLM validation failed: {llm_response}")
                return None
                
        except Exception as e:
            logging.error(f"[Knowledge Base] LLM validation error: {e}")
            return None
    
    return None


def perform_three_pronged_discovery(query: str, llm_service: Optional[LLMServiceBase] = None) -> ThreeProngedResult:
    """
    NEW STRATEGY: Sequential discovery with early exit optimization
    
    Flow:
    1. Knowledge Base Search (Primary) - Check for exact match first
       - If found: Return immediately with SQL reference
    2. Skills-Based Discovery - Keyword matching
       - If high scores (≥15): Present top 20 to user
    3. Value Index Fallback - Only if skills scores are low
       - Merge with low-score skills results
       - Present top 20 merged results to user
    
    Args:
        query: User's natural language query
        llm_service: LLM service for validation and extraction
        
    Returns:
        ThreeProngedResult with discovery results and user selection requirements
    """
    logging.info(f"[Discovery] Starting three-pronged discovery for: {query}")
    
    # ========================================
    # STAGE 1: Knowledge Base Exact Match
    # ========================================
    exact_match = check_knowledge_base_exact_match(query, llm_service)
    
    if exact_match:
        logging.info(f"[Discovery] EXACT MATCH FOUND in knowledge base!")
        logging.info(f"[Discovery] Matched question: {exact_match['question']}")
        
        # Extract tables from the matched SQL
        tables = extract_tables_from_match(exact_match, llm_service)
        
        return ThreeProngedResult(
            exact_match_found=True,
            exact_match_query=exact_match,
            merged_candidates=tables,
            knowledge_base_tables=tables,
            requires_user_selection=False  # No selection needed - exact match found
        )
    
    logging.info(f"[Discovery] No exact match found, proceeding to skills-based discovery")
    
    # ========================================
    # STAGE 2: Skills-Based Discovery
    # ========================================
    skills_result = perform_skills_based_discovery(query, llm_service)
    skills_tables = skills_result.candidate_tables
    
    logging.info(f"[Discovery] Skills found {len(skills_tables)} candidate tables")
    
    # Check for high-confidence matches
    high_score_tables = [t for t in skills_tables if t.score >= SKILLS_HIGH_SCORE_THRESHOLD]
    
    if high_score_tables:
        logging.info(f"[Discovery] Found {len(high_score_tables)} high-score matches (≥{SKILLS_HIGH_SCORE_THRESHOLD})")
        
        # Sort by score and take top K
        top_candidates = sorted(high_score_tables, key=lambda x: x.score, reverse=True)[:USER_SELECTION_TOP_K]
        
        logging.info(f"[Discovery] Presenting top {len(top_candidates)} candidates to user for selection")
        
        return ThreeProngedResult(
            skills_tables=skills_tables,
            requires_user_selection=True,
            selection_candidates=top_candidates,
            merged_candidates=[]  # Will be populated after user selection
        )
    
    logging.info(f"[Discovery] No high-score skills matches, falling back to value index merge")
    
    # ========================================
    # STAGE 3: Value Index Fallback + Merge
    # ========================================
    value_tables = perform_value_index_search(query)
    
    logging.info(f"[Discovery] Value index found {len(value_tables)} candidate tables")
    
    # Merge low-score skills results with value index
    merged = rerank_candidates(skills_tables, value_tables, [])
    
    # Sort by score and take top K
    top_merged = sorted(merged, key=lambda x: x.score, reverse=True)[:USER_SELECTION_TOP_K]
    
    logging.info(f"[Discovery] Merged results: {len(merged)} total, presenting top {len(top_merged)} to user")
    
    return ThreeProngedResult(
        skills_tables=skills_tables,
        value_tables=value_tables,
        requires_user_selection=True,
        selection_candidates=top_merged,
        merged_candidates=[]  # Will be populated after user selection
    )


def rerank_candidates(
    skills_tables: List[RankedTable],
    value_tables: List[RankedTable],
    kb_tables: List[RankedTable]
) -> List[RankedTable]:
    """
    Stage 4: Reranking & Deduplication
    
    Scoring:
    - Skills match: +10 points (authoritative)
    - Value index: +8 points (exact entity match)
    - Knowledge base: +5 points (proven query pattern)
    
    Args:
        skills_tables: Tables from skills navigation
        value_tables: Tables from value index
        kb_tables: Tables from knowledge base
        
    Returns:
        Deduplicated and ranked list of tables
    """
    # Build a map of (schema, table) -> RankedTable with cumulative scores
    table_map: Dict[tuple, RankedTable] = {}
    
    def normalize_key(schema: str, table: str) -> tuple:
        """Normalize table identifier for deduplication"""
        return (schema.lower().replace('[', '').replace(']', ''),
                table.lower().replace('[', '').replace(']', ''))
    
    # Process skills tables
    for table in skills_tables:
        key = normalize_key(table.schema_name, table.table_name)
        if key in table_map:
            table_map[key].score += 10
            if 'skills' not in table_map[key].matched_by:
                table_map[key].matched_by.append('skills')
        else:
            table.score = 10
            table.matched_by = ['skills']
            table_map[key] = table
    
    # Process value index tables
    for table in value_tables:
        key = normalize_key(table.schema_name, table.table_name)
        if key in table_map:
            table_map[key].score += 8
            if 'value_index' not in table_map[key].matched_by:
                table_map[key].matched_by.append('value_index')
        else:
            table.score = 8
            table.matched_by = ['value_index']
            table_map[key] = table
    
    # Process knowledge base tables
    for table in kb_tables:
        key = normalize_key(table.schema_name, table.table_name)
        if key in table_map:
            table_map[key].score += 5
            if 'knowledge_base' not in table_map[key].matched_by:
                table_map[key].matched_by.append('knowledge_base')
        else:
            table.score = 5
            table.matched_by = ['knowledge_base']
            table_map[key] = table
    
    # Sort by score descending
    ranked = sorted(table_map.values(), key=lambda x: x.score, reverse=True)
    
    return ranked


def check_smart_threshold(candidates: List[RankedTable]) -> ThresholdDecision:
    """
    Stage 5: Smart Threshold Decision
    
    Decision Logic:
    - IF (cross_schema OR cross_database) AND tables >= 5: Trigger user selection
    - ELSE IF tables >= 10: Trigger user selection
    - ELSE: Auto-proceed
    
    Args:
        candidates: List of ranked candidate tables
        
    Returns:
        ThresholdDecision with auto_proceed flag and analysis
    """
    total_tables = len(candidates)
    
    # Detect cross-schema situation
    schemas = set(t.schema_name.lower() for t in candidates)
    cross_schema = len(schemas) > 1
    
    # Detect cross-database situation
    data_sources = set(t.data_source for t in candidates if t.data_source)
    cross_database = len(data_sources) > 1
    
    # Apply threshold logic
    if (cross_schema or cross_database) and total_tables >= 5:
        return ThresholdDecision(
            auto_proceed=False,
            total_tables=total_tables,
            cross_schema=cross_schema,
            cross_database=cross_database,
            trigger_reason="cross_schema_detected" if cross_schema else "cross_database_detected"
        )
    elif total_tables >= 10:
        return ThresholdDecision(
            auto_proceed=False,
            total_tables=total_tables,
            cross_schema=cross_schema,
            cross_database=cross_database,
            trigger_reason="high_table_count"
        )
    elif total_tables < 3:
        return ThresholdDecision(
            auto_proceed=False,
            total_tables=total_tables,
            cross_schema=cross_schema,
            cross_database=cross_database,
            trigger_reason="insufficient_results"
        )
    else:
        return ThresholdDecision(
            auto_proceed=True,
            total_tables=total_tables,
            cross_schema=cross_schema,
            cross_database=cross_database,
            trigger_reason=None
        )


def generate_user_selection_prompt(
    candidates: List[RankedTable],
    query: str,
    llm_service: Optional[LLMServiceBase] = None
) -> SelectionPrompt:
    """
    Stage 6: Generate User Selection UI Data
    
    Groups candidates by:
    - Recommended (LLM confidence > 80% or score > 15)
    - Ambiguous (user must choose - cross-schema groups)
    - Additional options (other possibilities)
    
    Args:
        candidates: List of ranked candidate tables
        query: User's original query
        llm_service: Optional LLM for confidence scoring
        
    Returns:
        SelectionPrompt with grouped recommendations
    """
    recommended = []
    ambiguous_groups = []
    additional_options = []
    
    # High-confidence threshold
    confidence_threshold = 15
    
    # Separate by score
    for table in candidates:
        if table.score >= confidence_threshold:
            recommended.append(table)
    
    # Group remaining tables by schema for ambiguous section
    remaining = [t for t in candidates if t.score < confidence_threshold]
    
    if remaining:
        # Group by schema
        schema_groups = defaultdict(list)
        for table in remaining:
            schema_groups[table.schema_name].append(table)
        
        # Create ambiguous groups for cross-schema scenarios
        for schema, tables in schema_groups.items():
            ambiguous_groups.append({
                'label': f"{schema.capitalize()} Schema",
                'table_count': len(tables),
                'tables': [f"{t.schema_name}.{t.table_name}" for t in tables],
                'description': f"{len(tables)} tables from {schema} schema"
            })
    
    # Additional options (low score or single matches)
    low_score_tables = [t for t in candidates if t.score < 5]
    if low_score_tables:
        data_group_map = defaultdict(list)
        for table in low_score_tables:
            if table.data_group:
                data_group_map[table.data_group].append(table)
        
        for group_name, tables in data_group_map.items():
            additional_options.append({
                'label': group_name,
                'table_count': len(tables),
                'tables': [f"{t.schema_name}.{t.table_name}" for t in tables],
                'description': f"Additional tables from {group_name}"
            })
    
    return SelectionPrompt(
        recommended=recommended,
        ambiguous_groups=ambiguous_groups,
        additional_options=additional_options
    )


def apply_user_selection(
    candidates: List[RankedTable],
    user_choices: List[str]
) -> List[RankedTable]:
    """
    Filter candidates based on user's checkbox selections
    
    Args:
        candidates: Full list of candidate tables
        user_choices: List of selected table names (format: "schema.table")
        
    Returns:
        Filtered list of RankedTable objects
    """
    if not user_choices:
        return candidates
    
    # Normalize user choices
    normalized_choices = set()
    for choice in user_choices:
        choice = choice.lower().replace('[', '').replace(']', '')
        normalized_choices.add(choice)
    
    # Filter candidates
    filtered = []
    for table in candidates:
        table_name = f"{table.schema_name}.{table.table_name}".lower()
        if table_name in normalized_choices:
            filtered.append(table)
    
    return filtered


def validate_groups_with_llm(
    query: str,
    matched_groups: List,
    llm_service: LLMServiceBase
) -> List:
    """
    LLM validates relevance of matched data groups
    
    Args:
        query: User's query
        matched_groups: List of DataGroup objects from keyword matching
        llm_service: LLM service for validation
        
    Returns:
        Filtered list of validated data groups
    """
    # TODO: Implement LLM validation
    # For now, return all matched groups
    # Future: Ask LLM "Does {group.description} answer the query: {query}?"
    return matched_groups


def hydrate_discovery_context_from_skills(
    table_names: List[str],
    similar_queries: List[Dict]
) -> DiscoveryContext:
    """
    Build DiscoveryContext by loading table schemas from skills files
    
    Args:
        table_names: List of table names (format: "schema.table")
        similar_queries: List of similar queries from knowledge base
        
    Returns:
        DiscoveryContext with full table schemas
    """
    skills_service = get_skills_service()
    
    # Load table schemas from skills
    # For each table name, find corresponding .md file
    table_schemas = []
    
    for table_name in table_names:
        # Parse schema.table format
        if '.' in table_name:
            parts = table_name.replace('[', '').replace(']', '').split('.')
            schema_name = parts[0]
            table = parts[1]
        else:
            schema_name = 'dbo'
            table = table_name.replace('[', '').replace(']', '')
        
        # Find the table schema file in skills directory
        # Pattern: skills/data-sources/{data-source}/schemas/{schema}/{schema}.{table}.md
        # We need to search for it since we don't know the data source
        from pathlib import Path
        skills_path = Path("skills/data-sources")
        
        # Search for the table file
        matches = list(skills_path.rglob(f"schemas/{schema_name}/{schema_name}.{table}.md"))
        
        if matches:
            # Load the first match
            table_schema = skills_service._parse_table_schema_file(matches[0])
            if table_schema:
                table_schemas.append(table_schema)
    
    return DiscoveryContext(
        relevant_tables=table_schemas,
        similar_queries=similar_queries,
        glossary_terms={}
    )
