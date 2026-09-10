from app.models.schemas import GenerateSQLRequest, GenerateSQLResponse, DiscoveryContext, AgentStatus, TableSchema
import re
import logging
from typing import Optional, Tuple, List, Dict, Any, Generator, Union, Set
from datetime import datetime
from app.services.llm_service import get_llm_service
from app.services.discovery_service import (
    perform_discovery, DiscoveryRequest,
    perform_three_pronged_discovery, check_smart_threshold,
    generate_user_selection_prompt, hydrate_discovery_context_from_skills
)
from app.services.validation_service import validate_sql_with_db
from app.services.vector_store import get_vector_store
from app.services.settings_service import get_settings_for_display
from app.services.relationship_graph import get_relationship_graph
from collections import defaultdict
from app.services.system_query_service import classify_query_intent, build_system_catalog_prompt

def parse_table_override_name(raw_name: str) -> Tuple[str, str]:
    cleaned = raw_name.strip().replace('[', '').replace(']', '')
    if '.' in cleaned:
        schema, table = cleaned.split('.', 1)
        return schema.strip() or "dbo", table.strip()
    return "dbo", cleaned.strip()


def _normalize_database_objects(database_objects: Optional[List[str]]) -> List[str]:
    if not database_objects:
        return []
    cleaned = []
    seen = set()
    for obj in database_objects:
        if not obj:
            continue
        item = str(obj).strip()
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
    return cleaned


def _resolve_database_objects_to_tables(
    database_objects: List[str],
    vector_store,
    source_id: Optional[str],
    allowed_tables: Optional[Set[str]] = None
) -> Tuple[List[TableSchema], List[str]]:
    if not database_objects:
        return [], []

    resolved_tables: List[TableSchema] = []
    unresolved: List[str] = []

    for raw_obj in database_objects:
        cleaned = raw_obj.strip().replace('[', '').replace(']', '')
        if not cleaned:
            continue

        parts = [p for p in cleaned.split('.') if p]
        schema_name = None
        table_name = None
        if len(parts) >= 2:
            schema_name, table_name = parts[0], parts[1]
        elif parts:
            schema_name, table_name = "dbo", parts[0]

        matched = None
        if schema_name and table_name:
            try:
                matched = vector_store.get_schema_by_name(schema_name, table_name)
            except Exception:
                matched = None

        if not matched:
            try:
                candidates = _search_schemas_scoped(
                    vector_store,
                    raw_obj,
                    top_k=1,
                    source_id=source_id
                )
                if candidates:
                    matched = candidates[0]
            except Exception:
                matched = None

        if matched:
            full_name = f"{matched.schema_name}.{matched.table_name}".lower()
            if allowed_tables and full_name not in allowed_tables:
                unresolved.append(raw_obj)
                continue
            if not any(
                t.schema_name == matched.schema_name and t.table_name == matched.table_name
                for t in resolved_tables
            ):
                resolved_tables.append(matched)
        else:
            unresolved.append(raw_obj)

    return resolved_tables, unresolved


def _merge_tables_into_context(context: DiscoveryContext, tables: List[TableSchema]) -> None:
    if not tables:
        return
    existing = {(t.schema_name.lower(), t.table_name.lower()) for t in context.relevant_tables}
    insert_index = 0
    for table in tables:
        key = (table.schema_name.lower(), table.table_name.lower())
        if key in existing:
            continue
        context.relevant_tables.insert(insert_index, table)
        insert_index += 1
        existing.add(key)

def hydrate_override_context(
    table_names: List[str],
    source_id: Optional[str] = None
) -> DiscoveryContext:
    if source_id:
        return hydrate_discovery_context_from_skills(
            table_names,
            similar_queries=[],
            source_id=source_id
        )

    vector_store = get_vector_store()
    selected_schemas = []
    for raw_name in table_names:
        schema_name, table_name = parse_table_override_name(raw_name)
        schema = vector_store.get_schema_by_name(schema_name, table_name)
        if schema:
            selected_schemas.append(schema)
    return DiscoveryContext(
        relevant_tables=selected_schemas,
        similar_queries=[]
    )

def rerank_and_select_tables(few_shot_tables: List[str], value_tables: List[str], schema_tables: List[str]) -> List[str]:
    scores = defaultdict(int)
    display_names = {}
    
    def normalize(name):
        return name.lower().replace('[', '').replace(']', '').strip()
        
    def process_list(tables, weight):
        for t in tables:
            norm = normalize(t)
            if not norm: continue
            scores[norm] += weight
            # Prefer names with dots (schema qualified) (or first encountered if not present)
            if norm not in display_names:
                display_names[norm] = t
            elif '.' in t and '.' not in display_names[norm]:
                display_names[norm] = t
                
                
    process_list(value_tables, 10)  # Value matches are critical
    process_list(few_shot_tables, 5) # Few-shot is strong indicator
    process_list(schema_tables, 2)   # Schema search is backup relevance
    
    # Sort by score descending
    sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    # Return top 8 display names
    return [display_names[item[0]] for item in sorted_items[:8]]


def _get_allowed_table_set(vector_store, source_id: Optional[str]) -> Optional[Set[str]]:
    if not source_id:
        return None
    try:
        objects = vector_store.get_all_objects_v2(source_id)
    except Exception:
        return None

    if not objects:
        return None

    allowed_tables: Set[str] = set()
    for obj in objects or []:
        obj_type = (obj.get("object_type") or "").lower()
        if obj_type not in {"table", "view"}:
            continue
        schema_name = obj.get("schema_name")
        object_name = obj.get("object_name")
        if schema_name and object_name:
            allowed_tables.add(f"{schema_name}.{object_name}".lower())
    return allowed_tables


def _filter_table_names_by_source(
    table_names: List[str],
    allowed_tables: Optional[Set[str]]
) -> List[str]:
    if allowed_tables is None:
        return table_names

    filtered = []
    for table_name in table_names:
        norm = table_name.lower().replace('[', '').replace(']', '').strip()
        if not norm:
            continue
        if '.' in norm and norm in allowed_tables:
            filtered.append(table_name)
        elif '.' not in norm and f"dbo.{norm}" in allowed_tables:
            filtered.append(table_name)
    return filtered


def _filter_ranked_tables_by_source(
    ranked_tables: List[Any],
    allowed_tables: Optional[Set[str]]
) -> List[Any]:
    if allowed_tables is None:
        return ranked_tables
    return [
        t for t in ranked_tables
        if f"{t.schema_name}.{t.table_name}".lower() in allowed_tables
    ]


def _search_schemas_scoped(
    vector_store,
    query: str,
    top_k: int,
    source_id: Optional[str]
) -> List[TableSchema]:
    if not source_id:
        return vector_store.search_schemas(query, top_k)

    try:
        objects = vector_store.search_objects_v2(
            query=query,
            top_k=top_k,
            source_id=source_id,
            object_types=["table", "view"]
        )
        schemas = []
        for obj in objects or []:
            schema_name = obj.get("schema_name") or "dbo"
            table_name = obj.get("object_name") or "unknown"
            schemas.append(TableSchema(
                schema_name=schema_name,
                table_name=table_name,
                table_type=obj.get("object_type", "table"),
                description=obj.get("description", ""),
                columns=[]
            ))
        return schemas
    except Exception:
        return vector_store.search_schemas(query, top_k)


def _search_values_scoped(
    vector_store,
    query: str,
    top_k: int,
    allowed_tables: Optional[Set[str]]
) -> List[Dict[str, Any]]:
    results = vector_store.search_values(query, top_k=top_k)
    if allowed_tables is None:
        return results
    return [
        r for r in results
        if f"{r.get('schema_name', 'dbo')}.{r.get('table_name', '')}".lower() in allowed_tables
    ]


def _hydrate_discovery_context_scoped(
    table_names: List[str],
    similar_queries: List[Dict],
    source_id: Optional[str]
) -> DiscoveryContext:
    if source_id:
        return hydrate_discovery_context_from_skills(
            table_names,
            similar_queries=similar_queries,
            source_id=source_id
        )
    return hydrate_discovery_context(table_names, similar_queries)

def hydrate_discovery_context(table_names: List[str], similar_queries: List[Dict]) -> DiscoveryContext:
    vector_store = get_vector_store()
    # 1. Fetch all schemas (efficient enough for <1000 tables)
    all_schemas = vector_store.get_all_schemas()
    
    # 2. Map normalized names to selection
    target_map = {}
    for t in table_names:
        norm = t.lower().replace('[', '').replace(']', '').strip()
        target_map[norm] = True
        # Also handle implicit dbo if missing
        if '.' not in norm:
            target_map[f"dbo.{norm}"] = True
            
    selected_schemas = []
    for schema in all_schemas:
        full_name = f"{schema.schema_name}.{schema.table_name}".lower()
        if full_name in target_map:
            selected_schemas.append(schema)
    
    # 3. Format similar queries
    formatted_queries = []
    for sq in similar_queries:
        formatted_queries.append({
            "question": sq.get("question", ""),
            "sql": sq.get("sql_query", "") or sq.get("sql", "")
        })
            
    return DiscoveryContext(
        relevant_tables=selected_schemas,
        similar_queries=formatted_queries
    )

def expand_context_with_neighbors(
    selected_tables: List[str],
    user_query: str,
    source_id: Optional[str] = None
) -> List[str]:
    """
    Use LLM to identify disjoint tables and suggest intermediate glue tables.
    """
    try:
        vector_store = get_vector_store()
        # Ask LLM for suggestions
        llm_service = get_llm_service()
        suggestions = llm_service.suggest_intermediate_tables(selected_tables, user_query)
        
        if not suggestions:
            return selected_tables
            
        logging.info(f"Context Expansion: LLM suggested glue tables: {suggestions}")
        
        # Search for these tables in schema index to verify existence
        verified_additions = []
        for table_suggestion in suggestions:
            # Semantic search for the specific table name
            results = _search_schemas_scoped(vector_store, table_suggestion, top_k=1, source_id=source_id)
            for res in results:
                # Basic fuzzy match check
                found_name = f"{res.schema_name}.{res.table_name}"
                simple_suggest = table_suggestion.lower().replace('[', '').replace(']', '').split('.')[-1]
                simple_found = res.table_name.lower()
                
                if simple_suggest in simple_found or simple_found in simple_suggest:
                    verified_additions.append(found_name)
                    
        # Combine unique
        final_set = set(selected_tables)
        final_set.update(verified_additions)
        
        return list(final_set)
        
    except Exception as e:
        print(f"Error in context expansion: {e}")
        return selected_tables

def expand_value_tables_with_relationships(
    value_tables: List[str],
    max_hops: int = 2,
    max_per_hit: int = 3
) -> List[str]:
    """
    Expand value index table list by tracing FK relationships.
    
    For each table in value_tables, follows FK edges up to max_hops
    to discover related data tables (capped at max_per_hit per source).
    
    Args:
        value_tables: List of "schema.table" strings from value index search
        max_hops: Maximum FK hops to traverse
        max_per_hit: Maximum related tables to add per source table
        
    Returns:
        Expanded list of "schema.table" strings (originals + discovered)
    """
    if not value_tables:
        return value_tables
    
    try:
        graph = get_relationship_graph()
    except Exception as e:
        logging.warning(f"[Relationship] Graph unavailable (non-fatal): {e}")
        return value_tables
    
    seen = set()
    result = []
    
    for table_str in value_tables:
        # Normalize and parse
        clean = table_str.replace('[', '').replace(']', '').strip()
        if '.' in clean:
            parts = clean.split('.', 1)
            schema_name, table_name = parts[0], parts[1]
        else:
            schema_name, table_name = 'dbo', clean
        
        key = (schema_name.lower(), table_name.lower())
        if key not in seen:
            seen.add(key)
            result.append(table_str)  # keep original formatting
        
        # Trace relationships
        try:
            related = graph.trace_related_tables(schema_name, table_name, max_hops=max_hops, max_tables=max_per_hit)
            for rel in related:
                rel_key = (rel.schema_name.lower(), rel.table_name.lower())
                if rel_key not in seen:
                    seen.add(rel_key)
                    result.append(f"{rel.schema_name}.{rel.table_name}")
                    logging.info(f"[Relationship] Expanded: {schema_name}.{table_name} -> {rel.schema_name}.{rel.table_name}")
        except Exception as e:
            logging.warning(f"[Relationship] Trace failed for {schema_name}.{table_name} (non-fatal): {e}")
    
    return result

def extract_entities(query: str) -> Tuple[List[str], List[str]]:
    """
    Extract key nouns (entities) and date ranges from query.
    Returns: (entities, date_ranges)
    """
    # Extract potential table/entity names
    entities = []
    date_pattern = r'\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2}|January|February|March|April|May|June|July|August|September|October|November|December|\d{4})\b'
    date_ranges = re.findall(date_pattern, query, re.IGNORECASE)
    
    # Extract nouns (simplified: common business terms)
    noun_pattern = r'\b(customers?|orders?|products?|employees?|suppliers?|categories?|shippers?|territories?|region|sales|inventory|transactions?|revenues?|invoices?|shipments?)\b'
    entities = list(set(re.findall(noun_pattern, query, re.IGNORECASE)))
    
    return entities, date_ranges

def score_query_complexity(query: str) -> str:
    """
    Score query complexity to adjust generation strategy.
    Returns: 'simple', 'moderate', or 'complex'
    """
    query_lower = query.lower()
    
    # Complex indicators
    complex_keywords = [
        'join', 'aggregate', 'group by', 'multiple', 'compare',
        'relationship', 'across', 'between', 'correlate',
        'average', 'above average', 'below average', 'exceed',
        'top n', 'rank', 'percentile', 'cumulative',
        'step by step', 'first find', 'then', 'based on',
        'who spent more than', 'having', 'subquery',
        'dependency', 'dependencies', 'multi-step',
    ]
    complex_count = sum(1 for kw in complex_keywords if kw in query_lower)
    
    if complex_count >= 2:
        return 'complex'
    elif complex_count == 1:
        return 'moderate'
    else:
        return 'simple'


def parse_validation_error(text: str) -> tuple[bool, str, list[str]]:
    """
    Check if the text is a validation error message from the LLM.
    Returns (is_error, error_message, missing_items)
    """
    text = text.strip()
    missing_items = []
    
    if text.startswith("COLUMN_VALIDATION_ERROR") or text.startswith("TABLE_VALIDATION_ERROR"):
        # Format: "TYPE_ERROR: Cannot find ... [item] ..."
        match = re.search(r'\[([^\]]+)\]', text)
        if match:
            missing_items.append(match.group(1))
        return True, text, missing_items
    
    return False, "", []

def lookup_values_for_query(
    query: str,
    threshold: float = 0.7,
    allowed_tables: Optional[Set[str]] = None
) -> Dict[str, List[str]]:
    """
    Look up relevant values in the value index based on the user query.
    
    Args:
        query: User's natural language question
        threshold: Similarity score threshold (0-1)
    
    Returns:
        Dictionary mapping unique values to their metadata
    """
    try:
        vector_store = get_vector_store()
        # Search for values relevant to the query
        results = _search_values_scoped(vector_store, query, top_k=10, allowed_tables=allowed_tables)
        
        # Filter by similarity score if available
        filtered_results = []
        for result in results:
            # Check if score field exists and exceeds threshold
            # Note: Milvus L2 distance is lower for more similar items, so invert the logic
            score = result.get('score', 0)
            # L2 distance: lower = more similar, typically between 0-2 for normalized embeddings
            # Convert to similarity score (1 - normalized_distance)
            if score <= (2 - threshold * 2):  # Rough conversion
                filtered_results.append(result)
        
        # Group results by table.column for context injection
        value_map = {}
        for result in filtered_results[:5]:  # Limit to top 5
            entity = result.get('entity', result)
            value = entity.get('value', result.get('value', ''))
            table_name = entity.get('table_name', result.get('table_name', ''))
            column_name = entity.get('column_name', result.get('column_name', ''))
            schema_name = entity.get('schema_name', result.get('schema_name', 'dbo'))
            
            key = f"{schema_name}.{table_name}.{column_name}"
            if key not in value_map:
                value_map[key] = []
            value_map[key].append(value)
        
        return value_map
    except Exception as e:
        print(f"Error looking up values: {e}")
        return {}

def validate_schema_completeness(context: DiscoveryContext, user_query: str, llm_service) -> Tuple[bool, List[str], str]:
    """
    Validate if all referenced tables (foreign keys) are present in the context.
    Uses LLM to analyze schema descriptions for table references.
    
    Args:
        context: Current discovery context with table schemas
        user_query: User's natural language query
        llm_service: LLM service instance for validation
        
    Returns:
        Tuple of (is_complete, missing_tables, analysis)
        - is_complete: True if all referenced tables are present
        - missing_tables: List of missing table names (empty if complete)
        - analysis: LLM's explanation of the validation result
    """
    try:
        # Skip validation if no tables in context
        if not context.relevant_tables or len(context.relevant_tables) == 0:
            return True, [], "No tables in context to validate"
        
        # Call LLM to validate schema references
        validation_result = llm_service.validate_schema_references(
            context.relevant_tables,
            user_query
        )
        
        # Parse the validation result
        is_complete = True
        missing_tables = []
        analysis = ""
        
        lines = validation_result.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith("SCHEMA_COMPLETE:"):
                complete_status = line.split(":", 1)[1].strip().upper()
                is_complete = complete_status == "YES"
            elif line.startswith("MISSING_TABLES:"):
                tables_str = line.split(":", 1)[1].strip()
                if tables_str and tables_str.upper() != "NONE":
                    # Parse comma-separated table names
                    missing_tables = [t.strip() for t in tables_str.split(",") if t.strip()]
            elif line.startswith("ANALYSIS:"):
                analysis = line.split(":", 1)[1].strip()
        
        # Log the validation outcome
        logging.info(f"Schema validation - Complete: {is_complete}, Missing: {missing_tables}")
        
        return is_complete, missing_tables, analysis
        
    except Exception as e:
        # On error, assume complete to avoid blocking SQL generation
        logging.error(f"Error validating schema completeness: {e}")
        return True, [], f"Validation error: {e}"


def expand_context_for_missing_data(
    context: DiscoveryContext,
    search_suggestions: List[str],
    max_suggestions: int = 5,
    source_id: Optional[str] = None
) -> Tuple[List[str], DiscoveryContext]:
    """
    Expand the discovery context by searching for tables that might contain missing data.
    
    This is called when the schema sufficiency check detects that required columns
    are missing from the current context. It searches for suggested terms in the
    schema/value indexes and adds any newly discovered tables to the context.
    
    Args:
        context: Current discovery context with relevant tables
        search_suggestions: List of search terms from sufficiency check (e.g., ["tax", "SalesTax"])
        max_suggestions: Maximum number of suggestions to search for
        
    Returns:
        Tuple of (tables_added, updated_context)
        - tables_added: List of "schema.table" strings that were added
        - updated_context: The context with new tables appended
    """
    tables_added = []
    
    for suggestion in search_suggestions[:max_suggestions]:
        try:
            disc_res = perform_discovery(DiscoveryRequest(
                query=suggestion,
                top_k=3,
                source_id=source_id
            ))
            for table in disc_res.context.relevant_tables:
                # Check if table already exists in context
                already_exists = any(
                    t.table_name == table.table_name and t.schema_name == table.schema_name 
                    for t in context.relevant_tables
                )
                if not already_exists:
                    context.relevant_tables.append(table)
                    tables_added.append(f"{table.schema_name}.{table.table_name}")
        except Exception as e:
            logging.warning(f"Discovery failed for suggestion '{suggestion}': {e}")
    
    return tables_added, context


def search_data_objects(query: str) -> GenerateSQLResponse:
    """
    Search for relevant database objects based on user query.
    Queries skills-based schema library (filesystem), Milvus vector indexes, 
    and returns unique [schema].[table] objects sorted by relevance.
    
    Uses a multi-source approach:
    1. Skills-based keyword search on filesystem schema library (.object-index.json)
    2. Skills-based data group search for broader coverage
    3. Semantic search on Milvus with score threshold (if enabled)
    4. Fallback keyword search on Milvus if no semantic matches found
    
    Args:
        query: User's search query
    
    Returns:
        GenerateSQLResponse with objects list in explanation field
    """
    try:
        from app.core.config import settings as app_settings
        
        # Track objects with their best (lowest) score - L2 distance where lower = more similar
        object_scores: Dict[str, float] = {}
        object_metadata: Dict[str, Dict[str, Optional[str]]] = {}

        def normalize_table_type(raw_type: Optional[str]) -> Optional[str]:
            if not raw_type:
                return None
            normalized = raw_type.strip().lower()
            if normalized == "table":
                return "Table"
            if normalized == "view":
                return "View"
            return raw_type.strip()
        
        # ================================================================
        # SOURCE 1: Skills-based schema library search (filesystem indexes)
        # ================================================================
        try:
            from app.services.skills_service import get_skills_service
            skills_service = get_skills_service()
            
            # 1a. Search object indexes by keyword (searches .object-index.json files)
            # This is the primary skills-based search - matches against object names, 
            # keywords, and descriptions in all data sources
            skills_results = skills_service.search_objects_by_keyword(query, top_k=20)
            logging.info(f"Skills object search for '{query}': {len(skills_results)} hits")
            
            for result in skills_results:
                schema_name = result.get('schema_name') or 'dbo'
                obj_name = result.get('object_name', '')
                obj_type = normalize_table_type(result.get('object_type'))
                skill_score = result.get('score', 0)
                
                if obj_name:
                    obj_key = f"[{schema_name}].[{obj_name}]"
                    # Convert skills score (higher=better) to L2-like score (lower=better)
                    # Skills scores range from ~1.0 to ~10.0+; map to 0.0-3.0 range
                    normalized_score = max(0.1, 3.0 - (skill_score * 0.3))
                    
                    if obj_key not in object_scores or normalized_score < object_scores[obj_key]:
                        object_scores[obj_key] = normalized_score
                    if obj_key not in object_metadata or (obj_type and not object_metadata[obj_key].get("type")):
                        object_metadata[obj_key] = {
                            "schema": schema_name,
                            "name": obj_name,
                            "type": obj_type
                        }
        except Exception as e:
            logging.warning(f"Skills-based search failed (non-fatal): {e}")
        
        # ================================================================
        # SOURCE 2: Milvus vector search (if enabled)
        # ================================================================
        if app_settings.VECTOR_DB_ENABLED:
            try:
                vector_store = get_vector_store()
                from pymilvus import utility
                
                # Diagnostic: track search statistics
                schema_total_hits = 0
                schema_filtered_hits = 0
                all_schema_scores = []  # Track all scores for debugging
                
                if utility.has_collection(app_settings.MILVUS_COLLECTION_SCHEMA):
                    embedding = vector_store._get_embedding(query)
                    
                    # First, get results with a very high threshold to see what's available
                    schema_results_unfiltered = vector_store._search_collection(
                        app_settings.MILVUS_COLLECTION_SCHEMA,
                        embedding,
                        ['schema_name', 'table_name', 'table_type'],
                        top_k=10,
                        score_threshold=10.0  # Very high to see all candidates
                    )
                    schema_total_hits = len(schema_results_unfiltered)
                    
                    # Collect all scores for diagnostics
                    for result in schema_results_unfiltered:
                        score = result.get('score', 999)
                        all_schema_scores.append(score)
                    
                    # Now filter with actual threshold
                    # If skills already found strong results, tighten Milvus threshold to reduce noise
                    skills_found_strong = any(
                        object_scores.get(k, 999) < 1.0 for k in object_scores
                    )
                    SCORE_THRESHOLD = 1.2 if skills_found_strong else 2.0
                    schema_results = [r for r in schema_results_unfiltered if r.get('score', 999) <= SCORE_THRESHOLD]
                    schema_filtered_hits = len(schema_results)
                    
                    logging.info(f"Schema search for '{query}': {schema_total_hits} total hits, {schema_filtered_hits} after threshold ({SCORE_THRESHOLD})")
                    if all_schema_scores:
                        logging.info(f"Score distribution: min={min(all_schema_scores):.3f}, max={max(all_schema_scores):.3f}, scores={[f'{s:.2f}' for s in sorted(all_schema_scores)[:5]]}")
                    
                    for result in schema_results:
                        entity = result.get('entity', result)
                        schema_name = entity.get('schema_name') or 'dbo'
                        table_name = entity.get('table_name', '')
                        table_type = normalize_table_type(entity.get('table_type'))
                        score = result.get('score', 999)
                        if table_name:
                            obj_key = f"[{schema_name}].[{table_name}]"
                            # Keep the best (lowest) score for each object
                            if obj_key not in object_scores or score < object_scores[obj_key]:
                                object_scores[obj_key] = score
                            if obj_key not in object_metadata or (table_type and not object_metadata[obj_key].get("type")):
                                object_metadata[obj_key] = {
                                    "schema": schema_name,
                                    "name": table_name,
                                    "type": table_type
                                }
                else:
                    logging.warning(f"Schema collection '{app_settings.MILVUS_COLLECTION_SCHEMA}' not found in Milvus")
                
                # Search value index for relevant tables
                value_results = vector_store.search_values(query, top_k=10)
                logging.info(f"Value search for '{query}': {len(value_results)} hits")
                for result in value_results:
                    entity = result.get('entity', result)
                    schema_name = entity.get('schema_name') or 'dbo'
                    table_name = entity.get('table_name', '')
                    score = result.get('score', 999)
                    if table_name:
                        obj_key = f"[{schema_name}].[{table_name}]"
                        # Keep the best (lowest) score for each object
                        if obj_key not in object_scores or score < object_scores[obj_key]:
                            object_scores[obj_key] = score
                        if obj_key not in object_metadata:
                            object_metadata[obj_key] = {
                                "schema": schema_name,
                                "name": table_name,
                                "type": None
                            }
                
                # Fallback: If no results at all (including skills), try keyword-based search on Milvus
                if not object_scores and utility.has_collection(app_settings.MILVUS_COLLECTION_SCHEMA):
                    logging.info(f"No semantic matches for '{query}', attempting keyword fallback search")
                    
                    # Extract keywords from query (words with 3+ chars, excluding common words)
                    stop_words = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 
                                 'was', 'one', 'our', 'out', 'has', 'have', 'been', 'find', 'get', 'show', 
                                 'list', 'what', 'which', 'where', 'how', 'top', 'best', 'most'}
                    query_words = set(word.lower() for word in re.findall(r'\b\w{3,}\b', query) if word.lower() not in stop_words)
                    
                    if query_words:
                        # Load collection and search all entities
                        from pymilvus import Collection
                        collection = Collection(app_settings.MILVUS_COLLECTION_SCHEMA)
                        collection.load()
                        
                        # Query all table names (limited to avoid memory issues)
                        try:
                            all_tables = collection.query(
                                expr="table_name != ''",
                                output_fields=['schema_name', 'table_name', 'table_type'],
                                limit=500
                            )
                            
                            # Score tables by keyword matches in name
                            for table in all_tables:
                                table_name = table.get('table_name', '').lower()
                                schema_name = table.get('schema_name', 'dbo')
                                table_type = normalize_table_type(table.get('table_type'))
                                
                                # Check for keyword matches
                                matches = sum(1 for word in query_words if word in table_name)
                                if matches > 0:
                                    obj_key = f"[{schema_name}].[{table.get('table_name', '')}]"
                                    # Use negative match count as score (more matches = better = lower score)
                                    keyword_score = 5.0 - (matches * 0.5)  # Score between 3.0-4.5 for fallback results
                                    
                                    if obj_key not in object_scores or keyword_score < object_scores[obj_key]:
                                        object_scores[obj_key] = keyword_score
                                    if obj_key not in object_metadata:
                                        object_metadata[obj_key] = {
                                            "schema": schema_name,
                                            "name": table.get('table_name', ''),
                                            "type": table_type
                                        }
                            
                            logging.info(f"Keyword fallback found {len(object_scores)} matching tables for keywords: {query_words}")
                        except Exception as e:
                            logging.warning(f"Keyword fallback search failed: {e}")
            except Exception as e:
                logging.warning(f"Milvus vector search failed (non-fatal): {e}")
        else:
            logging.info("Vector DB disabled, using skills-based search only")
        
        # Sort objects by score (lower = more relevant)
        sorted_objects = sorted(object_scores.keys(), key=lambda x: object_scores[x])
        
        objects_payload = [
            {
                "schema": object_metadata.get(obj, {}).get("schema", "dbo"),
                "name": object_metadata.get(obj, {}).get("name", obj.strip("[]").split("].[")[-1]),
                "type": object_metadata.get(obj, {}).get("type")
            }
            for obj in sorted_objects
        ]

        if sorted_objects:
            # Format as markdown list
            objects_list = "\n".join([f"• {obj}" for obj in sorted_objects])
            explanation = f"**Found {len(sorted_objects)} relevant database object(s):**\n\n{objects_list}"
        else:
            explanation = "No matching database objects found for your search. Try different keywords or check the value index."
        
        return GenerateSQLResponse(
            sql="",
            explanation=explanation,
            objects=objects_payload,
            query_type="search",
            context_text=f"Searched for: {query}"
        )
    except Exception as e:
        # Log detailed error for debugging but return generic message to user
        logging.error(f"Error searching data objects: {e}")
        return GenerateSQLResponse(
            sql="",
            explanation="An error occurred while searching database objects. Please try again or refine your search.",
            query_type="search",
            context_text=f"Search failed for: {query}"
        )


def _detect_turn_type_fast(query: str, planning_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Fast turn-type detection using keyword-based heuristics.
    
    Detects conversation turn types:
    - confirmation: User agrees to proceed ("yes", "ok", "sounds good")
    - correction: User changes specific details ("no, I meant...", "actually...")
    - pivot: User switches topics (low keyword overlap + signal words)
    - refinement: User adds details to existing goal (high overlap + signal words)
    
    Args:
        query: User's current message
        planning_context: Current planning state with "goal" field
    
    Returns:
        Dict with turn_type, confidence, reasoning, topic_similarity, or None if no clear pattern
    """
    query_lower = query.lower().strip()
    goal = planning_context.get("goal", "")
    
    # 1. CONFIRMATION SIGNALS (highest priority)
    confirmation_signals = [
        r'\b(yes|yeah|yep|yup|sure|ok|okay|sounds good|looks good|correct|right|perfect|go ahead|proceed)\b',
        r'^(y|k)\b',  # Short affirmatives
    ]
    for pattern in confirmation_signals:
        if re.search(pattern, query_lower):
            return {
                "turn_type": "confirmation",
                "confidence": 0.95,
                "reasoning": "User confirmed with affirmative language",
                "topic_similarity": 1.0
            }
    
    # 2. CORRECTION/REJECTION SIGNALS (2+ signals required, or explicit "no" with pending pivot)
    correction_signals = [
        r'\b(no|not|nope|incorrect|wrong|actually|instead|rather)\b',
        r'\b(i\s+\w+\s+meant|meant|should be|change)\b',  # "i meant", "i actually meant", etc.
        r'\b(different|other|another)\b',
    ]
    correction_count = sum(1 for pattern in correction_signals if re.search(pattern, query_lower))
    
    # Special case: explicit "no" when there's a pending pivot (rejection)
    # But check if user also included a new request after "no" (e.g., "No. let's find order tables")
    if planning_context.get("pending_pivot") and re.search(r'^\s*(no|nope|nah|not)\b', query_lower):
        # Check if there's a meaningful request after the rejection
        # Pattern: "no" followed by action words like "let's", "find", "show", "search", "look"
        has_followup_request = re.search(
            r'\b(no|nope|nah|not)[,.\s]+(let\'?s?|find|show|search|look|get|check|instead|but)\b',
            query_lower
        )
        if has_followup_request:
            # User rejected pivot BUT included a new request - treat as refinement
            return {
                "turn_type": "refinement",
                "confidence": 0.90,
                "reasoning": "User rejected pending pivot but included a follow-up request",
                "topic_similarity": 0.0
            }
        return {
            "turn_type": "correction",
            "confidence": 0.95,
            "reasoning": "User rejected pending pivot with explicit negative response",
            "topic_similarity": 0.0
        }
    
    if correction_count >= 2:
        return {
            "turn_type": "correction",
            "confidence": 0.85,
            "reasoning": f"Multiple correction signals detected ({correction_count})",
            "topic_similarity": 0.5
        }
    
    # 3. KEYWORD OVERLAP CALCULATION (for pivot vs refinement)
    topic_similarity = _compute_topic_similarity(query, goal)
    
    # 4. PIVOT DETECTION (low overlap + pivot signals)
    pivot_signals = [
        r'\b(instead|now|new|different|switch|change to)\b',
        r'\b(forget|ignore|nevermind|scratch that)\b',
    ]
    pivot_signal_count = sum(1 for pattern in pivot_signals if re.search(pattern, query_lower))
    
    if pivot_signal_count > 0 and topic_similarity < 0.3:
        return {
            "turn_type": "pivot",
            "confidence": 0.85,
            "reasoning": f"Pivot signals detected ({pivot_signal_count}) with low topic overlap ({topic_similarity:.2f})",
            "topic_similarity": topic_similarity
        }
    
    # 5. REFINEMENT DETECTION (refinement signals + higher overlap)
    refinement_signals = [
        r'\b(also|too|additionally|furthermore|plus|and)\b',
        r'\b(add|include|show|break down|filter|only|find|search|look)\b',
        r'\b(more|specifically|detailed|by)\b',
        r'\b(let\'?s?)\b',  # "let's", "lets" - indicates user wants to take action
    ]
    refinement_signal_count = sum(1 for pattern in refinement_signals if re.search(pattern, query_lower))
    
    if refinement_signal_count >= 2:
        return {
            "turn_type": "refinement",
            "confidence": 0.80,
            "reasoning": f"Multiple refinement signals detected ({refinement_signal_count})",
            "topic_similarity": topic_similarity
        }
    
    # No clear pattern detected
    return None


def _compute_topic_similarity(query: str, goal: str) -> float:
    """
    Compute topic similarity between two strings using Jaccard index.
    
    Extracts keywords (4+ character words) from both strings and calculates
    the Jaccard similarity coefficient: |intersection| / |union|.
    
    This is used by pivot detection to determine if the user is switching topics
    or refining the current goal.
    
    Args:
        query: Current user query string
        goal: Previous goal or context string
    
    Returns:
        float: Similarity score from 0.0 (no overlap) to 1.0 (identical)
    
    Examples:
        >>> _compute_topic_similarity("show sales data", "show sales data")
        1.0
        >>> _compute_topic_similarity("show sales", "show revenue")
        0.5
        >>> _compute_topic_similarity("show sales", "employee count")
        0.0
    """
    def extract_keywords(text: str) -> set:
        """Extract 4+ character words as keywords."""
        if not text:
            return set()
        words = re.findall(r'\b\w{4,}\b', text.lower())
        return set(words)
    
    query_keywords = extract_keywords(query)
    goal_keywords = extract_keywords(goal)
    
    # Handle edge cases: empty keyword sets
    if not query_keywords or not goal_keywords:
        return 0.0
    
    # Calculate Jaccard index: intersection / union
    intersection = query_keywords & goal_keywords
    union = query_keywords | goal_keywords
    
    return len(intersection) / len(union) if union else 0.0


def _classify_turn_type_llm(query: str, planning_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    LLM-based turn-type classification fallback for ambiguous cases.
    
    Uses an LLM to analyze conversation context and classify the user's turn type
    when fast pattern matching is insufficient. Includes conversation history for
    better context understanding.
    
    Args:
        query: Current user message
        planning_context: Planning state including goal, conversation_history, etc.
    
    Returns:
        Dict with fields:
            - turn_type: One of "refinement", "correction", "pivot", "confirmation", "clarification"
            - confidence: Float in [0.0, 1.0]
            - reasoning: Explanation of classification
            - topic_similarity: Float in [0.0, 1.0]
            - changed_requirements: List of requirement keys that changed (for corrections)
            - new_requirements: List of new requirements added (for refinements)
        
        On error, returns fallback REFINEMENT classification with confidence=0.5
    """
    import json
    
    try:
        llm_service = get_llm_service()
        
        # Build conversation history string
        history_text = ""
        for turn in planning_context.get("conversation_history", []):
            user_msg = turn.get("user", "")
            assistant_msg = turn.get("assistant", "")
            history_text += f"User: {user_msg}\nAssistant: {assistant_msg}\n"
        
        # Build classification prompt
        prompt = f"""You are analyzing a planning conversation to classify the user's latest message.

Current Goal: {planning_context.get("goal", "Not yet established")}

Conversation History:
{history_text if history_text else "No previous conversation"}

Latest User Message: {query}

Classify this message as one of the following turn types:
1. **refinement**: User is adding details or constraints to the existing goal (e.g., "also filter by region")
2. **correction**: User is changing a specific detail they previously stated (e.g., "no, I meant 2023, not 2022")
3. **pivot**: User is switching to a completely different topic (e.g., from sales to employees)
4. **confirmation**: User is agreeing to proceed (e.g., "yes", "ok", "sounds good")
5. **clarification**: User is answering a specific question the assistant asked

Respond with JSON:
{{
    "turn_type": "refinement|correction|pivot|confirmation|clarification",
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation of why this classification",
    "topic_similarity": 0.0-1.0,
    "changed_requirements": ["list", "of", "changed", "keys"],
    "new_requirements": ["list", "of", "new", "requirements"]
}}

IMPORTANT: Only return the JSON object, no additional text."""
        
        # Call LLM with temperature=0.3 for consistent but slightly flexible responses
        response = llm_service.chat(prompt, temperature=0.3)
        
        # Clean markdown code blocks if present
        response_clean = response.strip()
        if response_clean.startswith("```"):
            response_clean = re.sub(r'^```(?:json)?\s*\n', '', response_clean)
            response_clean = re.sub(r'\n```\s*$', '', response_clean)
        
        # Parse JSON
        result = json.loads(response_clean)
        
        # Validate required fields
        required_fields = ["turn_type", "confidence", "reasoning", "topic_similarity"]
        if not all(field in result for field in required_fields):
            raise ValueError(f"Missing required fields. Got: {list(result.keys())}")
        
        # Validate turn_type is valid enum value
        valid_turn_types = ["refinement", "correction", "pivot", "confirmation", "clarification"]
        if result["turn_type"] not in valid_turn_types:
            raise ValueError(f"Invalid turn_type: {result['turn_type']}")
        
        # Validate confidence and topic_similarity are in [0, 1]
        if not (0.0 <= result["confidence"] <= 1.0):
            raise ValueError(f"Confidence out of bounds: {result['confidence']}")
        if not (0.0 <= result["topic_similarity"] <= 1.0):
            raise ValueError(f"Topic similarity out of bounds: {result['topic_similarity']}")
        
        # Ensure optional fields exist with defaults
        result.setdefault("changed_requirements", [])
        result.setdefault("new_requirements", [])
        
        return result
        
    except Exception as e:
        # Log error and return fallback
        logging.error(f"LLM turn-type classification failed: {e}")
        return {
            "turn_type": "refinement",
            "confidence": 0.5,
            "reasoning": f"Fallback classification due to error: {str(e)}",
            "topic_similarity": 0.5,
            "changed_requirements": [],
            "new_requirements": []
        }


def _serialize_planning_context(planning_context: Dict[str, Any]) -> str:
    """
    Serialize planning context to JSON, converting sets to lists.
    
    Planning context uses sets for rejected_tables, confirmed_tables, and
    last_auto_checked to efficiently track table state. This function converts
    those sets to lists for JSON serialization.
    
    Args:
        planning_context: Planning state dictionary potentially containing set fields
    
    Returns:
        JSON string representation of planning context with sets converted to lists
    """
    import json
    
    # Create a shallow copy to avoid modifying the original
    serializable_context = {}
    
    for key, value in planning_context.items():
        # Convert sets to lists for JSON serialization
        if isinstance(value, set):
            serializable_context[key] = list(value)
        else:
            serializable_context[key] = value
    
    return json.dumps(serializable_context)


def planning_conversation(
    query: str, 
    planning_context: Optional[Dict[str, Any]] = None,
    user_selected_tables: Optional[List[str]] = None
) -> GenerateSQLResponse:
    """
    Intelligent planning mode with LLM-driven conversation and smart clarification detection.
    
    Strategy:
    - Ask questions only when information is ambiguous or missing
    - Auto-check tables with >90% confidence
    - Guide user efficiently toward complete planning
    
    Args:
        query: User's current message
        planning_context: Accumulated planning state from previous turns
            {
                "goal": str,  # User's stated analysis objective
                "selected_tables": List[str],  # User-checked tables
                "suggested_tables": List[Dict],  # AI-suggested tables
                "requirements": List[Dict],  # Filters, date ranges, business logic
                "conversation_history": List[Dict],  # Previous Q&A
                "turn_count": int
            }
    
    Returns:
        GenerateSQLResponse with:
            - explanation: AI's conversational response
            - objects: Suggested tables with auto_checked flag
            - context_text: Updated planning_context JSON
            - query_type: "plan"
    """
    import json
    
    try:
        llm_service = get_llm_service()
        vector_store = get_vector_store()
        
        # Initialize or load context
        if not planning_context:
            planning_context = {
                "goal": "",
                "selected_tables": [],
                "suggested_tables": [],
                "requirements": [],
                "conversation_history": [],
                "turn_count": 0,
                # NEW: Intent evolution tracking fields
                "goal_history": [],  # List of previous goals (for pivot detection)
                "rejected_tables": set(),  # Tables user explicitly rejected
                "confirmed_tables": set(),  # Tables user explicitly confirmed
                "adjustments": [],  # List of corrections/refinements made
                "last_auto_checked": set()  # Tables that were auto-checked in previous turn
            }
        else:
            # Ensure new fields exist for backward compatibility
            planning_context.setdefault("goal_history", [])
            planning_context.setdefault("adjustments", [])
            
            # Convert list fields to sets for efficient lookups (backward compatibility)
            for field in ["rejected_tables", "confirmed_tables", "last_auto_checked"]:
                if field not in planning_context:
                    planning_context[field] = set()
                elif isinstance(planning_context[field], list):
                    planning_context[field] = set(planning_context[field])
        
        # Serialize context for JSON (convert sets to lists) - do this early for all paths
        context_for_prompt = {}
        for key, value in planning_context.items():
            if isinstance(value, set):
                context_for_prompt[key] = list(value)
            else:
                context_for_prompt[key] = value
        
        # Step 0: Detect table selection changes (user-only action without text input)
        query_is_empty = not query or query.strip() == ""
        # User submitted the form (user_selected_tables is not None) without typing anything
        has_table_selection_submission = user_selected_tables is not None
        
        # If user submitted table selection form without typing anything, treat as TABLE_SELECTION turn type
        if query_is_empty and has_table_selection_submission:
            # Update selected_tables in context
            previous_selected = set(planning_context.get("selected_tables", []))
            new_selected = set(user_selected_tables or [])  # Type safety: handle None case
            
            # Track confirmed and rejected tables
            newly_added = new_selected - previous_selected
            newly_removed = previous_selected - new_selected
            
            if newly_added:
                planning_context["confirmed_tables"].update(newly_added)
            if newly_removed:
                planning_context["rejected_tables"].update(newly_removed)
            
            # Update context
            planning_context["selected_tables"] = list(new_selected)
            
            # Generate a synthetic query for processing
            if newly_added and newly_removed:
                query = f"I've updated my table selection (added {len(newly_added)}, removed {len(newly_removed)} tables)."
            elif newly_added:
                added_names = ", ".join([t.split('.')[-1] for t in list(newly_added)[:3]])
                if len(newly_added) > 3:
                    added_names += f" and {len(newly_added) - 3} more"
                query = f"I've selected {added_names}."
            elif newly_removed:
                removed_names = ", ".join([t.split('.')[-1] for t in list(newly_removed)[:3]])
                if len(newly_removed) > 3:
                    removed_names += f" and {len(newly_removed) - 3} more"
                query = f"I've deselected {removed_names}."
            else:
                query = "I've confirmed my table selection."
            
            # Override turn type
            turn_type = "table_selection"
            turn_classification = {
                "turn_type": "table_selection",
                "confidence": 1.0,
                "topic_similarity": 1.0,
                "reasoning": "User selected/deselected tables without text input"
            }
        else:
            # Normal turn-type classification
            turn_classification = None
            turn_type = None
        
        # Step 1: Turn-type classification and intent analysis (skip if already classified)
        if not turn_classification:
            # Classify turn type using fast detection first, fallback to LLM
            turn_classification = _detect_turn_type_fast(query, planning_context)
            if not turn_classification:
                turn_classification = _classify_turn_type_llm(query, planning_context)
            
            turn_type = turn_classification["turn_type"]
        
        # Handle pivot with confirmation
        # BUT: Skip pivot detection on the FIRST turn of a new conversation
        # (when there's no existing goal, it's the primary request, not a topic change)
        is_first_turn = planning_context.get("turn_count", 0) == 0 and not planning_context.get("goal")
        
        if turn_type == "pivot" and not is_first_turn:
            if not planning_context.get("pending_pivot"):
                # First pivot detection - ask for confirmation
                planning_context["pending_pivot"] = {
                    "new_goal": query,
                    "previous_goal": planning_context.get("goal", "")
                }
                
                response_text = f"""It looks like you want to switch from "{planning_context.get('goal', 'your current analysis')}" to "{query}". 

Would you like to start fresh with this new topic? (This will clear your current table selections and requirements)"""
                
                return GenerateSQLResponse(
                    sql="",
                    explanation=response_text,
                    objects=[],
                    query_type="plan",
                    context_text=_serialize_planning_context(planning_context)
                )
        elif turn_type == "pivot" and is_first_turn:
            # First turn - treat as refinement (primary request), not a pivot
            turn_type = "refinement"
        
        # Handle pending pivot confirmation
        if planning_context.get("pending_pivot") and turn_type == "confirmation":
            # User confirmed the pivot - switch topics
            old_goal = planning_context["goal"]
            new_goal = planning_context["pending_pivot"]["new_goal"]
            
            # Archive old goal
            if old_goal:
                planning_context["goal_history"].append(old_goal)
            
            # Reset for new topic
            planning_context["goal"] = ""
            planning_context["selected_tables"] = []
            planning_context["suggested_tables"] = []
            planning_context.setdefault("requirements", [])
            planning_context["rejected_tables"] = set()
            planning_context["confirmed_tables"] = set()
            planning_context["last_auto_checked"] = set()
            
            # Clear pending pivot
            del planning_context["pending_pivot"]
            
            # Reprocess with new query
            query = new_goal
            turn_type = "refinement"  # Treat as fresh start
        
        # Handle pending pivot rejection (user said "no")
        if planning_context.get("pending_pivot") and turn_type == "correction":
            # User rejected the pivot - keep original topic
            previous_goal = planning_context["pending_pivot"]["previous_goal"]
            
            # Clear pending pivot
            del planning_context["pending_pivot"]
            
            # Acknowledge rejection and continue with original topic
            response_text = f"Understood! Let's continue with your current topic: \"{previous_goal}\". How would you like to proceed?"
            
            return GenerateSQLResponse(
                sql="",
                explanation=response_text,
                objects=[],
                query_type="plan",
                context_text=_serialize_planning_context(planning_context)
            )
        
        # Handle pending pivot rejection WITH a new request (e.g., "No. let's find order tables")
        # When turn_type is "refinement" but there's still a pending_pivot, user rejected and provided new direction
        if planning_context.get("pending_pivot") and turn_type == "refinement":
            # User rejected the pivot but provided a follow-up request
            previous_goal = planning_context["pending_pivot"]["previous_goal"]
            
            # Clear pending pivot
            del planning_context["pending_pivot"]
            
            # Extract the actual request by removing the "no" prefix
            # Pattern: strip "no", "nope", etc. and any following punctuation/whitespace
            cleaned_query = re.sub(r'^\s*(no|nope|nah|not)[,.\s]+', '', query, flags=re.IGNORECASE).strip()
            
            # If we have a meaningful cleaned query, use it; otherwise use original
            if cleaned_query and len(cleaned_query) > 3:
                query = cleaned_query
            
            # If previous goal was empty (first turn failed), don't reference it
            if previous_goal:
                planning_context["goal_history"].append(previous_goal)
            
            # Continue with the refinement flow - don't return early
        
        # Handle TABLE_SELECTION (user modified table selection without text input)
        if turn_type == "table_selection":
            # Skip intent analysis - directly prepare response about table selection
            selected_count = len(planning_context.get("selected_tables", []))
            
            if selected_count == 0:
                response_text = "I notice you've deselected all tables. Please select at least one table to continue, or describe what data you're looking for."
            elif selected_count == 1:
                table_name = planning_context["selected_tables"][0].split('.')[-1]
                response_text = f"Got it! You've selected the **{table_name}** table. What would you like to analyze from this table?"
            else:
                response_text = f"Perfect! You've selected {selected_count} tables. What analysis would you like to perform with these tables?"
            
            # Add turn to conversation history
            planning_context["conversation_history"].append({
                "role": "user",
                "content": query,  # synthetic query describing the action
                "turn": planning_context.get("turn_count", 0)
            })
            planning_context["conversation_history"].append({
                "role": "assistant",
                "content": response_text,
                "turn": planning_context.get("turn_count", 0)
            })
            planning_context["turn_count"] = planning_context.get("turn_count", 0) + 1
            
            return GenerateSQLResponse(
                sql="",
                explanation=response_text,
                objects=[],
                query_type="plan",
                context_text=_serialize_planning_context(planning_context)
            )
        
        # Run intent analysis
        intent_prompt = f"""You are a data analysis planning assistant. Analyze the user's message:

Previous Context: {json.dumps(context_for_prompt, indent=2)}
User Message: {query}

Determine:
1. Is the user's goal clear? (yes/no)
2. Are there ambiguities that MUST be resolved before finding tables? (list them)
3. Is there enough info to suggest database tables? (yes/no)
4. What critical questions need answers? (only if truly necessary)

Respond in JSON:
{{
    "goal_clear": true/false,
    "goal_statement": "Clear 1-sentence goal",
    "critical_ambiguities": ["ambiguity1", "ambiguity2"],
    "ready_for_search": true/false,
    "required_questions": [
        {{"question": "...", "reason": "why this must be asked"}}
    ],
    "requirements_extracted": [
        {{"type": "time_period|filter|metric|grouping", "value": "..."}}
    ]
}}

IMPORTANT: Only ask questions if information is genuinely ambiguous or missing critical details.
If the user said "sales analysis", assume they want revenue unless they specify otherwise.
Be helpful, not interrogative."""

        try:
            intent_response = llm_service.chat(intent_prompt)
            # Clean up response - remove markdown code blocks and extra prefixes
            intent_response_clean = intent_response.strip()
            
            # Remove markdown code blocks
            if intent_response_clean.startswith("```"):
                intent_response_clean = re.sub(r'^```(?:json)?\s*\n', '', intent_response_clean)
                intent_response_clean = re.sub(r'\n```\s*$', '', intent_response_clean)
            
            # Remove standalone "json" prefix if present (LLM sometimes adds this)
            if intent_response_clean.startswith("json"):
                intent_response_clean = intent_response_clean[4:].strip()
            
            intent_data = json.loads(intent_response_clean)
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse intent JSON: {e}. Response: {intent_response}")
            # Fallback: assume basic intent
            intent_data = {
                "goal_clear": True,
                "goal_statement": query,
                "critical_ambiguities": [],
                "ready_for_search": True,
                "required_questions": [],
                "requirements_extracted": []
            }
        
        # Step 2: Update planning context based on turn type
        old_goal = planning_context.get("goal", "")
        
        if intent_data.get("goal_statement"):
            new_goal = intent_data["goal_statement"]
            
            # Track goal evolution for corrections and refinements
            if turn_type in ["correction", "refinement"] and old_goal and new_goal != old_goal:
                planning_context["goal_history"].append(old_goal)
                
                # Record adjustment
                planning_context["adjustments"].append({
                    "type": turn_type,
                    "from": old_goal,
                    "to": new_goal,
                    "turn": planning_context.get("turn_count", 0)
                })
            
            planning_context["goal"] = new_goal
        elif not old_goal and query:
            # Fallback: If no goal_statement from LLM and no existing goal, use the query itself
            # This ensures we always have SOME goal set for context preservation
            planning_context["goal"] = query
        
        # Ensure requirements field exists
        planning_context.setdefault("requirements", [])
        
        for req in intent_data.get("requirements_extracted", []):
            planning_context["requirements"].append(req)
        
        planning_context["conversation_history"].append({
            "turn": planning_context.get("turn_count", 0),
            "user": query,
            "intent": intent_data,
            "turn_type": turn_type
        })
        planning_context["turn_count"] = planning_context.get("turn_count", 0) + 1
        
        # Step 3: Perform semantic search if ready
        suggested_objects = []
        auto_checked_tables = []
        
        # Always search on the first turn (turn_count == 1) since the user came to plan mode
        # with a specific question. Also search when LLM says ready, or when query explicitly
        # asks to find/search for tables.
        is_first_turn = planning_context.get("turn_count", 0) == 1
        llm_says_ready = intent_data.get("ready_for_search", False)
        explicitly_searching = bool(re.search(
            r'\b(find|search|look\s+for|show|list|discover|locate|identify|where)\b.*\b(table|view|schema|object|column|stored|data)\b',
            query, re.IGNORECASE
        ))
        
        should_search = llm_says_ready or is_first_turn or explicitly_searching
        
        if should_search:
            search_query = planning_context.get("goal", "") + " " + query
            search_result = search_data_objects(search_query)
            suggested_objects = search_result.objects or []
            
            # Step 4: Determine which tables to auto-check (>90% confidence)
            if suggested_objects and len(suggested_objects) > 0:
                # Build table descriptions for confidence prompt
                table_list = [
                    f"[{obj.schema_name}].[{obj.name}] ({obj.type or 'Table'})"
                    for obj in suggested_objects
                ]
                
                confidence_prompt = f"""Given this user goal: {planning_context.get("goal", query)}

And these suggested tables: {', '.join(table_list)}

Which tables are ESSENTIAL (>90% confidence needed) for this analysis?

Respond with JSON:
{{
    "essential_tables": ["[schema].[table]", ...],
    "reasoning": {{"[schema].[table]": "why essential"}}
}}

Be conservative - only mark as essential if absolutely required for the stated goal.
Maximum 3 essential tables."""

                try:
                    confidence_response = llm_service.chat(confidence_prompt)
                    # Clean up response
                    confidence_response_clean = confidence_response.strip()
                    
                    # Remove markdown code blocks
                    if confidence_response_clean.startswith("```"):
                        confidence_response_clean = re.sub(r'^```(?:json)?\s*\n', '', confidence_response_clean)
                        confidence_response_clean = re.sub(r'\n```\s*$', '', confidence_response_clean)
                    
                    # Remove standalone "json" prefix if present
                    if confidence_response_clean.startswith("json"):
                        confidence_response_clean = confidence_response_clean[4:].strip()
                    
                    confidence_data = json.loads(confidence_response_clean)
                    auto_checked_tables = confidence_data.get("essential_tables", [])
                except (json.JSONDecodeError, Exception) as e:
                    logging.error(f"Failed to parse confidence JSON: {e}. Response: {confidence_response if 'confidence_response' in locals() else 'N/A'}")
                    # Fallback: auto-check top 1 table
                    if suggested_objects:
                        auto_checked_tables = [f"[{suggested_objects[0].schema_name}].[{suggested_objects[0].name}]"]
                
                # Normalize auto-checked table names and mark objects
                auto_checked_normalized = []
                for table_name in auto_checked_tables:
                    normalized = table_name.strip().replace('[', '').replace(']', '')
                    auto_checked_normalized.append(normalized)
                
                # Mark auto-checked objects
                for obj in suggested_objects:
                    obj_key = f"{obj.schema_name}.{obj.name}"
                    if obj_key in auto_checked_normalized or f"[{obj.schema_name}].[{obj.name}]" in auto_checked_tables:
                        obj.auto_checked = True
                
                # Add to selected tables in context
                planning_context["selected_tables"] = list(set(
                    planning_context.get("selected_tables", []) + auto_checked_tables
                ))
        
        # Step 5: Generate conversational response
        response_prompt = f"""Generate a helpful response for this planning conversation.

Context: {json.dumps(context_for_prompt, indent=2)}
Intent Analysis: {json.dumps(intent_data, indent=2)}
Number of Suggested Tables: {len(suggested_objects)}
Auto-Checked Tables: {json.dumps(auto_checked_tables, indent=2)}

User's Message: {query}

Guidelines:
1. **If user asks about current state** (e.g., "which tables are selected?", "what did we discuss?", "summarize our conversation"):
   - Answer directly using information from Context (goal, selected_tables, requirements, conversation_history)
   - List selected tables from "selected_tables" field
   - Summarize goal from "goal" field
   - Reference requirements from "requirements" field
   
2. Acknowledge their input warmly

3. ONLY ask questions from intent_data["required_questions"] (if any exist)

4. If tables found, say: "Based on your question about [topic], please review the following tables and select the ones you want to use in the analysis:"

5. If tables were auto-checked, mention: "I've pre-selected tables that are essential for your analysis, but you can adjust the selection."

6. Keep it conversational and helpful, not robotic

7. If planning seems complete (goal clear, tables selected, requirements noted), say: "Your planning is complete! Switch to 'Generate SQL' or another mode when you're ready to create the code."

Format as markdown. Be concise but friendly. Maximum 4 sentences (unless answering state questions, which may need more detail)."""

        ai_response = llm_service.chat(response_prompt)
        
        return GenerateSQLResponse(
            sql="",
            explanation=ai_response,
            objects=suggested_objects,
            query_type="plan",
            context_text=_serialize_planning_context(planning_context)
        )
        
    except Exception as e:
        logging.error(f"Error in planning conversation: {e}")
        return GenerateSQLResponse(
            sql="",
            explanation=f"I encountered an issue during planning. Let's try again: {str(e)}",
            query_type="plan",
            context_text=_serialize_planning_context(planning_context) if planning_context else "{}"
        )


def generate_planning_summary(planning_context: Dict[str, Any]) -> str:
    """
    Generate a structured markdown summary from planning context.
    
    Args:
        planning_context: Accumulated planning state
    
    Returns:
        Formatted summary for display and code generation
    """
    import json
    
    try:
        llm_service = get_llm_service()
        
        # Serialize context for JSON (convert sets to lists)
        context_for_prompt = {}
        for key, value in planning_context.items():
            if isinstance(value, set):
                context_for_prompt[key] = list(value)
            else:
                context_for_prompt[key] = value
        
        # Extract user's original request from conversation history
        user_messages = [turn.get("user", "") for turn in planning_context.get("conversation_history", [])]
        original_request = user_messages[0] if user_messages else planning_context.get("goal", "")
        
        prompt = f"""Create a concise summary from this planning conversation for code generation.

**User's Primary Request:** {original_request}

**Full Planning Context:** {json.dumps(context_for_prompt, indent=2)}

CRITICAL: The summary must focus on WHAT THE USER WANTS TO ACHIEVE (their primary analysis request), NOT just list tables.

Format as markdown:
## Primary Request
[Restate the user's original analysis question/goal in clear terms - this is the MAIN focus]

## Data Sources
[List only the selected tables - keep this section minimal]
• [schema].[table]
• ...

## Additional Requirements
[ONLY if user specified filters, date ranges, grouping, metrics, etc.]
• [requirement]

Guidelines:
- The "Primary Request" section is THE MOST IMPORTANT - it should clearly state what the user wants to analyze or find out
- Selected tables are SUPPORTING information, not the main focus
- Keep total summary under 150 words
- This summary will be sent directly to code generation, so it must clearly communicate the user's intent"""

        summary = llm_service.chat(prompt)
        return summary
        
    except Exception as e:
        logging.error(f"Error generating planning summary: {e}")
        # Fallback: simple summary focusing on user's primary request
        user_messages = [turn.get("user", "") for turn in planning_context.get("conversation_history", [])]
        original_request = user_messages[0] if user_messages else planning_context.get("goal", "Analysis goal not specified")
        
        tables = planning_context.get("selected_tables", [])
        requirements = planning_context.get("requirements", [])
        
        summary = f"## Primary Request\n{original_request}\n\n"
        if tables:
            summary += f"## Data Sources\n"
            for table in tables:
                summary += f"• {table}\n"
            summary += "\n"
        if requirements:
            summary += "## Additional Requirements\n"
            for req in requirements[:5]:  # Limit to 5
                req_value = req.get("value", str(req))
                summary += f"• {req_value}\n"
        
        return summary


def generate_sql_for_request(request: GenerateSQLRequest, previous_sql: Optional[str] = None, query_history: Optional[str] = None) -> Generator[Union[AgentStatus, Dict[str, Any]], None, None]:
    # Build context-aware query by combining with conversation history at the very start
    # This ensures ALL branches (plan, search, database) maintain context from previous queries
    combined_query = request.query
    if query_history:
        combined_query = f"{query_history}. {request.query}"
        logging.info(f"[Context] Combined query with history: {combined_query}")

    normalized_db_objects = _normalize_database_objects(request.database_objects)
    existing_code = request.existing_code or request.previousSQL
    editor_mode = "debug" if request.error_message else ("optimize" if existing_code else "fresh")
    is_editor_mode = editor_mode != "fresh"
    
    # Check for plan mode first - conversational planning
    if request.queryMode == "plan":
        yield AgentStatus(step_id=1, message="Thinking about your data needs...")
        result = planning_conversation(
            combined_query, 
            request.planning_context,
            user_selected_tables=request.user_selected_tables
        )
        yield {"type": "result", "payload": result}
        yield {"type": "done"}
        return
    
    # Check for search mode - user explicitly chose to search objects
    if request.queryMode == "search":
        yield AgentStatus(step_id=1, message="Searching database objects...")
        result = search_data_objects(combined_query)
        yield {"type": "result", "payload": result}
        yield {"type": "done"}
        return
    
    yield AgentStatus(step_id=1, message="Initializing agent and loading settings...")

    
    # Load settings for dynamic configuration
    vector_store = get_vector_store()
    try:
        # Get fresh LLM service instance to ensure latest settings
        llm_service = get_llm_service()
        
        # Load database metadata from skills data sources instead of settings
        from app.services.skills_service import get_skills_service
        skills_service = get_skills_service()
        data_sources = skills_service.load_data_sources_index() or []
        primary_source = skills_service.load_primary_data_source()

        if primary_source:
            friendly_name = primary_source.name
            db_description = primary_source.description
            db_keywords = primary_source.keywords
        elif data_sources:
            friendly_name = data_sources[0].name
            db_description = data_sources[0].description
            db_keywords = data_sources[0].keywords
        else:
            # Fallback to defaults if skills not available
            friendly_name = "Database"
            db_description = "Primary database"
            db_keywords = []

        if primary_source and not any(ds.name == primary_source.name for ds in data_sources):
            data_sources = [primary_source] + data_sources
    except Exception as e:
        print(f"Failed to load database metadata, using defaults: {e}")
        friendly_name = "Database"
        db_description = "Primary database"
        db_keywords = []
        data_sources = []
        primary_source = None
    
    # combined_query was already built at the start of the function with conversation history
    
    # Stage 1: Intent Classification & Query Analysis
    yield AgentStatus(step_id=2, message="Classifying query intent...")
    
    # If forceGeneral flag is set (user explicitly chose "General Answer"), skip classification
    if request.forceGeneral:
        yield AgentStatus(step_id=3, message="Processing general query...")
        result = _handle_general_query(combined_query, llm_service)
        yield {"type": "result", "payload": result}
        yield {"type": "done"}
        return

    # 3-way LLM intent classification: data_query / system_metadata / off_topic
    # Use combined query so classifier has full conversation context
    classification = classify_query_intent(
        combined_query, llm_service,
        db_name=friendly_name,
        db_description=db_description,
        db_keywords=db_keywords,
        data_sources=data_sources,
    )
    if isinstance(classification, dict):
        query_intent = classification.get("intent", "data_query")
        related_sources = classification.get("related_sources", [])
        related_source_guids = classification.get("related_source_guids", [])
    else:
        query_intent = (classification or "").strip().lower()
        related_sources = []
        related_source_guids = []

    source_by_guid = {
        getattr(ds, "source_id", None): ds
        for ds in (data_sources or [])
        if getattr(ds, "source_id", None)
    }

    if len(related_source_guids) > 1:
        options = []
        for guid in related_source_guids:
            source = source_by_guid.get(guid)
            name = source.name if source else "Unknown"
            options.append(f"- {name} (guid: {guid})")

        explanation = (
            "Multiple data sources match your request. Please choose one source ID to proceed:\n"
            + "\n".join(options)
            + "\n\nReply with the GUID of the data source you want to use."
        )
        result = GenerateSQLResponse(
            sql="",
            explanation=explanation,
            query_type="general"
        )
        yield {"type": "result", "payload": result}
        yield {"type": "done"}
        return

    selected_source_id = None
    if related_source_guids:
        selected_source_id = related_source_guids[0]
    else:
        selected_source_id = getattr(primary_source, "source_id", None) if primary_source else None
        if not selected_source_id and data_sources:
            selected_source_id = getattr(data_sources[0], "source_id", None)
    
    status_message = f"Intent classified as: {query_intent}"
    if related_sources:
        status_message += f" (sources: {', '.join(related_sources)})"
    if selected_source_id:
        status_message += f" (source_id: {selected_source_id})"
    yield AgentStatus(step_id=3, message=status_message)

    # --- Off-Topic Branch ---
    if query_intent == "off_topic":
        yield AgentStatus(step_id=4, message="Off-topic query detected. Generating general response...")
        result = _handle_general_query(combined_query, llm_service)
        yield {"type": "result", "payload": result}
        yield {"type": "done"}
        return

    # --- System Metadata Branch ---
    if query_intent == "system_metadata":
        yield AgentStatus(step_id=4, message="System metadata query detected. Accessing SQL Server catalogs...")
        selected_source = source_by_guid.get(selected_source_id) if selected_source_id else None

        if selected_source:
            database_info = f"Database: {selected_source.name}\nDescription: {selected_source.description}"
        else:
            database_info = f"Database: {friendly_name}\nDescription: {db_description}"
        system_prompt = build_system_catalog_prompt(combined_query, database_info=database_info)

        max_system_attempts = 2
        last_error = ""
        for attempt in range(max_system_attempts):
            yield AgentStatus(step_id=10 + attempt, message=f"Generating system catalog SQL (Attempt {attempt + 1}/{max_system_attempts})...")

            retry_prompt = system_prompt
            if attempt > 0 and last_error:
                retry_prompt += f"\n\n### PREVIOUS ATTEMPT FAILED\nError: {last_error}\nPlease fix the query and try again."

            sql = llm_service.generate_sql_with_context(combined_query, retry_prompt)
            is_valid, error_msg, _ = validate_sql_with_db(sql, source_id=selected_source_id)

            if is_valid:
                result = GenerateSQLResponse(
                    sql=sql,
                    explanation="System metadata query generated from SQL Server catalog views.",
                    query_type="database",
                    context_text=retry_prompt,
                    discovery_branch="system_catalog",
                    source_id=selected_source_id
                )
                yield {"type": "result", "payload": result}
                yield {"type": "done"}
                return

            last_error = error_msg
            logging.warning(f"System catalog SQL attempt {attempt + 1} failed: {error_msg}")

        result = GenerateSQLResponse(
            sql="",
            explanation=f"Failed to generate a valid system metadata query after {max_system_attempts} attempts. Last error: {last_error}",
            query_type="database",
            context_text=system_prompt,
            discovery_branch="system_catalog",
            source_id=selected_source_id
        )
        yield {"type": "result", "payload": result}
        yield {"type": "done"}
        return

    # --- Data Query Branch (continues to Stage 2: Discovery) ---
    # Built-in generator strangler: plan/search/system_catalog stay above this point.
    from app.core.config import settings as _app_settings
    if getattr(_app_settings, "BUILTIN_SQL_GENERATOR", True) and request.queryMode == "generate":
        from app.core.orchestrator.builtin_sql_generator import generate_sql_builtin
        from app.services.stores.bundle import build_source_stores
        from app.services.source_resolver import resolve_or_primary

        builtin_source = request.source_id or selected_source_id
        builtin_source = resolve_or_primary(builtin_source)
        stores = build_source_stores(builtin_source)
        for event in generate_sql_builtin(request, stores):
            yield event
        return

    # Use the combined query (with conversation history) for discovery
    discovery_query = combined_query

    allowed_tables = _get_allowed_table_set(vector_store, selected_source_id)

    db_object_tables, db_object_unresolved = _resolve_database_objects_to_tables(
        normalized_db_objects,
        vector_store,
        selected_source_id,
        allowed_tables=allowed_tables
    )
    
    # Extract entities and score complexity for database queries (using context-aware query)
    entities, date_ranges = extract_entities(discovery_query)
    query_complexity = score_query_complexity(discovery_query)
    
    yield AgentStatus(step_id=4, message=f"Analyzed query. Complexity: {query_complexity}. Entities: {', '.join(entities) if entities else 'None'}")

    # Stage 2: Discovery & Context Synthesis (Multi-Source Retrieval)
    yield AgentStatus(step_id=5, message="Discovering relevant tables and schemas...")
    
    table_override = [t for t in (request.table_override or []) if t]
    use_table_override = len(table_override) > 0

    # Initialize discovery tracking variables (used by all branches)
    discovery_branch = None
    kb_assessment = None

    if use_table_override:
        yield AgentStatus(step_id=4, message="Locking context to user-selected tables...")
        table_override = _filter_table_names_by_source(table_override, allowed_tables)
        context = hydrate_override_context(table_override, source_id=selected_source_id)
        if not context.relevant_tables:
            result = GenerateSQLResponse(
                sql="",
                explanation="No matching schemas were found for the selected objects. Please verify the table names and try again.",
                query_type="database",
                context_text="Selected tables not found",
                source_id=selected_source_id
            )
            yield {"type": "result", "payload": result}
            yield {"type": "done"}
            return
    elif request.context:
        # If context is explicitly provided, use it
        context = request.context
    else:
        # ====================================================================
        # KNOWLEDGE-BASE-FIRST DISCOVERY (Sequential + Conditional)
        # ====================================================================
        
        # STEP 1: Knowledge Base Priority Search
        yield AgentStatus(step_id=5, message="Searching knowledge base for similar queries...")
        kb_results = vector_store.search_fewshots_with_threshold(
            discovery_query, 
            top_k=3, 
            knowledge_type="sql_query",
            score_threshold=0.5  # L2 distance threshold
        )
        
        if kb_results:
            # ============================================================
            # BRANCH 1.1: Knowledge Base Hit - LLM Evaluation
            # ============================================================
            yield AgentStatus(step_id=6, message="Evaluating knowledge base examples with AI...")
            logging.info(f"[KB-First] Found {len(kb_results)} KB results. Evaluating relevance...")
            
            kb_assessment = llm_service.evaluate_example_relevance(discovery_query, kb_results)
            
            is_sufficient = kb_assessment.get("is_sufficient", False)
            confidence = kb_assessment.get("confidence", 0.0)
            
            if is_sufficient and confidence >= 0.7:
                # ========================================================
                # BRANCH 1.1.1: High Confidence - Direct to Prompt
                # ========================================================
                discovery_branch = "kb_direct"
                logging.info(f"[KB-First] HIGH CONFIDENCE ({confidence}). Using KB example directly.")
                yield AgentStatus(step_id=6, message=f"Found highly relevant example (confidence: {confidence:.0%}). Using as reference...")
                
                # Extract tables from the best KB example's SQL
                best_example = kb_results[0]
                best_entity = best_example.get('entity', best_example)
                best_sql = best_entity.get('sql_query', '')
                
                # Get table names from the KB SQL
                kb_sql_tables = llm_service.extract_tables_from_sql([best_sql]) if best_sql else []
                
                # Format similar queries from KB results for context
                similar_queries = []
                for r in kb_results:
                    entity = r.get('entity', r)
                    similar_queries.append({
                        "question": entity.get("question", ""),
                        "sql": entity.get("sql_query", "")
                    })
                
                # Hydrate context using only the KB-referenced tables
                if kb_sql_tables:
                    kb_sql_tables = _filter_table_names_by_source(kb_sql_tables, allowed_tables)
                    context = _hydrate_discovery_context_scoped(
                        kb_sql_tables,
                        similar_queries,
                        selected_source_id
                    )
                else:
                    # Fallback: use similar queries without specific table hydration
                    context = DiscoveryContext(
                        relevant_tables=[],
                        similar_queries=similar_queries
                    )
                
                logging.info(f"[KB-First] Branch 1.1.1 complete. Tables: {kb_sql_tables}")
                
            else:
                # ========================================================
                # BRANCH 1.1.2: Gap Filling - Targeted Supplementary Search
                # ========================================================
                discovery_branch = "kb_gap_fill"
                missing_entities = kb_assessment.get("missing_entities", [])
                missing_tables = kb_assessment.get("missing_tables", [])
                search_terms = kb_assessment.get("suggested_search_terms", [])
                
                logging.info(
                    f"[KB-First] INSUFFICIENT ({confidence}). "
                    f"Missing entities: {missing_entities}, Missing tables: {missing_tables}, "
                    f"Search terms: {search_terms}"
                )
                yield AgentStatus(step_id=6, message="Knowledge base example needs supplementation. Searching for missing context...")
                
                # Extract tables from KB examples as a starting point
                kb_sql_list = []
                for r in kb_results:
                    entity = r.get('entity', r)
                    sql = entity.get('sql_query', '')
                    if sql:
                        kb_sql_list.append(sql)
                
                kb_tables = llm_service.extract_tables_from_sql(kb_sql_list) if kb_sql_list else []
                
                # Build search keywords from KB tables + LLM gap analysis
                gap_keywords = list(set(missing_entities + missing_tables + search_terms))
                
                # Targeted supplementary search using gap keywords
                supplementary_tables = []
                supplementary_value_tables = []
                
                for keyword in gap_keywords[:5]:  # Limit to 5 gap searches
                    # Schema index search
                    schema_hits = _search_schemas_scoped(vector_store, keyword, top_k=3, source_id=selected_source_id)
                    for s in schema_hits:
                        full_name = f"{s.schema_name}.{s.table_name}"
                        if full_name not in supplementary_tables:
                            supplementary_tables.append(full_name)
                    
                    # Value index search
                    value_hits = _search_values_scoped(vector_store, keyword, top_k=3, allowed_tables=allowed_tables)
                    for v in value_hits:
                        entity = v.get('entity', v)
                        table_name = entity.get('table_name', '')
                        schema_name = entity.get('schema_name', 'dbo')
                        if table_name:
                            full_name = f"{schema_name}.{table_name}"
                            if full_name not in supplementary_value_tables:
                                supplementary_value_tables.append(full_name)
                
                # Expand supplementary value tables with FK relationships
                if supplementary_value_tables:
                    supplementary_value_tables = expand_value_tables_with_relationships(supplementary_value_tables)
                    supplementary_value_tables = _filter_table_names_by_source(supplementary_value_tables, allowed_tables)

                # Combine KB tables with supplementary discoveries
                all_tables = list(set(kb_tables + supplementary_tables + supplementary_value_tables))
                all_tables = _filter_table_names_by_source(all_tables, allowed_tables)
                
                logging.info(
                    f"[KB-First] Gap fill found {len(supplementary_tables)} schema + "
                    f"{len(supplementary_value_tables)} value tables. "
                    f"Combined: {len(all_tables)} tables."
                )
                
                # Format similar queries from KB results
                similar_queries = []
                for r in kb_results:
                    entity = r.get('entity', r)
                    similar_queries.append({
                        "question": entity.get("question", ""),
                        "sql": entity.get("sql_query", "")
                    })
                
                # Hydrate context
                context = _hydrate_discovery_context_scoped(
                    all_tables,
                    similar_queries,
                    selected_source_id
                )
                
                yield AgentStatus(step_id=7, message=f"Supplementary discovery complete. Found {len(context.relevant_tables)} tables.")
        
        else:
            # ============================================================
            # BRANCH 1.2: No KB Hit - Dual-Prong Strategy (Original Flow)
            # ============================================================
            discovery_branch = "dual_prong"
            logging.info("[KB-First] No KB results passed threshold. Falling back to dual-prong discovery.")
            
            # 1. NER & Value Discovery (Focused)
            yield AgentStatus(step_id=5, message="No knowledge base match. Identifying filter values and entities...")
            filter_values = llm_service.extract_filter_values(discovery_query)
            value_tables = []
            if filter_values:
                logging.info(f"Discovery: Extracted filter values: {filter_values}")
                for val in filter_values:
                    v_res = _search_values_scoped(vector_store, val, top_k=3, allowed_tables=allowed_tables)
                    value_tables.extend([f"{r.get('schema_name', 'dbo')}.{r.get('table_name')}" for r in v_res if r.get('table_name')])
            else:
                value_results = _search_values_scoped(vector_store, discovery_query, top_k=5, allowed_tables=allowed_tables)
                value_tables = [f"{r.get('schema_name', 'dbo')}.{r.get('table_name')}" for r in value_results if r.get('table_name')]
                
            # 1b. Expand value tables with FK relationship tracing
            if value_tables:
                original_count = len(value_tables)
                value_tables = expand_value_tables_with_relationships(value_tables)
                value_tables = _filter_table_names_by_source(value_tables, allowed_tables)
                if len(value_tables) > original_count:
                    logging.info(
                        f"Discovery: Relationship tracing expanded value tables "
                        f"from {original_count} to {len(value_tables)}"
                    )

            # 2. Few-Shot Discovery (broader search, no threshold)
            yield AgentStatus(step_id=6, message="Searching knowledge base for similar queries...")
            similar_queries = vector_store.search_fewshots(discovery_query, top_k=3, knowledge_type="sql_query")
            few_shot_sqls = [q.get('sql_query', '') or q.get('sql', '') for q in similar_queries]
            few_shot_tables = llm_service.extract_tables_from_sql(few_shot_sqls)
            few_shot_tables = _filter_table_names_by_source(few_shot_tables, allowed_tables)
            
            # 3. Schema Index Discovery
            schema_results = _search_schemas_scoped(vector_store, discovery_query, top_k=5, source_id=selected_source_id)
            schema_tables = [f"{s.schema_name}.{s.table_name}" for s in schema_results]
            schema_tables = _filter_table_names_by_source(schema_tables, allowed_tables)
            
            # 4. Re-rank and Filter
            final_table_list = rerank_and_select_tables(few_shot_tables, value_tables, schema_tables)
            final_table_list = _filter_table_names_by_source(final_table_list, allowed_tables)
            logging.info(f"Discovery: Selected tables after reranking: {final_table_list}")
            
            # 5. Hydrate Context (Initial)
            context = _hydrate_discovery_context_scoped(
                final_table_list,
                similar_queries,
                selected_source_id
            )
            
            # 6. Path Finding (Context Expansion)
            yield AgentStatus(step_id=7, message="Analyzing schema relationships and path finding...")
            expanded_list = expand_context_with_neighbors(final_table_list, discovery_query, selected_source_id)
            if len(expanded_list) > len(final_table_list):
                logging.info(f"Discovery: Expanded context from {len(final_table_list)} to {len(expanded_list)} tables.")
                expanded_list = _filter_table_names_by_source(expanded_list, allowed_tables)
                context = _hydrate_discovery_context_scoped(
                    expanded_list,
                    similar_queries,
                    selected_source_id
                )
    
    if db_object_tables and not use_table_override:
        _merge_tables_into_context(context, db_object_tables)
    if db_object_unresolved:
        logging.info(f"[DB Objects] Unresolved database_objects: {db_object_unresolved}")

    if not use_table_override:
        # Branch-aware validation routing
        if discovery_branch == "kb_direct":
            # BRANCH 1.1.1: Skip Steps 8, 9, 10 entirely - high confidence KB match
            logging.info("[KB-First] Branch 1.1.1: Skipping all validation (Steps 8-10). Direct to prompt.")
            value_mappings = {}
            yield AgentStatus(step_id=8, message="High-confidence knowledge base match. Skipping validation...")
            
        elif discovery_branch == "kb_gap_fill":
            # BRANCH 1.1.2: Skip Steps 8, 9 - jump to Step 10 (sufficiency validation)
            logging.info("[KB-First] Branch 1.1.2: Skipping Steps 8-9. Running Step 10 (sufficiency).")
            value_mappings = {}
            
            # Jump directly to Step 10: Schema Sufficiency with Join-Path Validation
            from app.core.config import settings as app_settings
            use_join_path = getattr(app_settings, 'ENABLE_JOIN_PATH_VALIDATION', True)
            
            if use_join_path:
                yield AgentStatus(step_id=10, message="Validating schema sufficiency with join-path analysis...")
                
                sufficiency_result = llm_service.validate_schema_with_join_paths(
                    user_query=discovery_query,
                    schemas=context.relevant_tables,
                    code_type="sql"
                )
            else:
                yield AgentStatus(step_id=10, message="Validating schema sufficiency for query requirements...")
                
                sufficiency_result = llm_service.check_schema_sufficiency(
                    user_query=discovery_query,
                    schemas=context.relevant_tables,
                    code_type="sql"
                )
            
            result_status = sufficiency_result.get("status")
            
            if result_status in ("insufficient_data", "insufficient_joins"):
                missing_points = sufficiency_result.get("missing_data_points", []) or sufficiency_result.get("validation_details", [])
                search_suggestions = sufficiency_result.get("search_suggestions", [])
                missing_logic = sufficiency_result.get("missing_logic")
                
                if result_status == "insufficient_joins" and missing_logic:
                    logging.info(f"Join-path validation failed. Missing logic: {missing_logic}")
                else:
                    logging.info(f"Schema sufficiency check failed. Missing: {[p.get('name', p.get('requirement', '')) for p in missing_points]}")
                
                if search_suggestions:
                    yield AgentStatus(step_id=10, message=f"Missing data detected. Expanding search...")
                    
                    tables_added, context = expand_context_for_missing_data(
                        context,
                        search_suggestions,
                        max_suggestions=5,
                        source_id=selected_source_id
                    )
                    
                    if tables_added:
                        yield AgentStatus(step_id=10, message=f"Added {len(tables_added)} tables: {', '.join(tables_added[:3])}{'...' if len(tables_added) > 3 else ''}")
                        
                        if use_join_path:
                            sufficiency_result = llm_service.validate_schema_with_join_paths(
                                user_query=discovery_query,
                                schemas=context.relevant_tables,
                                code_type="sql"
                            )
                        else:
                            sufficiency_result = llm_service.check_schema_sufficiency(
                                user_query=discovery_query,
                                schemas=context.relevant_tables,
                                code_type="sql"
                            )
                        result_status = sufficiency_result.get("status")
                
                # If still insufficient after expansion, inform user
                if result_status in ("insufficient_data", "insufficient_joins"):
                    if "missing_data_points" in sufficiency_result:
                        missing_names = [p.get("name", "unknown") for p in sufficiency_result.get("missing_data_points", [])]
                    else:
                        missing_names = [d.get("requirement", "unknown") for d in sufficiency_result.get("validation_details", []) if not d.get("found", True)]
                    
                    analysis = sufficiency_result.get("analysis", "Required data not found in available schemas.")
                    missing_logic_msg = sufficiency_result.get("missing_logic", "")
                    
                    missing_list = "\n".join([f"- {name}" for name in missing_names])
                    
                    explanation = f"**Schema Validation Failed**\n\nI analyzed your request but cannot find the required data in the available schemas.\n\n**Missing data points:**\n{missing_list}\n\n**Analysis:** {analysis}"
                    if missing_logic_msg:
                        explanation += f"\n\n**Join issue:** {missing_logic_msg}"
                    
                    result = GenerateSQLResponse(
                        sql="",
                        explanation=explanation,
                        query_type="database",
                        context_text=f"Sufficiency check failed. Missing: {', '.join(missing_names)}",
                        source_id=selected_source_id
                    )
                    yield {"type": "result", "payload": result}
                    yield {"type": "done"}
                    return
            
            last_sufficiency_result = sufficiency_result
            yield AgentStatus(step_id=10, message="Schema sufficiency validated. Proceeding with generation...")
            
        else:
            # BRANCH 1.2 (dual_prong) or fallback: Run full validation pipeline
            # Stage 2.3: Schema Completeness Validation
            yield AgentStatus(step_id=8, message="Validating schema completeness...")
            is_complete, missing_tables, validation_analysis = validate_schema_completeness(
                context, 
                request.query, 
                llm_service
            )
            
            # If missing tables detected, attempt auto-discovery
            if not is_complete and missing_tables:
                logging.info(f"Schema validation found missing tables: {missing_tables}")
                logging.info(f"Validation analysis: {validation_analysis}")
                
                discovery_feedback = ""
                tables_added = []
                tables_not_found = []
                
                for missing_table in missing_tables[:5]:
                    try:
                        disc_res = perform_discovery(DiscoveryRequest(
                            query=missing_table,
                            top_k=3,
                            source_id=selected_source_id
                        ))
                        
                        newly_added = False
                        for table in disc_res.context.relevant_tables:
                            table_full_name = f"{table.schema_name}.{table.table_name}"
                            
                            if not any(t.table_name == table.table_name and t.schema_name == table.schema_name 
                                      for t in context.relevant_tables):
                                context.relevant_tables.append(table)
                                discovery_feedback += f"\n- Auto-discovered and added: {table_full_name}"
                                tables_added.append(table_full_name)
                                newly_added = True
                                logging.info(f"Auto-discovered missing table: {table_full_name}")
                        
                        if not newly_added:
                            already_present = any(
                                missing_table.lower() in f"{t.schema_name}.{t.table_name}".lower()
                                for t in context.relevant_tables
                            )
                            if not already_present:
                                tables_not_found.append(missing_table)
                                
                    except Exception as e:
                        logging.error(f"Error discovering missing table {missing_table}: {e}")
                        tables_not_found.append(missing_table)
                
                if tables_not_found:
                    missing_list = "\n".join([f"- {t}" for t in tables_not_found])
                    result = GenerateSQLResponse(
                        sql="",
                        explanation=f"""I detected that the following referenced tables are missing from the database schema index:

{missing_list}

**Reason:** {validation_analysis}

**Next Steps:**
1. Please ensure these tables exist in your database
2. Go to the Schema Management page and sync these table schemas
3. Then try your query again

Alternatively, if these table references are incorrect, please rephrase your query.""",
                        query_type="database",
                        context_text=f"Missing schemas: {', '.join(tables_not_found)}",
                        source_id=selected_source_id
                    )
                    yield {"type": "result", "payload": result}
                    yield {"type": "done"}
                    return
                
                if tables_added:
                    logging.info(f"Auto-discovery successful. Added tables: {tables_added}")
            
            # Stage 2.5: Value Index Lookup
            yield AgentStatus(step_id=9, message="Checking value index for specific data mappings...")
            value_mappings = lookup_values_for_query(combined_query, allowed_tables=allowed_tables)
            
            # Stage 2.6: Schema Sufficiency Pre-Flight Check
            from app.core.config import settings as app_settings
            use_join_path = getattr(app_settings, 'ENABLE_JOIN_PATH_VALIDATION', True)
            
            if use_join_path:
                yield AgentStatus(step_id=10, message="Validating schema sufficiency with join-path analysis...")
                
                sufficiency_result = llm_service.validate_schema_with_join_paths(
                    user_query=discovery_query,
                    schemas=context.relevant_tables,
                    code_type="sql"
                )
            else:
                yield AgentStatus(step_id=10, message="Validating schema sufficiency for query requirements...")
                
                sufficiency_result = llm_service.check_schema_sufficiency(
                    user_query=discovery_query,
                    schemas=context.relevant_tables,
                    code_type="sql"
                )
            
            result_status = sufficiency_result.get("status")
            
            if result_status in ("insufficient_data", "insufficient_joins"):
                missing_points = sufficiency_result.get("missing_data_points", []) or sufficiency_result.get("validation_details", [])
                search_suggestions = sufficiency_result.get("search_suggestions", [])
                missing_logic = sufficiency_result.get("missing_logic")
                
                if result_status == "insufficient_joins" and missing_logic:
                    logging.info(f"Join-path validation failed. Missing logic: {missing_logic}")
                else:
                    logging.info(f"Schema sufficiency check failed. Missing: {[p.get('name', p.get('requirement', '')) for p in missing_points]}")
                
                if search_suggestions:
                    yield AgentStatus(step_id=10, message=f"Missing data detected. Expanding search...")
                    
                    tables_added, context = expand_context_for_missing_data(
                        context,
                        search_suggestions,
                        max_suggestions=5,
                        source_id=selected_source_id
                    )
                    
                    if tables_added:
                        yield AgentStatus(step_id=10, message=f"Added {len(tables_added)} tables: {', '.join(tables_added[:3])}{'...' if len(tables_added) > 3 else ''}")
                        
                        if use_join_path:
                            sufficiency_result = llm_service.validate_schema_with_join_paths(
                                user_query=discovery_query,
                                schemas=context.relevant_tables,
                                code_type="sql"
                            )
                        else:
                            sufficiency_result = llm_service.check_schema_sufficiency(
                                user_query=discovery_query,
                                schemas=context.relevant_tables,
                                code_type="sql"
                            )
                        result_status = sufficiency_result.get("status")
                
                if result_status in ("insufficient_data", "insufficient_joins"):
                    if "missing_data_points" in sufficiency_result:
                        missing_names = [p.get("name", "unknown") for p in sufficiency_result.get("missing_data_points", [])]
                    else:
                        missing_names = [d.get("requirement", "unknown") for d in sufficiency_result.get("validation_details", []) if not d.get("found", True)]
                    
                    analysis = sufficiency_result.get("analysis", "Required data not found in available schemas.")
                    missing_logic_msg = sufficiency_result.get("missing_logic", "")
                    
                    missing_list = "\n".join([f"- {name}" for name in missing_names])
                    
                    explanation = f"**Schema Validation Failed**\n\nI analyzed your request but cannot find the required data in the available schemas.\n\n**Missing data points:**\n{missing_list}\n\n**Analysis:** {analysis}"
                    if missing_logic_msg:
                        explanation += f"\n\n**Join issue:** {missing_logic_msg}"
                    
                    result = GenerateSQLResponse(
                        sql="",
                        explanation=explanation,
                        query_type="database",
                        context_text=f"Sufficiency check failed. Missing: {', '.join(missing_names)}",
                        source_id=selected_source_id
                    )
                    yield {"type": "result", "payload": result}
                    yield {"type": "done"}
                    return
            
            last_sufficiency_result = sufficiency_result
            yield AgentStatus(step_id=10, message="Schema sufficiency validated. Proceeding with generation...")
    else:
        value_mappings = {}
    
    # Capture validation result for T-SQL prompt (mapping injection and schema adherence)
    last_sufficiency_result: Optional[Dict[str, Any]] = None

    # Build dynamic database info from settings
    keywords_str = ", ".join(db_keywords[:5]) if db_keywords else "business data"
    database_info = f"{friendly_name}: {db_description} ({keywords_str})."
    
    # Stage 3: Build Reference Section (Complexity-Mapped Knowledge Base Examples)
    sql_references = []
    
    # If KB-direct branch, prioritize KB examples and include adjustment guidance
    kb_guidance = ""
    if discovery_branch == "kb_direct" and kb_assessment:
        adjustments = kb_assessment.get("adjustments_needed", [])
        if adjustments:
            kb_guidance = "\n### KB-INFORMED ADJUSTMENTS\nThe following adjustments should be applied to the reference SQL:\n"
            for adj in adjustments:
                kb_guidance += f"- {adj}\n"
            kb_guidance += "\nUse the reference SQL as your starting point and apply these adjustments.\n"
    
    # Map knowledge base examples to complexity level
    complexity_relevant_queries = []
    for sq in (context.similar_queries or []):
        if sq.get("sql", "").strip():
            # Prefer queries with similar complexity
            sq_complexity = score_query_complexity(sq.get("question", ""))
            if sq_complexity == query_complexity or not complexity_relevant_queries:
                complexity_relevant_queries.append(sq)
    
    # Build numbered knowledge base examples
    for idx, sq in enumerate(complexity_relevant_queries[:3], start=1):  # Limit to top 3 mapped examples
        sql_references.append(f"Question {idx}: {sq.get('question', 'N/A')}\nSQL:\n```sql\n{sq.get('sql')}\n```")

    reference_text = "\n\n".join(sql_references) if sql_references else "No previous examples available."
    reference_text += kb_guidance
    
    # Build value mappings reference section
    value_context = ""
    if value_mappings:
        value_context = "\n### VERIFIED DATA MAPPINGS\n"
        for key, values in list(value_mappings.items())[:5]:  # Limit to top 5 mappings
            unique_vals = list(set(values))
            # Format: The value 'Seafood' was found in: [dbo].[Categories].[CategoryName]
            val_str = ", ".join(repr(v) for v in unique_vals)
            value_context += f"- The value(s) {val_str} was found in: {key}\n"

    # Log the initial context
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Build initial schema text using shared utility (table names + column lists for T-SQL stage)
    from app.services.schema_context_utils import build_schema_text
    initial_schema_text = build_schema_text(context.relevant_tables, use_table_override=use_table_override)

    db_objects_context = ""
    if normalized_db_objects:
        objects_list = ", ".join(normalized_db_objects)
        db_objects_context = (
            "### PRIORITIZED DATABASE OBJECTS\n"
            f"The following database objects are already identified as relevant: {objects_list}. "
            "Prioritize these over general schema discovery unless the query explicitly requires otherwise.\n\n"
        )

    editor_context = ""
    if is_editor_mode:
        editor_context = "### EDITOR MODE\nReview the provided code. "
        if request.error_message:
            editor_context += (
                "An error is attached; identify the root cause (syntax, logic, or schema mismatch) and provide a corrected version.\n"
                "### ERROR\n"
                f"{request.error_message}\n"
            )
        else:
            editor_context += "No error is attached; optimize or extend the logic based on the user request.\n"
        if existing_code:
            editor_context += "### EXISTING CODE\n" + existing_code + "\n"
        if request.is_user_code:
            editor_context += "### NOTE\nThe code was manually written by the user. Preserve their style and intent while correcting issues.\n"
        editor_context += "\n"

    # Build validated mapping block from pre-flight validation for T-SQL adherence
    validated_mapping_section = ""
    if last_sufficiency_result:
        details = last_sufficiency_result.get("validation_details", []) or last_sufficiency_result.get("required_data_points", [])
        found_with_mapping = [
            d for d in details
            if d.get("found", False) and (d.get("mapping") or d.get("column_mapping"))
        ]
        if found_with_mapping:
            validated_mapping_section = "### VALIDATED MAPPING (use these exact tables/columns)\n"
            for d in found_with_mapping:
                mapping = d.get("mapping") or d.get("column_mapping")
                req = d.get("requirement") or d.get("name", "requirement")
                validated_mapping_section += f"- Requirement '{req}' -> {mapping}\n"
            validated_mapping_section += "\n"

    context_guard = ""
    if use_table_override:
        context_guard = "### USER-SELECTED CONTEXT\nYou must only use the following schema context provided by the user. Do not reference tables outside of this selection.\n\n"

    # Build scripting authorization based on complexity
    scripting_instruction = ""
    if query_complexity == 'complex':
        scripting_instruction = """### SCRIPTING AUTHORIZATION
This is a COMPLEX query. You are encouraged to use:
- `SET NOCOUNT ON;` at the top of the script
- `DECLARE @variables` for intermediate scalar values
- `#TemporaryTables` for intermediate result sets
- Multiple sequential SELECT/INSERT INTO statements
- `DROP TABLE IF EXISTS #TempTable` for cleanup at the end
Prefer a multi-statement script over a single massive JOIN when the logic involves multiple steps.

"""
    elif query_complexity == 'moderate':
        scripting_instruction = """### SCRIPTING AUTHORIZATION
This is a MODERATE complexity query. You may use variables (`DECLARE`) or CTEs if they improve clarity, but a single query is acceptable if it remains readable.

"""

    initial_prompt = f"""{database_info}

### QUERY ANALYSIS
Complexity Level: {query_complexity}
Extracted Entities: {', '.join(entities) if entities else 'None'}
Date Ranges: {', '.join(date_ranges) if date_ranges else 'None'}

### KNOWLEDGE BASE EXAMPLES
{reference_text}{value_context}

{db_objects_context}{editor_context}{context_guard}{validated_mapping_section}### AVAILABLE SCHEMAS (table names and column lists — use only these)
{initial_schema_text}

### REASONING PROCESS
1. **Decomposition**: Break the request into logical steps (e.g., Step 1: Filter Users; Step 2: Aggregate Sales; Step 3: Join results).
2. **Variable Mapping**: Identify values that should be stored in variables (e.g., @StartDate, @AvgSpend) for reuse across steps.
3. **Drafting**: For complex queries, use #TempTables to hold intermediate results so each step stays clean and readable.
4. **Joins & Bridges**: Look at the "VERIFIED DATA MAPPINGS" to see which tables contain specific data values. If tables are disjoint, find "bridge" tables to join them.
5. **Final Selection**: Return the final result set from the temp tables, variables, or direct query.

### VIEW HANDLING
- If both a base table and its view variant appear in schemas, prefer the base table
- Views ending in _YYYY, _vw, or _view are typically filtered subsets of base tables
- Base tables with datetime columns support flexible date filtering via WHERE clauses

{scripting_instruction}### ATTEMPT HISTORY
First attempt.

## CRITICAL SQL RULES

### 1. SCHEMA ADHERENCE (STRICT)
- You MUST use the table(s) identified in the prior validation analysis (e.g. VALIDATED MAPPING or validation_details). Do not assume the existence of tables or columns not explicitly listed in the PROVIDED TABLE SCHEMAS / AVAILABLE SCHEMAS above.
- Use ONLY the tables and columns defined in the provided schema.
- Pay strict attention to column data types such as INT, VARCHAR, and DATETIME.
- Never assume column names or data types that are not explicitly shown.

### 2. DATA TYPE MATCHING & JOINS
- **CRITICAL**: Before filtering on a column, verify the user's value matches the column's data type.
- If the user provides a STRING value but the target column is INT or NUMERIC, you must JOIN to a related table to look up the ID.
- ALWAYS analyze foreign key relationships found in column descriptions.
- Generate JOIN queries when filtering by attributes from related tables.
- When joining a related table to resolve a type mismatch, do NOT filter on the foreign key ID column using a string value.
- Examine all columns in the joined table's schema and select the column where the data type matches your filter value type and the column name suggests it stores that type of value (e.g., Code, Name).

### 3. TABLE ALIASING & QUALIFICATION
- You MUST use table aliases for every table, such as `FROM dbo.Orders AS o`.
- Every column must be prefixed with its assigned alias, such as `o.OrderID` or `c.CustomerName`.

### 4. T-SQL SYNTAX
- Use `SELECT TOP n` for limiting the number of results.
- Use `DATEPART()` for date components.
- Use `CAST()` for type conversions.
- Use the `N''` prefix for Unicode strings.

### 5. QUERY ANALYSIS PROCESS
- Identify the main entity the user is asking for, such as orders, customers, or products.
- Identify specified filters or conditions, such as customer names or date ranges.
- Compare the data type of each filter value against the target column.
- If a type mismatch exists, determine which related table to JOIN to resolve it.
- Analyze the foreign key relationships between the relevant tables.

### 6. ERROR HANDLING (NO GUESSING)
- If the user request requires a column not present in the provided schema, you are strictly forbidden from guessing. You MUST return: "COLUMN_VALIDATION_ERROR: Cannot find column [column_name]".
- If the user request requires a table not present in the provided schema, you are strictly forbidden from guessing. You MUST return: "TABLE_VALIDATION_ERROR: Cannot find table [table_name]".
- Do not enter a best-effort or TRY...CATCH path with guessed names when data is missing; return a validation error as above.

### 7. OUTPUT FORMAT
- Return raw T-SQL code only. Do not wrap the code in markdown blocks (e.g. ``` sql or ```) as this causes execution failures.
- Provide the explanation in a `/* ... */` comment block at the very top of the response.
- Follow immediately with the T-SQL script. The script MAY contain multiple statements, variable declarations (`DECLARE`), and temporary table operations (`SELECT INTO #Temp`, `DROP TABLE IF EXISTS`).
- Always begin multi-statement scripts with `SET NOCOUNT ON;` to suppress intermediate row-count messages.

### 8. COMPLEX LOGIC & SCRIPTING
- **Multi-Statement Scripts**: If the request involves multi-step aggregations, complex filtering, or data dependencies, use a multi-statement script instead of one massive JOIN.
- **Variables**: Use `DECLARE @VariableName AS DataType` to store intermediate scalar values (like date ranges, averages, or specific IDs).
- **Temporary Tables**: Use `#TempTables` to store intermediate result sets. This improves readability and performance for multi-step logic.
  - *Example*: Store a list of filtered IDs into `#FilteredCustomers` before joining with large transaction tables.
- **CTE vs. Temp Tables**: Use Common Table Expressions (CTEs) for simple recursive or readability needs; use `#TempTables` for complex logic requiring multiple passes over intermediate data.
- **Clean Up**: Always include `DROP TABLE IF EXISTS #TempTable` at the end of your script to clean up temporary tables.

Target Request: {combined_query}
"""

    # Stage 3: Reasoning-First Generation & Iterative Validation
    current_context_history = []
    error_msg = "Unknown error"
    
    # combined_query was already built at the start of the function with conversation history
    
    for attempt in range(5):
        yield AgentStatus(step_id=10 + attempt, message=f"Generating SQL (Attempt {attempt + 1})..." if attempt == 0 else f"Refining SQL (Attempt {attempt + 1})...")
        # Use full schema (table names + column lists) for context continuity with validation stage
        schema_text = initial_schema_text

        # Build attempt history section with failed SQL and errors
        attempt_history_section = ""
        
        target_request_section = f"Target Request: {combined_query}"
        
        if current_context_history:
            attempt_history_section = "\n### PREVIOUS ATTEMPTS (Learn from these errors)\n"
            attempt_history_section += "\n".join(current_context_history)
            
            # Add context about previous failures to the target request
            failure_summary = f"\n\nPrevious attempt failed with: {error_msg}"
            target_request_section = f"Target Request: {combined_query}{failure_summary}\nPlease fix the issues and generate correct SQL."
        else:
            attempt_history_section = "### ATTEMPT HISTORY\nFirst attempt."

        # Construct the full prompt with failed SQL and error details (include validated mapping + full schemas)
        current_prompt = f"""{database_info}

### QUERY ANALYSIS
Complexity Level: {query_complexity}
Extracted Entities: {', '.join(entities) if entities else 'None'}

### KNOWLEDGE BASE EXAMPLES
{reference_text}{value_context}

{db_objects_context}{editor_context}{context_guard}{validated_mapping_section}### AVAILABLE SCHEMAS (table names and column lists — use only these)
{schema_text}

{attempt_history_section}

{scripting_instruction}## CRITICAL SQL RULES

### 1. SCHEMA ADHERENCE (STRICT)
- You MUST use the table(s) identified in the prior validation analysis (e.g. VALIDATED MAPPING or validation_details). Do not assume the existence of tables or columns not explicitly listed in the PROVIDED TABLE SCHEMAS / AVAILABLE SCHEMAS above.
- Use ONLY the tables and columns defined in the provided schema.
- Pay strict attention to column data types such as INT, VARCHAR, and DATETIME.
- Never assume column names or data types that are not explicitly shown.

### 2. DATA TYPE MATCHING & JOINS
- **CRITICAL**: Before filtering on a column, verify the user's value matches the column's data type.
- If the user provides a STRING value but the target column is INT or NUMERIC, you must JOIN to a related table to look up the ID.
- ALWAYS analyze foreign key relationships found in column descriptions.
- Generate JOIN queries when filtering by attributes from related tables.
- When joining a related table to resolve a type mismatch, do NOT filter on the foreign key ID column using a string value.
- Examine all columns in the joined table's schema and select the column where the data type matches your filter value type and the column name suggests it stores that type of value (e.g., Code, Name).

### 3. TABLE ALIASING & QUALIFICATION
- You MUST use table aliases for every table, such as `FROM dbo.Orders AS o`.
- Every column must be prefixed with its assigned alias, such as `o.OrderID` or `c.CustomerName`.

### 4. T-SQL SYNTAX
- Use `SELECT TOP n` for limiting the number of results.
- Use `DATEPART()` for date components.
- Use `CAST()` for type conversions.
- Use the `N''` prefix for Unicode strings.

### 5. QUERY ANALYSIS PROCESS
- Identify the main entity the user is asking for, such as orders, customers, or products.
- Identify specified filters or conditions, such as customer names or date ranges.
- Compare the data type of each filter value against the target column.
- If a type mismatch exists, determine which related table to JOIN to resolve it.
- Analyze the foreign key relationships between the relevant tables.

### 6. ERROR HANDLING (NO GUESSING)
- If the user request requires a column not present in the provided schema, you are strictly forbidden from guessing. You MUST return: "COLUMN_VALIDATION_ERROR: Cannot find column [column_name]".
- If the user request requires a table not present in the provided schema, you are strictly forbidden from guessing. You MUST return: "TABLE_VALIDATION_ERROR: Cannot find table [table_name]".
- Do not enter a best-effort or TRY...CATCH path with guessed names when data is missing; return a validation error as above.

### 7. OUTPUT FORMAT
- Return raw T-SQL code only. Do not wrap the code in markdown blocks (e.g. ``` sql or ```) as this causes execution failures.
- Provide the explanation in a `/* ... */` comment block at the very top of the response.
- Follow immediately with the T-SQL script. The script MAY contain multiple statements, variable declarations (`DECLARE`), and temporary table operations (`SELECT INTO #Temp`, `DROP TABLE IF EXISTS`).
- Always begin multi-statement scripts with `SET NOCOUNT ON;` to suppress intermediate row-count messages.

### 8. COMPLEX LOGIC & SCRIPTING
- **Multi-Statement Scripts**: If the request involves multi-step aggregations, complex filtering, or data dependencies, use a multi-statement script instead of one massive JOIN.
- **Variables**: Use `DECLARE @VariableName AS DataType` to store intermediate scalar values (like date ranges, averages, or specific IDs).
- **Temporary Tables**: Use `#TempTables` to store intermediate result sets. This improves readability and performance for multi-step logic.
- **CTE vs. Temp Tables**: Use CTEs for simple recursive or readability needs; use `#TempTables` for complex logic requiring multiple passes over intermediate data.
- **Clean Up**: Always include `DROP TABLE IF EXISTS #TempTable` at the end of your script.

{target_request_section}
"""

        # Generate SQL query using combined query (with conversation history)
        sql = llm_service.generate_sql_with_context(combined_query, current_prompt)
        
        # Store the generated SQL for later use in attempt history
        generated_sql = sql.strip() if sql else ""
        
        # Validate
        is_special_error, error_text, special_missing = parse_validation_error(sql)
        if is_special_error:
            is_valid, error_msg, missing_cols = False, error_text, special_missing
        else:
            is_valid, error_msg, missing_cols = validate_sql_with_db(sql, source_id=selected_source_id)

        if is_valid:
            result = GenerateSQLResponse(
                sql=sql,
                explanation="The following code might be able to retrieve the data you requested.",
                query_type="database",
                context_text=current_prompt,
                context_history=current_context_history,
                discovery_branch=discovery_branch if not use_table_override else "table_override",
                source_id=selected_source_id
            )
            yield {"type": "result", "payload": result}
            yield {"type": "done"}
            return

        # Stage 3.5: Intelligent Recovery Logic
        discovery_feedback = ""
        recovery_instruction = ""
        
        # Check if this is a special validation error (TABLE_VALIDATION_ERROR or COLUMN_VALIDATION_ERROR)
        if not use_table_override and is_special_error and missing_cols:
            # Missing Object recovery - search for the missing objects in vector database
            for missing_obj in missing_cols:
                disc_res = perform_discovery(DiscoveryRequest(
                    query=missing_obj,
                    top_k=5,
                    source_id=selected_source_id
                ))
                newly_added = False
                for table in disc_res.context.relevant_tables:
                    # Only add if not already in context
                    if not any(t.table_name == table.table_name for t in context.relevant_tables):
                        context.relevant_tables.append(table)
                        discovery_feedback += f"\n- Found new table: {table.table_name} (searched for: {missing_obj})"
                        newly_added = True
                
                # If we found new tables, also do a broader search to find related tables that were excluded
                if newly_added:
                    # Perform additional discovery with broader context to find more related tables
                    broader_query = f"{request.query} {missing_obj}"
                    broader_disc = perform_discovery(DiscoveryRequest(
                        query=broader_query,
                        top_k=5,
                        source_id=selected_source_id
                    ))
                    for table in broader_disc.context.relevant_tables:
                        # Exclude tables already in context
                        if not any(t.table_name == table.table_name for t in context.relevant_tables):
                            context.relevant_tables.append(table)
                            discovery_feedback += f"\n- Found additional related table: {table.table_name}"
            
            if discovery_feedback:
                recovery_instruction = f"Missing Object Recovery: Searched vector database and added newly discovered tables. Retry with updated schema."
            else:
                # No new tables found - stop trying and ask user for more information
                result = GenerateSQLResponse(
                    sql="",
                    explanation=f"I could not find the required objects ({', '.join(missing_cols)}) in the database schema. Please provide more information about:\n1. The correct table or column names\n2. The database schema you're referring to\n3. More context about the data you're trying to query",
                    query_type="database",
                    context_text=current_prompt,
                    context_history=current_context_history,
                    source_id=selected_source_id
                )
                yield {"type": "result", "payload": result}
                yield {"type": "done"}
                return
        elif not use_table_override and missing_cols:
            # Database validation error with missing objects
            for col in missing_cols:
                disc_res = perform_discovery(DiscoveryRequest(
                    query=col,
                    top_k=3,
                    source_id=selected_source_id
                ))
                newly_added = False
                for table in disc_res.context.relevant_tables:
                    if not any(t.table_name == table.table_name for t in context.relevant_tables):
                        context.relevant_tables.append(table)
                        discovery_feedback += f"\n- Found new relevant table: {table.table_name}"
                        newly_added = True
                
                # If found, do a broader search for related tables
                if newly_added:
                    broader_query = f"{request.query} {col}"
                    broader_disc = perform_discovery(DiscoveryRequest(
                        query=broader_query,
                        top_k=5,
                        source_id=selected_source_id
                    ))
                    for table in broader_disc.context.relevant_tables:
                        if not any(t.table_name == table.table_name for t in context.relevant_tables):
                            context.relevant_tables.append(table)
                            discovery_feedback += f"\n- Found additional related table: {table.table_name}"
            
            recovery_instruction = "Missing Object Recovery: New tables added. Retry with updated schema."
        elif "Invalid column name" in error_msg or "Ambiguous column name" in error_msg:
            # Ambiguity/Logic Error recovery
            recovery_instruction = f"Self-Correction: {error_msg}\nRe-examine the join logic and ensure all columns are properly qualified with table aliases."
        elif "type mismatch" in error_msg.lower() or "cannot be converted" in error_msg.lower():
            # Type Mismatch recovery
            recovery_instruction = f"Type Mismatch: {error_msg}\nEnsure data types match in comparisons. Use CAST() when necessary."
        else:
            recovery_instruction = f"Query Error: {error_msg}\nReview the SQL syntax and schema constraints."

        # Record this failure into history with clear SQL query and error message
        # Include full script in failure entry so LLM can see variable/temp table context
        if generated_sql and ("select" in generated_sql.lower() or "declare" in generated_sql.lower() or "#" in generated_sql):
            failure_entry = f"Attempt {attempt+1}:\nUser Request: {combined_query}\nFailed Script:\n{generated_sql}\n\nError Message:\n{error_msg}{discovery_feedback}\n\nRecovery Strategy:\n{recovery_instruction}"
        else:
            failure_entry = f"Attempt {attempt+1}:\nUser Request: {combined_query}\nError Message:\n{error_msg}{discovery_feedback}\n\nRecovery Strategy:\n{recovery_instruction}"
        current_context_history.append(failure_entry)

    # Stage 4: Final Output after exhausting retries
    # Stage 4: Final Output after exhausting retries
    result = GenerateSQLResponse(
        sql="",
        explanation=f"Failed after 5 attempts. Final error: {error_msg}. Please try rephrasing your query or providing more context.",
        query_type="database",
        context_text=current_prompt,
        context_history=current_context_history,
        source_id=selected_source_id
    )
    yield {"type": "result", "payload": result}
    yield {"type": "done"}

def _handle_general_query(query: str, llm_service):
    # (Helper function logic for general classification to keep main function clean)
    system_prompt = "You are a helpful AI assistant for the database."
    response_text = llm_service.chat_completion(
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": query}],
        temperature=0.7
    )
    return GenerateSQLResponse(sql="", explanation=response_text, query_type="general")


def regenerate_sql_with_error_feedback(
    original_request: str,
    failed_sql: str,
    error_message: str,
    schema_context: str,
    attempt_number: int
) -> str:
    """
    Regenerates SQL query based on execution error feedback.
    
    This is a lightweight regeneration function used in the auto-retry loop.
    It focuses specifically on fixing the error without re-running the full
    4-stage discovery pipeline.
    
    Args:
        original_request: User's natural language query
        failed_sql: SQL that failed execution
        error_message: Error traceback from database
        schema_context: Schema descriptions used in original generation
        attempt_number: Current retry attempt (2-5)
        
    Returns:
        Regenerated SQL query as string
    """
    llm_service = get_llm_service()
    
    # Build a focused prompt for error correction
    prompt = f"""You are a T-SQL expert fixing a query that failed execution.

ORIGINAL USER REQUEST:
{original_request}

FAILED SQL QUERY:
{failed_sql}

EXECUTION ERROR:
{error_message}

DATABASE SCHEMA CONTEXT:
{schema_context}

ATTEMPT NUMBER: {attempt_number} of 5

INSTRUCTIONS:
1. Carefully analyze the error message to identify the root cause
2. Maintain the original intent and logic of the query
3. Fix ONLY the specific issue causing the error
4. Follow T-SQL best practices:
   - Use proper table aliases to avoid ambiguous columns
   - Use CAST() for type conversions when needed
   - Qualify all column names with table aliases
   - Use square brackets for reserved words
   - Ensure all referenced tables and columns exist in the schema

COMMON ERROR PATTERNS:
- "Invalid object name" → Check table name spelling and schema
- "Invalid column name" → Verify column exists in schema
- "Ambiguous column name" → Add table alias qualifiers
- "Type mismatch" → Use CAST() or CONVERT()
- "Syntax error" → Check T-SQL syntax (JOIN conditions, WHERE clause, etc.)

MULTI-STATEMENT SCRIPTS:
- The failed code may be a multi-statement script with DECLARE, #TempTables, and multiple SELECTs.
- Preserve the overall script structure when fixing errors.
- Always include SET NOCOUNT ON; at the top of multi-statement scripts.
- Ensure DROP TABLE IF EXISTS for any #TempTables at the end.

OUTPUT:
Return ONLY the corrected SQL script, with no additional text, markdown, or explanation.
"""
    
    try:
        # Call LLM with low temperature for consistency
        fixed_sql = llm_service.chat(prompt, temperature=0.1)
        
        # Clean up any LLM artifacts (markdown blocks, etc.)
        fixed_sql = fixed_sql.strip()
        
        # Remove markdown code blocks
        fixed_sql = re.sub(r'^```sql\s*\n?', '', fixed_sql, flags=re.IGNORECASE)
        fixed_sql = re.sub(r'^```\s*\n?', '', fixed_sql)
        fixed_sql = re.sub(r'\n?```$', '', fixed_sql)
        
        # Remove common prefixes
        if fixed_sql.lower().startswith('sql:'):
            fixed_sql = fixed_sql[4:].strip()
        
        logging.info(f"Regenerated SQL on attempt {attempt_number}")
        return fixed_sql
        
    except Exception as e:
        logging.error(f"Error regenerating SQL: {str(e)}")
        # Return original SQL as fallback
        return failed_sql
    
