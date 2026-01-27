from app.models.schemas import GenerateSQLRequest, GenerateSQLResponse, DiscoveryContext, AgentStatus
import re
import logging
from typing import Optional, Tuple, List, Dict, Any, Generator, Union
from datetime import datetime
from app.services.llm_service import get_llm_service
from app.services.discovery_service import perform_discovery, DiscoveryRequest
from app.services.validation_service import validate_sql_with_db
from app.services.vector_store import get_vector_store
from app.services.settings_service import get_settings_for_display
from collections import defaultdict

def parse_table_override_name(raw_name: str) -> Tuple[str, str]:
    cleaned = raw_name.strip().replace('[', '').replace(']', '')
    if '.' in cleaned:
        schema, table = cleaned.split('.', 1)
        return schema.strip() or "dbo", table.strip()
    return "dbo", cleaned.strip()

def hydrate_override_context(table_names: List[str]) -> DiscoveryContext:
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

def expand_context_with_neighbors(selected_tables: List[str], user_query: str) -> List[str]:
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
            results = vector_store.search_schemas(table_suggestion, top_k=1)
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
    complex_keywords = ['join', 'aggregate', 'group by', 'multiple', 'compare', 'relationship', 'across', 'between', 'correlate']
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

def lookup_values_for_query(query: str, threshold: float = 0.7) -> Dict[str, List[str]]:
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
        results = vector_store.search_values(query, top_k=10)
        
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


def search_data_objects(query: str) -> GenerateSQLResponse:
    """
    Search for relevant database objects based on user query.
    Queries both schema and value indexes and returns unique [schema].[table] objects sorted by relevance.
    
    Args:
        query: User's search query
    
    Returns:
        GenerateSQLResponse with objects list in explanation field
    """
    try:
        vector_store = get_vector_store()
        from app.core.config import settings as app_settings
        if not app_settings.VECTOR_DB_ENABLED:
            return GenerateSQLResponse(
                sql="",
                explanation="Vector search is disabled on this server. Enable VECTOR_DB_ENABLED to use object search.",
                query_type="search",
                context_text=f"Searched for: {query}"
            )
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
        
        # Search schema index for relevant tables
        # Use the internal _search_collection to get scores
        from pymilvus import utility
        
        if utility.has_collection(app_settings.MILVUS_COLLECTION_SCHEMA):
            embedding = vector_store._get_embedding(query)
            schema_results = vector_store._search_collection(
                app_settings.MILVUS_COLLECTION_SCHEMA,
                embedding,
                ['schema_name', 'table_name', 'table_type'],
                top_k=10,
                score_threshold=1.5  # Relaxed threshold for object search (L2 distance)
            )
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
        
        # Search value index for relevant tables
        value_results = vector_store.search_values(query, top_k=10)
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


def generate_sql_for_request(request: GenerateSQLRequest, previous_sql: Optional[str] = None, query_history: Optional[str] = None) -> Generator[Union[AgentStatus, Dict[str, Any]], None, None]:
    # Check for search mode first - user explicitly chose to search objects
    if request.queryMode == "search":
        yield AgentStatus(step_id=1, message="Searching database objects...")
        result = search_data_objects(request.query)
        yield {"type": "result", "payload": result}
        return
    
    yield AgentStatus(step_id=1, message="Initializing agent and loading settings...")

    
    # Load settings for dynamic configuration
    vector_store = get_vector_store()
    try:
        # Get fresh LLM service instance to ensure latest settings
        llm_service = get_llm_service()
        
        settings = get_settings_for_display()
        friendly_name = settings.target_db.friendly_name
        db_description = settings.target_db.description
        db_keywords = settings.target_db.keywords
    except Exception as e:
        print(f"Failed to load settings, using defaults: {e}")
        friendly_name = "Northwind"
        db_description = "Sales database for specialty foods"
        db_keywords = []
    
    # Stage 1: Query Analysis & Intent
    yield AgentStatus(step_id=2, message="Analyzing query and intent...")
    
    # If forceGeneral flag is set (user explicitly chose "General Answer"), skip classification
    if request.forceGeneral:
        yield AgentStatus(step_id=3, message="Processing general query...")
        result = _handle_general_query(request, llm_service)
        yield {"type": "result", "payload": result}
        return

    # Classification removed: Always assume 'database' query unless forceGeneral is set

    # Extract entities and score complexity for database queries
    entities, date_ranges = extract_entities(request.query)
    query_complexity = score_query_complexity(request.query)
    
    yield AgentStatus(step_id=3, message=f"Analyzed query. Complexity: {query_complexity}. Entities: {', '.join(entities) if entities else 'None'}")
    
    # Stage 2: Discovery & Context Synthesis (Multi-Source Retrieval)
    yield AgentStatus(step_id=4, message="Discovering relevant tables and schemas...")
    
    table_override = [t for t in (request.table_override or []) if t]
    use_table_override = len(table_override) > 0

    if use_table_override:
        yield AgentStatus(step_id=4, message="Locking context to user-selected tables...")
        context = hydrate_override_context(table_override)
        if not context.relevant_tables:
            result = GenerateSQLResponse(
                sql="",
                explanation="No matching schemas were found for the selected objects. Please verify the table names and try again.",
                query_type="database",
                context_text="Selected tables not found"
            )
            yield {"type": "result", "payload": result}
            return
    elif request.context:
        # If context is explicitly provided, use it
        context = request.context
    else:
        # Multi-Source Discovery
        
        
        # 1. NER & Value Discovery (Focused)
        # Extract specific entities to avoid noisy value searches (e.g. searching for "how" or "much")
        yield AgentStatus(step_id=5, message="Identifying filter values and entities...")
        filter_values = llm_service.extract_filter_values(request.query)
        value_tables = []
        if filter_values:
            logging.info(f"Discovery: Extracted filter values: {filter_values}")
            for val in filter_values:
                # Search for each specific entity
                v_res = vector_store.search_values(val, top_k=3)
                value_tables.extend([f"{r.get('schema_name', 'dbo')}.{r.get('table_name')}" for r in v_res if r.get('table_name')])
        else:
            # Fallback to broad search if no entities found
            value_results = vector_store.search_values(request.query, top_k=5)
            value_tables = [f"{r.get('schema_name', 'dbo')}.{r.get('table_name')}" for r in value_results if r.get('table_name')]
            
        # 2. Few-Shot Discovery
        # Search for similar queries to get table hints
        yield AgentStatus(step_id=6, message="Searching knowledge base for similar queries...")
        similar_queries = vector_store.search_fewshots(request.query, top_k=3, knowledge_type="sql_query")
        few_shot_sqls = [q.get('sql_query', '') or q.get('sql', '') for q in similar_queries]
        few_shot_tables = llm_service.extract_tables_from_sql(few_shot_sqls)
        
        # 3. Schema Index Discovery
        schema_results = vector_store.search_schemas(request.query, top_k=5)
        schema_tables = [f"{s.schema_name}.{s.table_name}" for s in schema_results]
        
        # 4. Re-rank and Filter
        final_table_list = rerank_and_select_tables(few_shot_tables, value_tables, schema_tables)
        logging.info(f"Discovery: Selected tables after reranking: {final_table_list}")
        
        # 5. Hydrate Context (Initial)
        context = hydrate_discovery_context(final_table_list, similar_queries)
        
        # 6. Path Finding (Context Expansion)
        # Check if the initial selection needs glue tables
        yield AgentStatus(step_id=7, message="Analyzing schema relationships and path finding...")
        expanded_list = expand_context_with_neighbors(final_table_list, request.query)
        if len(expanded_list) > len(final_table_list):
            logging.info(f"Discovery: Expanded context from {len(final_table_list)} to {len(expanded_list)} tables.")
            context = hydrate_discovery_context(expanded_list, similar_queries)
    
    if not use_table_override:
        # Stage 2.3: Schema Completeness Validation - Check if all referenced tables are present
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
            
            # Limit to max 5 missing tables to avoid excessive discovery calls
            for missing_table in missing_tables[:5]:
                try:
                    # Search for the missing table in vector database
                    disc_res = perform_discovery(DiscoveryRequest(query=missing_table, top_k=3))
                    
                    # Add newly discovered tables to context
                    newly_added = False
                    for table in disc_res.context.relevant_tables:
                        # Check if this table matches what we're looking for
                        table_full_name = f"{table.schema_name}.{table.table_name}"
                        
                        # Only add if not already in context
                        if not any(t.table_name == table.table_name and t.schema_name == table.schema_name 
                                  for t in context.relevant_tables):
                            context.relevant_tables.append(table)
                            discovery_feedback += f"\n- Auto-discovered and added: {table_full_name}"
                            tables_added.append(table_full_name)
                            newly_added = True
                            logging.info(f"Auto-discovered missing table: {table_full_name}")
                    
                    if not newly_added:
                        # Check if table was already in context
                        already_present = any(
                            missing_table.lower() in f"{t.schema_name}.{t.table_name}".lower()
                            for t in context.relevant_tables
                        )
                        if not already_present:
                            tables_not_found.append(missing_table)
                            
                except Exception as e:
                    logging.error(f"Error discovering missing table {missing_table}: {e}")
                    tables_not_found.append(missing_table)
            
            # If we couldn't find some tables, return error asking user to sync schemas
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
                    context_text=f"Missing schemas: {', '.join(tables_not_found)}"
                )
                yield {"type": "result", "payload": result}
                return
            
            # Log successful auto-discovery
            if tables_added:
                logging.info(f"Auto-discovery successful. Added tables: {tables_added}")
        
        # Stage 2.5: Value Index Lookup - Get relevant values for the query
        yield AgentStatus(step_id=9, message="Checking value index for specific data mappings...")
        value_mappings = lookup_values_for_query(request.query)
    else:
        value_mappings = {}
    
    # Build dynamic database info from settings
    keywords_str = ", ".join(db_keywords[:5]) if db_keywords else "business data"
    database_info = f"{friendly_name}: {db_description} ({keywords_str})."
    
    # Stage 3: Build Reference Section (Complexity-Mapped Knowledge Base Examples)
    sql_references = []
    
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
    
    # Build initial schema text
    schema_parts = []
    for t in context.relevant_tables:
        if use_table_override and t.description:
            schema_parts.append(t.description)
            continue

        # Format table header
        t_text = f"Table: {t.schema_name or 'dbo'}.{t.table_name}\nDescription: {t.description or 'No description'}\nColumns:"
        # Format columns
        if t.columns:
            for col in t.columns:
                t_text += f"\n  - {col.name} ({col.data_type}): {col.description or ''}"
        else:
             t_text += "\n  (No columns defined)"
        schema_parts.append(t_text)
    
    initial_schema_text = "\n\n".join(schema_parts)

    context_guard = ""
    if use_table_override:
        context_guard = "### USER-SELECTED CONTEXT\nYou must only use the following schema context provided by the user. Do not reference tables outside of this selection.\n\n"

    initial_prompt = f"""{database_info}

### QUERY ANALYSIS
Complexity Level: {query_complexity}
Extracted Entities: {', '.join(entities) if entities else 'None'}
Date Ranges: {', '.join(date_ranges) if date_ranges else 'None'}

### KNOWLEDGE BASE EXAMPLES
{reference_text}{value_context}

{context_guard}### DATABASE SCHEMA
{initial_schema_text}

### REASONING PROCESS
1. Identify the entities and values in the user's request.
2. Look at the "VERIFIED DATA MAPPINGS" to see which tables contain the specific data values (e.g., 'Canada' in Customers).
3. Look at the "DATABASE SCHEMA" to find the relationships between these tables.
4. If tables are disjoint (e.g., Categories and Customers), find the "bridge" tables (like Orders, OrderDetails) to join them.
5. Construct the JOIN path step-by-step.

### ATTEMPT HISTORY
First attempt.

## CRITICAL SQL RULES

### 1. SCHEMA ADHERENCE
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

### 6. ERROR HANDLING
- If a required column is missing from the schema, return: "COLUMN_VALIDATION_ERROR: Cannot find column [column_name]".
- If a required table is missing, return: "TABLE_VALIDATION_ERROR: Cannot find table [table_name]".

### 7. OUTPUT FORMAT
- When generating T-SQL queries, always provide the explanation at the very top of the response, enclosed within a /* ... */ comment block. The code should follow immediately after the comment block.

Target Request: {request.query}
"""

    # Stage 3: Reasoning-First Generation & Iterative Validation
    current_context_history = []
    error_msg = "Unknown error"
    
    # Build accumulated query history (all user requests from conversation start)
    combined_query = request.query
    if query_history:
        combined_query = f"{query_history}. {request.query}"
    
    for attempt in range(5):
        yield AgentStatus(step_id=10 + attempt, message=f"Generating SQL (Attempt {attempt + 1})..." if attempt == 0 else f"Refining SQL (Attempt {attempt + 1})...")
        # Dynamically build schema text
        schema_text = "\n".join([
            f"{t.description}"
            for t in context.relevant_tables
            if t.description
        ])

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

        # Construct the full prompt with failed SQL and error details
        current_prompt = f"""{database_info}

### QUERY ANALYSIS
Complexity Level: {query_complexity}
Extracted Entities: {', '.join(entities) if entities else 'None'}

### KNOWLEDGE BASE EXAMPLES
{reference_text}{value_context}

{context_guard}### DATABASE SCHEMA
{schema_text}

{attempt_history_section}

## CRITICAL SQL RULES

### 1. SCHEMA ADHERENCE
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

### 6. ERROR HANDLING
- If a required column is missing from the schema, return: "COLUMN_VALIDATION_ERROR: Cannot find column [column_name]".
- If a required table is missing, return: "TABLE_VALIDATION_ERROR: Cannot find table [table_name]".

### 7. OUTPUT FORMAT
- When generating T-SQL queries, always provide the explanation at the very top of the response, enclosed within a /* ... */ comment block. The code should follow immediately after the comment block.

{target_request_section}
"""

        # Generate SQL query
        sql = llm_service.generate_sql_with_context(request.query, current_prompt)
        
        # Store the generated SQL for later use in attempt history
        generated_sql = sql.strip() if sql else ""
        
        # Validate
        is_special_error, error_text, special_missing = parse_validation_error(sql)
        if is_special_error:
            is_valid, error_msg, missing_cols = False, error_text, special_missing
        else:
            is_valid, error_msg, missing_cols = validate_sql_with_db(sql)

        if is_valid:
            result = GenerateSQLResponse(
                sql=sql,
                explanation="The following code might be able to retrieve the data you requested.",
                query_type="database",
                context_text=current_prompt,
                context_history=current_context_history
            )
            yield {"type": "result", "payload": result}
            return

        # Stage 3.5: Intelligent Recovery Logic
        discovery_feedback = ""
        recovery_instruction = ""
        
        # Check if this is a special validation error (TABLE_VALIDATION_ERROR or COLUMN_VALIDATION_ERROR)
        if not use_table_override and is_special_error and missing_cols:
            # Missing Object recovery - search for the missing objects in vector database
            for missing_obj in missing_cols:
                disc_res = perform_discovery(DiscoveryRequest(query=missing_obj, top_k=5))
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
                    broader_disc = perform_discovery(DiscoveryRequest(query=broader_query, top_k=5))
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
                    context_history=current_context_history
                )
                yield {"type": "result", "payload": result}
                return
        elif not use_table_override and missing_cols:
            # Database validation error with missing objects
            for col in missing_cols:
                disc_res = perform_discovery(DiscoveryRequest(query=col, top_k=3))
                newly_added = False
                for table in disc_res.context.relevant_tables:
                    if not any(t.table_name == table.table_name for t in context.relevant_tables):
                        context.relevant_tables.append(table)
                        discovery_feedback += f"\n- Found new relevant table: {table.table_name}"
                        newly_added = True
                
                # If found, do a broader search for related tables
                if newly_added:
                    broader_query = f"{request.query} {col}"
                    broader_disc = perform_discovery(DiscoveryRequest(query=broader_query, top_k=5))
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
        # Only include "Failed Query:" if generated_sql contains "select" (actual SQL query)
        if generated_sql and "select" in generated_sql.lower():
            failure_entry = f"Attempt {attempt+1}:\nUser Request: {combined_query}\nFailed Query:\n{generated_sql}\n\nError Message:\n{error_msg}{discovery_feedback}\n\nRecovery Strategy:\n{recovery_instruction}"
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
        context_history=current_context_history
    )
    yield {"type": "result", "payload": result}

def _handle_general_query(request, llm_service):
    # (Helper function logic for general classification to keep main function clean)
    system_prompt = "You are a helpful AI assistant for the database."
    response_text = llm_service.chat_completion(
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": request.query}],
        temperature=0.7
    )
    return GenerateSQLResponse(sql="", explanation=response_text, query_type="general")
    