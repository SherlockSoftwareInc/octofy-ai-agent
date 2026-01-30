"""
Discovery Service - Enhanced with Skills-Based Discovery

Implements three-pronged discovery:
1. Skills Navigation (Primary) - Keyword-based data group matching
2. Value Index Search - Entity-to-table mapping
3. Knowledge Base Search - Similar query pattern matching
"""

from typing import List, Dict, Optional, Set
from collections import defaultdict

from app.models.schemas import (
    DiscoveryRequest, DiscoveryResponse, DiscoveryContext,
    TableSchema, RankedTable, ThresholdDecision, SelectionPrompt,
    SkillsDiscoveryResult, ThreeProngedResult
)
from app.services.vector_store import get_vector_store
from app.services.skills_service import get_skills_service
from app.services.llm_service import LLMServiceBase


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
    Stage 2B: Value Index Search (Entity Mapping)
    
    Args:
        query: User's natural language query
        top_k: Number of top results to return
        
    Returns:
        List of RankedTable objects from value index
    """
    vector_store = get_vector_store()
    
    # Search value index for entity matches
    value_results = vector_store.search_values(query, top_k=top_k)
    
    ranked_tables = []
    for result in value_results:
        if isinstance(result, dict):
            entity = result.get('entity', {})
            schema_name = entity.get('schema_name', 'dbo')
            table_name = entity.get('table_name', '')
            
            if table_name:
                ranked_tables.append(RankedTable(
                    schema_name=schema_name,
                    table_name=table_name,
                    score=8,  # Value index score
                    matched_by=['value_index'],
                    data_source=None,
                    data_group=None
                ))
    
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


def perform_three_pronged_discovery(query: str, llm_service: Optional[LLMServiceBase] = None) -> ThreeProngedResult:
    """
    Stage 2: Orchestrate three-pronged discovery (parallel)
    
    Args:
        query: User's natural language query
        llm_service: LLM service for validation and extraction
        
    Returns:
        ThreeProngedResult with merged candidates from all sources
    """
    # Run all three discovery methods
    skills_result = perform_skills_based_discovery(query, llm_service)
    value_tables = perform_value_index_search(query)
    kb_tables = perform_knowledge_base_search(query, llm_service)
    
    # Skills tables come from the SkillsDiscoveryResult
    skills_tables = skills_result.candidate_tables
    
    # Merge and deduplicate
    merged = rerank_candidates(skills_tables, value_tables, kb_tables)
    
    return ThreeProngedResult(
        skills_tables=skills_tables,
        value_tables=value_tables,
        knowledge_base_tables=kb_tables,
        merged_candidates=merged
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
