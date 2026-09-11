"""
R and SAS code generation functions.

These functions generate R and SAS code based on user requests, using knowledge base examples
filtered by knowledge_type for better relevance.
"""

import re
from app.models.schemas import GenerateSQLRequest, GenerateSQLResponse, AgentStatus
from app.services.llm_service import get_llm_service
from app.services.settings_service import get_settings_for_display
from app.services.vector_store import get_vector_store
# Import the SQL generation service to use as context
from app.services.generation_service import (
    generate_sql_for_request,
    extract_entities,
    score_query_complexity,
    hydrate_override_context,
    hydrate_discovery_context,
    expand_context_with_neighbors,
    validate_schema_completeness,
    lookup_values_for_query,
    rerank_and_select_tables,
    search_data_objects,
    _handle_general_query,
    expand_context_for_missing_data
)
from app.services.discovery_service import perform_discovery, DiscoveryRequest
from typing import Optional, Generator, Union, Dict, Any, List
from datetime import datetime
import logging


from app.utils.python_normalization import cleanup_python_code as _cleanup_python_code

logger = logging.getLogger(__name__)


def generate_r_for_request(request: GenerateSQLRequest) -> Generator[Union[AgentStatus, Dict[str, Any]], None, None]:
    """
    Generate R code based on user request using the same discovery logic as SQL generation.
    It produces native R code (tidyverse/DBI) to retrieve and manipulate data.
    
    Args:
        request: Request containing the natural language query
    
    Returns:
        Generator yielding status updates and final response
    """
    if request.queryMode == "search":
        yield AgentStatus(step_id=1, message="Searching database objects...")
        result = search_data_objects(request.query)
        yield {"type": "result", "payload": result}
        yield {"type": "done"}
        return

    yield AgentStatus(step_id=1, message="Initializing agent and loading settings...")
    llm_service = get_llm_service()
    vector_store = get_vector_store()

    try:
        settings = get_settings_for_display()
        if settings.target_db is not None:
            friendly_name = settings.target_db.friendly_name
            db_description = settings.target_db.description
            db_keywords = settings.target_db.keywords
            server_name = settings.target_db.server or ""
            database_name = settings.target_db.database_name or ""
        else:
            friendly_name = "Target Database"
            db_description = "Business Data"
            db_keywords = []
            server_name = ""
            database_name = ""
    except Exception as e:
        logger.warning(f"Failed to load settings for R dbConnect: {e}")
        friendly_name = "Target Database"
        db_description = "Business Data"
        db_keywords = []
        server_name = ""
        database_name = ""
    
    # Stage 1: Query Analysis & Intent
    yield AgentStatus(step_id=2, message="Analyzing query and intent...")
    
    if request.forceGeneral:
        yield AgentStatus(step_id=3, message="Processing general query...")
        result = _handle_general_query(request, llm_service)
        yield {"type": "result", "payload": result}
        yield {"type": "done"}
        return

    entities, date_ranges = extract_entities(request.query)
    query_complexity = score_query_complexity(request.query)
    
    yield AgentStatus(step_id=3, message=f"Analyzed query. Complexity: {query_complexity}. Entities: {', '.join(entities) if entities else 'None'}")
    
    # Stage 2: Discovery & Context Synthesis
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
                query_type="r_code",
                context_text="Selected tables not found"
            )
            yield {"type": "result", "payload": result}
            yield {"type": "done"}
            return
    elif request.context:
        context = request.context
    else:
        # Multi-Source Discovery
        
        # 1. NER & Value Discovery
        yield AgentStatus(step_id=5, message="Identifying filter values and entities...")
        filter_values = llm_service.extract_filter_values(request.query)
        value_tables = []
        if filter_values:
            yield AgentStatus(step_id=5, message=f"Found filters: {', '.join(filter_values)}")
            logger.info(f"Discovery: Extracted filter values: {filter_values}")
            for val in filter_values:
                v_res = vector_store.search_values(val, top_k=3)
                value_tables.extend([f"{r.get('schema_name', 'dbo')}.{r.get('table_name')}" for r in v_res if r.get('table_name')])
        else:
            value_results = vector_store.search_values(request.query, top_k=5)
            value_tables = [f"{r.get('schema_name', 'dbo')}.{r.get('table_name')}" for r in value_results if r.get('table_name')]
            
        # 2. Few-Shot Discovery (Tables from SQL examples)
        yield AgentStatus(step_id=6, message="Searching knowledge base for table hints...")
        similar_queries = vector_store.search_fewshots(request.query, top_k=3, knowledge_type="sql_query")
        few_shot_sqls = [q.get('sql_query', '') or q.get('sql', '') for q in similar_queries]
        few_shot_tables = llm_service.extract_tables_from_sql(few_shot_sqls)
        
        # 3. Schema Index Discovery
        schema_results = vector_store.search_schemas(request.query, top_k=5)
        schema_tables = [f"{s.schema_name}.{s.table_name}" for s in schema_results]
        
        # 4. Re-rank and Filter
        final_table_list = rerank_and_select_tables(few_shot_tables, value_tables, schema_tables)
        yield AgentStatus(step_id=6, message=f"Identified relevant tables: {', '.join(final_table_list)}")
        logger.info(f"Discovery: Selected tables after reranking: {final_table_list}")
        
        # 5. Hydrate Context
        context = hydrate_discovery_context(final_table_list, [])
        
        # 6. Path Finding (Context Expansion)
        yield AgentStatus(step_id=7, message="Analyzing schema relationships and path finding...")
        expanded_list = expand_context_with_neighbors(final_table_list, request.query)
        
        context_msg = f"Final context contains {len(expanded_list)} tables."
        if len(expanded_list) > len(final_table_list):
            added = len(expanded_list) - len(final_table_list)
            context_msg = f"Added {added} glue tables for joins. Total: {len(expanded_list)} tables."
            logger.info(f"Discovery: Expanded context from {len(final_table_list)} to {len(expanded_list)} tables.")
            context = hydrate_discovery_context(expanded_list, [])
        yield AgentStatus(step_id=7, message=context_msg)

    if not use_table_override:
        # Stage 2.3: Schema Completeness Validation
        yield AgentStatus(step_id=8, message="Validating schema completeness...")
        is_complete, missing_tables, validation_analysis = validate_schema_completeness(
            context, 
            request.query, 
            llm_service
        )
        
        if not is_complete and missing_tables:
            logger.info(f"Schema validation found missing tables: {missing_tables}")
            tables_added = []
            tables_not_found = []
            
            for missing_table in missing_tables[:5]:
                try:
                    disc_res = perform_discovery(DiscoveryRequest(query=missing_table, top_k=3))
                    newly_added = False
                    for table in disc_res.context.relevant_tables:
                        if not any(t.table_name == table.table_name and t.schema_name == table.schema_name 
                                  for t in context.relevant_tables):
                            context.relevant_tables.append(table)
                            tables_added.append(f"{table.schema_name}.{table.table_name}")
                            newly_added = True
                    
                    if not newly_added:
                        already_present = any(
                            missing_table.lower() in f"{t.schema_name}.{t.table_name}".lower()
                            for t in context.relevant_tables
                        )
                        if not already_present:
                            tables_not_found.append(missing_table)
                except Exception as e:
                    logger.error(f"Error discovering missing table {missing_table}: {e}")
                    tables_not_found.append(missing_table)
            
            if tables_not_found:
                 missing_list = "\n".join([f"- {t}" for t in tables_not_found])
                 result = GenerateSQLResponse(
                    sql="",
                    explanation=f"I detected that the following referenced tables are missing from the database schema index:\n\n{missing_list}\n\n**Reason:** {validation_analysis}\n\nPlease sync the schemas.",
                    query_type="r_code",
                    context_text=f"Missing schemas: {', '.join(tables_not_found)}"
                )
                 yield {"type": "result", "payload": result}
                 yield {"type": "done"}
                 return

            if tables_added:
                logger.info(f"Auto-discovery successful. Added tables: {tables_added}")
        
        # Stage 2.5: Value Index Lookup
        yield AgentStatus(step_id=9, message="Checking value index for specific data mappings...")
        value_mappings = lookup_values_for_query(request.query)
    else:
        value_mappings = {}

    # Stage 2.6: Schema Sufficiency Pre-Flight Check (Join-Path Validation)
    if not use_table_override:
        from app.core.config import settings as app_settings
        use_join_path = getattr(app_settings, 'ENABLE_JOIN_PATH_VALIDATION', True)
        
        if use_join_path:
            yield AgentStatus(step_id=10, message="Validating schema sufficiency with join-path analysis...")
            
            sufficiency_result = llm_service.validate_schema_with_join_paths(
                user_query=request.query,
                schemas=context.relevant_tables,
                code_type="r"
            )
        else:
            yield AgentStatus(step_id=10, message="Validating schema sufficiency for query requirements...")
            
            sufficiency_result = llm_service.check_schema_sufficiency(
                user_query=request.query,
                schemas=context.relevant_tables,
                code_type="r"
            )
        
        result_status = sufficiency_result.get("status")
        
        if result_status in ("insufficient_data", "insufficient_joins"):
            search_suggestions = sufficiency_result.get("search_suggestions", [])
            missing_logic = sufficiency_result.get("missing_logic")
            
            if result_status == "insufficient_joins" and missing_logic:
                logger.info(f"Join-path validation failed for R. Missing logic: {missing_logic}")
            
            if search_suggestions:
                yield AgentStatus(step_id=10, message=f"Missing data detected. Expanding search...")
                
                tables_added, context = expand_context_for_missing_data(
                    context, 
                    search_suggestions,
                    max_suggestions=5
                )
                
                if tables_added:
                    yield AgentStatus(step_id=10, message=f"Added {len(tables_added)} tables: {', '.join(tables_added[:3])}{'...' if len(tables_added) > 3 else ''}")
                    
                    if use_join_path:
                        sufficiency_result = llm_service.validate_schema_with_join_paths(
                            user_query=request.query,
                            schemas=context.relevant_tables,
                            code_type="r"
                        )
                    else:
                        sufficiency_result = llm_service.check_schema_sufficiency(
                            user_query=request.query,
                            schemas=context.relevant_tables,
                            code_type="r"
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
                    query_type="r_code",
                    context_text=f"Sufficiency check failed. Missing: {', '.join(missing_names)}"
                )
                yield {"type": "result", "payload": result}
                yield {"type": "done"}
                return
        
        yield AgentStatus(step_id=10, message="Schema sufficiency validated. Proceeding with R code generation...")

    # Search for R-specific knowledge base examples
    yield AgentStatus(step_id=10, message="Searching knowledge base for R examples...")
    r_examples = vector_store.search_fewshots(request.query, top_k=3, knowledge_type="r_code")
    
    if not r_examples:
        logger.info("No R-specific examples found, using LLM knowledge")
    
    reference_text = ""
    if r_examples:
        references = []
        for idx, example in enumerate(r_examples, start=1):
            entity = example.get('entity', example)
            question = entity.get('question', '')
            code = entity.get('sql_query', '')  
            references.append(f"Example {idx}:\nQuestion: {question}\nR Code:\n```r\n{code}\n```")
        reference_text = "\n\n".join(references)
    
    # Build Schema & Value Text using shared utility
    from app.services.schema_context_utils import build_schema_text
    schema_text = build_schema_text(context.relevant_tables, use_table_override=use_table_override)

    value_context = ""
    if value_mappings:
        value_context = "\n### VERIFIED DATA MAPPINGS\n"
        for key, values in list(value_mappings.items())[:5]:
            unique_vals = list(set(values))
            val_str = ", ".join(repr(v) for v in unique_vals)
            value_context += f"- The value(s) {val_str} was found in: {key}\n"

    # Build DB Info
    keywords_str = ", ".join(db_keywords[:5]) if db_keywords else "business data"
    database_info = f"{friendly_name}: {db_description} ({keywords_str})."

    # Build R generation prompt
    prompt = f"""### ROLE
You are an expert R Programmer and Data Engineer specializing in the **tidyverse**.

### TASK
Generate clean, production-ready R code to answer the user's request. 
Use the `tidyverse` (dplyr, ggplot2) for data manipulation and visualization.
Use `DBI` and `odbc` for database connectivity.

### DATABASE INFO
{database_info}

### USER REQUEST
{request.query}

### QUERY ANALYSIS
Complexity: {query_complexity}
Entities: {', '.join(entities) if entities else 'None'}

### KNOWLEDGE BASE EXAMPLES
{reference_text if reference_text else "No specific examples available. Use your R knowledge."}
{value_context}

### DATABASE SCHEMA
{schema_text}

### R CODE GUIDELINES
- **Libraries:** Always include `library(DBI)`, `library(odbc)`, `library(dplyr)`, and `library(ggplot2)` (if plotting).
- **Database Connectivity:** 
    - Use `dbConnect(odbc::odbc(), ...)` with `Server = "your_server_name"` and `Database = "your_database_name"`.
    - Use Windows authentication with `Trusted_Connection = "Yes"` and do NOT include `UID` or `PWD`.
    - Use `Driver = "SQL Server"` as the default placeholder.
- **Data Retrieval Strategy:**
    - Use `dbReadTable(con, name = Id(schema="schema", table="table"))` to load raw tables into dataframes.
    - Or use `dbGetQuery(con, "SELECT ...")` for initial filtering if the dataset is large.
    - **CRITICAL**: Use ONLY the tables and columns defined in the DATABASE SCHEMA.
    - Pay attention to the "VERIFIED DATA MAPPINGS" for correct string values.
- **Data Manipulation:**
    - Perform joins, filtering, and aggregation using `dplyr` functions (`left_join`, `filter`, `group_by`, `summarise`).
    - Use `snake_case` for variables.
- **Execution Flow:** 
    1. Library Imports 
    2. Connection 
    3. Data Ingestion 
    4. Data Transformation 
    5. Connection Closure `dbDisconnect(con)`.
- **Output:**
    - Print the result or show the plot.

### OUTPUT FORMAT
1.  Start with a comment block (# ...) briefly explaining the approach.
2.  Follow with the R code.
3.  Return raw text. Do NOT include markdown code blocks (```r).
"""
    
    # Call LLM to generate R code
    yield AgentStatus(step_id=11, message="Generating R code...")
    r_code = llm_service.chat(prompt, temperature=0.1)
    
    response = GenerateSQLResponse(
        sql=r_code,
        explanation=f"The following R code uses tidyverse to analyze your data.",
        query_type="r_code",
        context_text=prompt
    )
    yield {"type": "result", "payload": response}
    yield {"type": "done"}


def generate_sas_for_request(request: GenerateSQLRequest) -> Generator[Union[AgentStatus, Dict[str, Any]], None, None]:
    """
    Generate SAS code based on user request using the same discovery logic as SQL generation.
    It produces native SAS code (PROC SQL/DATA Step) to retrieve and manipulate data.
    
    Args:
        request: Request containing the natural language query
    
    Returns:
        Generator yielding status updates and final response
    """
    # Check for search mode first
    if request.queryMode == "search":
        yield AgentStatus(step_id=1, message="Searching database objects...")
        result = search_data_objects(request.query)
        yield {"type": "result", "payload": result}
        yield {"type": "done"}
        return

    yield AgentStatus(step_id=1, message="Initializing agent and loading settings...")
    llm_service = get_llm_service()
    vector_store = get_vector_store()

    try:
        settings = get_settings_for_display()
        if settings.target_db is not None:
            friendly_name = settings.target_db.friendly_name
            db_description = settings.target_db.description
            db_keywords = settings.target_db.keywords
            server_name = settings.target_db.server or ""
            database_name = settings.target_db.database_name or ""
        else:
            friendly_name = "Target Database"
            db_description = "Business Data"
            db_keywords = []
            server_name = ""
            database_name = ""
    except Exception as e:
        logger.warning(f"Failed to load settings for SAS generation: {e}")
        friendly_name = "Target Database"
        db_description = "Business Data"
        db_keywords = []
        server_name = ""
        database_name = ""
    
    # Stage 1: Query Analysis & Intent
    yield AgentStatus(step_id=2, message="Analyzing query and intent...")
    
    if request.forceGeneral:
        yield AgentStatus(step_id=3, message="Processing general query...")
        result = _handle_general_query(request, llm_service)
        yield {"type": "result", "payload": result}
        yield {"type": "done"}
        return

    entities, date_ranges = extract_entities(request.query)
    query_complexity = score_query_complexity(request.query)
    
    yield AgentStatus(step_id=3, message=f"Analyzed query. Complexity: {query_complexity}. Entities: {', '.join(entities) if entities else 'None'}")
    
    # Stage 2: Discovery & Context Synthesis
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
                query_type="sas_code",
                context_text="Selected tables not found"
            )
            yield {"type": "result", "payload": result}
            yield {"type": "done"}
            return
    elif request.context:
        context = request.context
    else:
        # Multi-Source Discovery
        
        # 1. NER & Value Discovery
        yield AgentStatus(step_id=5, message="Identifying filter values and entities...")
        filter_values = llm_service.extract_filter_values(request.query)
        value_tables = []
        if filter_values:
            yield AgentStatus(step_id=5, message=f"Found filters: {', '.join(filter_values)}")
            logger.info(f"Discovery: Extracted filter values: {filter_values}")
            for val in filter_values:
                v_res = vector_store.search_values(val, top_k=3)
                value_tables.extend([f"{r.get('schema_name', 'dbo')}.{r.get('table_name')}" for r in v_res if r.get('table_name')])
        else:
            value_results = vector_store.search_values(request.query, top_k=5)
            value_tables = [f"{r.get('schema_name', 'dbo')}.{r.get('table_name')}" for r in value_results if r.get('table_name')]
            
        # 2. Few-Shot Discovery
        yield AgentStatus(step_id=6, message="Searching knowledge base for table hints...")
        similar_queries = vector_store.search_fewshots(request.query, top_k=3, knowledge_type="sql_query")
        few_shot_sqls = [q.get('sql_query', '') or q.get('sql', '') for q in similar_queries]
        few_shot_tables = llm_service.extract_tables_from_sql(few_shot_sqls)
        
        # 3. Schema Index Discovery
        schema_results = vector_store.search_schemas(request.query, top_k=5)
        schema_tables = [f"{s.schema_name}.{s.table_name}" for s in schema_results]
        
        # 4. Re-rank and Filter
        final_table_list = rerank_and_select_tables(few_shot_tables, value_tables, schema_tables)
        yield AgentStatus(step_id=6, message=f"Identified relevant tables: {', '.join(final_table_list)}")
        logger.info(f"Discovery: Selected tables after reranking: {final_table_list}")
        
        # 5. Hydrate Context
        context = hydrate_discovery_context(final_table_list, [])
        
        # 6. Path Finding
        yield AgentStatus(step_id=7, message="Analyzing schema relationships and path finding...")
        expanded_list = expand_context_with_neighbors(final_table_list, request.query)
        
        context_msg = f"Final context contains {len(expanded_list)} tables."
        if len(expanded_list) > len(final_table_list):
            added = len(expanded_list) - len(final_table_list)
            context_msg = f"Added {added} glue tables for joins. Total: {len(expanded_list)} tables."
            logger.info(f"Discovery: Expanded context from {len(final_table_list)} to {len(expanded_list)} tables.")
            context = hydrate_discovery_context(expanded_list, [])
        yield AgentStatus(step_id=7, message=context_msg)

    if not use_table_override:
        # Stage 2.3: Schema Completeness Validation
        yield AgentStatus(step_id=8, message="Validating schema completeness...")
        is_complete, missing_tables, validation_analysis = validate_schema_completeness(
            context, 
            request.query, 
            llm_service
        )
        
        if not is_complete and missing_tables:
            logger.info(f"Schema validation found missing tables: {missing_tables}")
            tables_added = []
            tables_not_found = []
            
            for missing_table in missing_tables[:5]:
                try:
                    disc_res = perform_discovery(DiscoveryRequest(query=missing_table, top_k=3))
                    newly_added = False
                    for table in disc_res.context.relevant_tables:
                        if not any(t.table_name == table.table_name and t.schema_name == table.schema_name 
                                  for t in context.relevant_tables):
                            context.relevant_tables.append(table)
                            tables_added.append(f"{table.schema_name}.{table.table_name}")
                            newly_added = True
                    
                    if not newly_added:
                        # Check if already present
                        already_present = any(
                            missing_table.lower() in f"{t.schema_name}.{t.table_name}".lower()
                            for t in context.relevant_tables
                        )
                        if not already_present:
                            tables_not_found.append(missing_table)
                except Exception as e:
                    logger.error(f"Error discovering missing table {missing_table}: {e}")
                    tables_not_found.append(missing_table)
            
            if tables_not_found:
                 missing_list = "\n".join([f"- {t}" for t in tables_not_found])
                 result = GenerateSQLResponse(
                    sql="",
                    explanation=f"I detected that the following referenced tables are missing from the database schema index:\n\n{missing_list}\n\n**Reason:** {validation_analysis}\n\nPlease sync the schemas.",
                    query_type="sas_code",
                    context_text=f"Missing schemas: {', '.join(tables_not_found)}"
                )
                 yield {"type": "result", "payload": result}
                 yield {"type": "done"}
                 return

            if tables_added:
                logger.info(f"Auto-discovery successful. Added tables: {tables_added}")
        
        # Stage 2.5: Value Index Lookup
        yield AgentStatus(step_id=9, message="Checking value index for specific data mappings...")
        value_mappings = lookup_values_for_query(request.query)
    else:
        value_mappings = {}

    # Stage 2.6: Schema Sufficiency Pre-Flight Check (Join-Path Validation)
    if not use_table_override:
        from app.core.config import settings as app_settings
        use_join_path = getattr(app_settings, 'ENABLE_JOIN_PATH_VALIDATION', True)
        
        if use_join_path:
            yield AgentStatus(step_id=10, message="Validating schema sufficiency with join-path analysis...")
            
            sufficiency_result = llm_service.validate_schema_with_join_paths(
                user_query=request.query,
                schemas=context.relevant_tables,
                code_type="sas"
            )
        else:
            yield AgentStatus(step_id=10, message="Validating schema sufficiency for query requirements...")
            
            sufficiency_result = llm_service.check_schema_sufficiency(
                user_query=request.query,
                schemas=context.relevant_tables,
                code_type="sas"
            )
        
        result_status = sufficiency_result.get("status")
        
        if result_status in ("insufficient_data", "insufficient_joins"):
            search_suggestions = sufficiency_result.get("search_suggestions", [])
            missing_logic = sufficiency_result.get("missing_logic")
            
            if result_status == "insufficient_joins" and missing_logic:
                logger.info(f"Join-path validation failed for SAS. Missing logic: {missing_logic}")
            
            if search_suggestions:
                yield AgentStatus(step_id=10, message=f"Missing data detected. Expanding search...")
                
                tables_added, context = expand_context_for_missing_data(
                    context, 
                    search_suggestions,
                    max_suggestions=5
                )
                
                if tables_added:
                    yield AgentStatus(step_id=10, message=f"Added {len(tables_added)} tables: {', '.join(tables_added[:3])}{'...' if len(tables_added) > 3 else ''}")
                    
                    if use_join_path:
                        sufficiency_result = llm_service.validate_schema_with_join_paths(
                            user_query=request.query,
                            schemas=context.relevant_tables,
                            code_type="sas"
                        )
                    else:
                        sufficiency_result = llm_service.check_schema_sufficiency(
                            user_query=request.query,
                            schemas=context.relevant_tables,
                            code_type="sas"
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
                    query_type="sas_code",
                    context_text=f"Sufficiency check failed. Missing: {', '.join(missing_names)}"
                )
                yield {"type": "result", "payload": result}
                yield {"type": "done"}
                return
        
        yield AgentStatus(step_id=10, message="Schema sufficiency validated. Proceeding with SAS code generation...")

    # Search for SAS-specific knowledge base examples
    yield AgentStatus(step_id=10, message="Searching knowledge base for SAS examples...")
    sas_examples = vector_store.search_fewshots(request.query, top_k=3, knowledge_type="sas_code")
    
    if not sas_examples:
        logger.info("No SAS-specific examples found, using LLM knowledge")
    
    reference_text = ""
    if sas_examples:
        references = []
        for idx, example in enumerate(sas_examples, start=1):
            entity = example.get('entity', example)
            question = entity.get('question', '')
            code = entity.get('sql_query', '')  
            references.append(f"Example {idx}:\nQuestion: {question}\nSAS Code:\n```sas\n{code}\n```")
        reference_text = "\n\n".join(references)
    
    # Build Schema & Value Text using shared utility
    from app.services.schema_context_utils import build_schema_text as build_schema_text_sas
    schema_text = build_schema_text_sas(context.relevant_tables, use_table_override=use_table_override)

    value_context = ""
    if value_mappings:
        value_context = "\n### VERIFIED DATA MAPPINGS\n"
        for key, values in list(value_mappings.items())[:5]:
            unique_vals = list(set(values))
            val_str = ", ".join(repr(v) for v in unique_vals)
            value_context += f"- The value(s) {val_str} was found in: {key}\n"

    # Build DB Info
    keywords_str = ", ".join(db_keywords[:5]) if db_keywords else "business data"
    database_info = f"{friendly_name}: {db_description} ({keywords_str})."

    # Build SAS generation prompt
    prompt = f"""### ROLE
You are an expert SAS Programmer and Data Analyst.

### TASK
Generate clean, production-ready SAS code to answer the user's request.
Use `PROC SQL` or `DATA` steps as appropriate.

### DATABASE INFO
{database_info}

### USER REQUEST
{request.query}

### QUERY ANALYSIS
Complexity: {query_complexity}
Entities: {', '.join(entities) if entities else 'None'}

### KNOWLEDGE BASE EXAMPLES
{reference_text if reference_text else "No specific examples available. Use your SAS knowledge."}
{value_context}

### DATABASE SCHEMA
{schema_text}

### SAS CODE GUIDELINES
- **Connectivity:**
    - Start by defining a library reference to the database: `LIBNAME dbdata ODBC ...` (or relevant SAS/ACCESS engine).
    - Use connection parameters: Server="{server_name}", Database="{database_name}". Assume Trusted Connection.
- **Data Retrieval:**
    - Access data directly from the library (e.g., `dbdata.Orders`).
    - **CRITICAL**: Use ONLY the tables and columns defined in the DATABASE SCHEMA.
    - Pay attention to the "VERIFIED DATA MAPPINGS" for correct string values.
- **Data Manipulation (The "SAS Way"):**
    - Use `PROC SQL` for complex joins, filtering, and initial aggregation (mental model similar to SQL).
    - Use **Data Steps** (`DATA ...; SET ...;`) for row-by-row logic, conditional flags, or complex transformations if more efficient.
    - Use specialized PROCs for analysis: `PROC FREQ` (counts), `PROC MEANS`/`SUMMARY` (aggregates), `PROC RANK`, etc.
    - Use `PROC SGPLOT` for any requested visualizations.
- **Code Quality:**
    - Add clear comments explaining the logic steps.
    - Use `TITLE` statements to label outputs.
    - Ensure the code handles missing values (SAS `.` or ` `).
    - End the script with `QUIT;` or `RUN;`.

### OUTPUT FORMAT
1.  Start with a comment block (/* ... */) briefly explaining the approach.
2.  Follow with the SAS code.
3.  Return raw text. Do NOT include markdown code blocks (```sas).
"""
    
    # Call LLM to generate SAS code
    yield AgentStatus(step_id=11, message="Generating SAS code...")
    sas_code = llm_service.chat(prompt, temperature=0.1)
    
    response = GenerateSQLResponse(
        sql=sas_code,
        explanation=f"The following SAS code may resolve your request.",
        query_type="sas_code",
        context_text=prompt
    )
    yield {"type": "result", "payload": response}
    yield {"type": "done"}


def _is_code_edit_request(query: str) -> bool:
    """Return True if the user message is asking to edit/modify previously generated code."""
    if not query or not query.strip():
        return False
    q = query.strip().lower()
    edit_phrases = [
        "change ", "replace ", "update the code", "in the generated code",
        "in the code", "modify the code", "edit the code", "fix the code",
        "change the ", "replace the ", "update the ", "change where", "replace where",
    ]
    return any(p in q for p in edit_phrases)


def _apply_python_code_edit(previous_code: str, user_edit_instruction: str, query_history: Optional[str], llm_service) -> str:
    """
    Ask the LLM to apply the user's edit to the previous code and return FULL executable code.
    Ensures the result is complete code that still answers the original request, not a snippet.
    """
    prompt = f"""### ROLE
You are an expert Python programmer. The user has previously been shown Python code and now wants a specific edit applied.

### CRITICAL RULES
1. Apply ONLY the change the user asked for. Do not add or remove unrelated logic.
2. You MUST return the COMPLETE, executable Python script—not a snippet or a diff.
3. The output must be valid Python that can run as-is (same structure: imports, engine, raw_connection, pd.read_sql, final_result_df, etc.).
4. Do NOT use markdown code blocks. Do NOT include any text before or after the code. Start with # comments or import.
5. Preserve the original goal of the script; the edit should only change what the user specified (e.g. a WHERE clause value).

### PREVIOUS PYTHON CODE
```python
{_strip_db_connection_injection(previous_code)}
```

### CONVERSATION CONTEXT (optional)
{query_history or "(none)"}

### USER'S EDIT REQUEST
{user_edit_instruction}

### YOUR TASK
Apply the user's requested change to the code above and output the ENTIRE modified Python script. The code must remain executable and still answer the original analysis question."""

    code = llm_service.chat(prompt, temperature=0.1)
    return _cleanup_python_code(code)


def generate_python_for_request(request: GenerateSQLRequest) -> Generator[Union[AgentStatus, Dict[str, Any]], None, None]:
    """
    Generate Python code using the same built-in pipeline as SQL generation:
    routing, pin validation, KB/precomputed fast paths, discovery, and bounded retry.
    """
    if request.queryMode == "search":
        yield AgentStatus(step_id=1, message="Searching database objects...")
        result = search_data_objects(request.query)
        yield {"type": "result", "payload": result}
        yield {"type": "done"}
        return

    combined_query = request.query
    if request.queryHistory:
        combined_query = f"{request.queryHistory}. {request.query}"

    if request.forceGeneral:
        yield AgentStatus(step_id=1, message="Processing general query...")
        llm_service = get_llm_service()
        result = _handle_general_query(combined_query, llm_service)
        yield {"type": "result", "payload": result}
        yield {"type": "done"}
        return

    existing_code = request.existing_code or request.previousSQL
    is_edit = bool(existing_code and existing_code.strip() and _is_code_edit_request(request.query))

    from app.core.orchestrator.builtin_sql_generator import generate_python_builtin
    from app.services.source_resolver import resolve_or_primary
    from app.services.stores.bundle import build_source_stores

    builtin_source = resolve_or_primary(request.source_id)
    stores = build_source_stores(builtin_source)
    for event in generate_python_builtin(request, stores):
        if is_edit and isinstance(event, dict) and event.get("type") == "result":
            payload = event.get("payload")
            if isinstance(payload, dict) and payload.get("sql") and payload.get("success") is not False:
                payload["is_code_edit"] = True
                if not payload.get("explanation"):
                    payload["explanation"] = "Code updated based on your request."
        yield event


def regenerate_python_with_error_feedback(
    original_request: str,
    failed_code: str,
    error_message: str,
    schema_context: str,
    attempt_number: int
) -> str:
    """
    Regenerate Python code based on execution error feedback.
    
    Args:
        original_request: The user's original natural language request
        failed_code: The Python code that failed to execute
        error_message: The error message and traceback from execution
        schema_context: The database schema context used for original generation
        attempt_number: Which retry attempt this is (2-5)
    
    Returns:
        Regenerated Python code as a string
    """
    llm_service = get_llm_service()
    
    # Strip DB_CONNECTION_STRING from failed code to avoid sending sensitive data
    code_to_send = _strip_db_connection_injection(failed_code)
    
    prompt = f"""### ROLE
You are an expert Python Programmer debugging code execution failures.

### CONTEXT
A Python script was generated to answer a user's request, but it failed during execution.
Your task is to fix the code based on the error feedback.

**IMPORTANT**: This is retry attempt {attempt_number} of 5. Focus on fixing the specific error while still fulfilling the original user request.

### ORIGINAL USER REQUEST
{original_request}

### FAILED CODE
```python
{code_to_send}
```

### EXECUTION ERROR
```
{error_message}
```

### DATABASE SCHEMA
{schema_context}

### YOUR TASK
1. Analyze the error carefully - identify the root cause
2. Fix the specific issue in the code
3. **CRITICAL**: The fix must still address the original user request
4. **CRITICAL**: Do NOT change the goal - only fix the execution error
5. Return corrected Python code that will execute successfully

### COMMON ISSUES TO CHECK
- **Connection Issues**: Ensure `engine.raw_connection()` is used with try/finally pattern
- **SQL Syntax**: Check table names, column names match the schema exactly (case-sensitive)
- **Data Types**: Ensure proper type conversions for operations
- **Missing Imports**: Verify all required libraries are imported
- **Variable Names**: Check for typos in variable names
- **DataFrame Operations**: Ensure operations are valid for pandas DataFrames

### PYTHON CODE GUIDELINES (SAME AS BEFORE)
- **Connectivity:**
    - The application will inject `DB_CONNECTION_STRING` at runtime (you don't need to define it)
    - **MANDATORY PATTERN**: 
      ```python
      conn = engine.raw_connection()
      try:
          df = pd.read_sql("SELECT * FROM dbo.TableName", conn)
      finally:
          conn.close()
      ```
    - **DO NOT use context managers** (`with` statements for connections)
- **Data Retrieval:**
    - Use ONLY tables and columns from the DATABASE SCHEMA
    - Use exact table/column names (case-sensitive)
- **Final Output:**
    - Assign final result to `final_result_df`
    - Do NOT wrap in `def main():` function

### OUTPUT FORMAT
Return ONLY the corrected Python code:
- Start with # comments explaining the fix
- Include all imports
- Use the MANDATORY connection pattern
- No markdown blocks, no shell commands, no plain text explanations
- Just executable Python code

**Example Format:**
# Fixed: Corrected table name from 'products' to 'dbo.Products'
# Fixed: Added missing import for datetime
import pandas as pd
import sqlalchemy
from datetime import datetime
# ... rest of corrected code ...
"""
    
    # Generate fixed code
    fixed_code = llm_service.chat(prompt, temperature=0.1)
    
    # Clean up the generated code
    fixed_code = _cleanup_python_code(fixed_code)
    
    return fixed_code


def _strip_db_connection_injection(code: str) -> str:
    """
    Remove the injected DB_CONNECTION_STRING value from code before sending to LLM.
    Keeps the variable reference but removes the actual connection string.
    
    Args:
        code: Python code that may contain injected connection string
    
    Returns:
        Code with DB_CONNECTION_STRING reference preserved but value stripped
    """
    if not code:
        return code
    
    # Pattern to match DB_CONNECTION_STRING assignment (keep the pattern, remove the value)
    # This regex looks for lines like: DB_CONNECTION_STRING = "mssql+pyodbc://..."
    # We'll replace the value with a placeholder comment
    
    lines = code.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # Check if this line contains DB_CONNECTION_STRING assignment
        if 'DB_CONNECTION_STRING' in line and '=' in line:
            # If it's a comment showing the example format, keep it
            if line.strip().startswith('#'):
                cleaned_lines.append(line)
            # If it's an actual assignment, replace with comment
            elif re.match(r'\s*DB_CONNECTION_STRING\s*=', line):
                cleaned_lines.append('# DB_CONNECTION_STRING will be injected at runtime')
            else:
                cleaned_lines.append(line)
        else:
            cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)
