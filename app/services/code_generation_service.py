"""
R and SAS code generation functions.

These functions generate R and SAS code based on user requests, using knowledge base examples
filtered by knowledge_type for better relevance.
"""

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
    _handle_general_query
)
from app.services.discovery_service import perform_discovery, DiscoveryRequest
from typing import Optional, Generator, Union, Dict, Any, List
from datetime import datetime
import logging

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
        return

    yield AgentStatus(step_id=1, message="Initializing agent and loading settings...")
    llm_service = get_llm_service()
    vector_store = get_vector_store()

    try:
        settings = get_settings_for_display()
        friendly_name = settings.target_db.friendly_name
        db_description = settings.target_db.description
        db_keywords = settings.target_db.keywords
        server_name = settings.target_db.server or ""
        database_name = settings.target_db.database_name or ""
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
                 return

            if tables_added:
                logger.info(f"Auto-discovery successful. Added tables: {tables_added}")
        
        # Stage 2.5: Value Index Lookup
        yield AgentStatus(step_id=9, message="Checking value index for specific data mappings...")
        value_mappings = lookup_values_for_query(request.query)
    else:
        value_mappings = {}

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
    
    # Build Schema & Value Text
    schema_parts = []
    for t in context.relevant_tables:
        if use_table_override and t.description:
            schema_parts.append(t.description)
            continue
        t_text = f"Table: {t.schema_name or 'dbo'}.{t.table_name}\nDescription: {t.description or 'No description'}\nColumns:"
        if t.columns:
            for col in t.columns:
                t_text += f"\n  - {col.name} ({col.data_type}): {col.description or ''}"
        else:
             t_text += "\n  (No columns defined)"
        schema_parts.append(t_text)
    schema_text = "\n\n".join(schema_parts)

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
    - Use `dbConnect(odbc::odbc(), ...)` with `Server = "{server_name}"` and `Database = "{database_name}"`.
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
        return

    yield AgentStatus(step_id=1, message="Initializing agent and loading settings...")
    llm_service = get_llm_service()
    vector_store = get_vector_store()

    try:
        settings = get_settings_for_display()
        friendly_name = settings.target_db.friendly_name
        db_description = settings.target_db.description
        db_keywords = settings.target_db.keywords
        server_name = settings.target_db.server or ""
        database_name = settings.target_db.database_name or ""
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
                 return

            if tables_added:
                logger.info(f"Auto-discovery successful. Added tables: {tables_added}")
        
        # Stage 2.5: Value Index Lookup
        yield AgentStatus(step_id=9, message="Checking value index for specific data mappings...")
        value_mappings = lookup_values_for_query(request.query)
    else:
        value_mappings = {}

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
    
    # Build Schema & Value Text
    schema_parts = []
    for t in context.relevant_tables:
        if use_table_override and t.description:
            schema_parts.append(t.description)
            continue
        t_text = f"Table: {t.schema_name or 'dbo'}.{t.table_name}\nDescription: {t.description or 'No description'}\nColumns:"
        if t.columns:
            for col in t.columns:
                t_text += f"\n  - {col.name} ({col.data_type}): {col.description or ''}"
        else:
             t_text += "\n  (No columns defined)"
        schema_parts.append(t_text)
    schema_text = "\n\n".join(schema_parts)

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


def generate_python_for_request(request: GenerateSQLRequest) -> Generator[Union[AgentStatus, Dict[str, Any]], None, None]:
    """
    Generate Python code based on user request using the same discovery logic as SQL generation.
    It produces native Python code (pandas/sqlalchemy) to retrieve and manipulate data.
    
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
        return

    yield AgentStatus(step_id=1, message="Initializing agent and loading settings...")
    llm_service = get_llm_service()
    vector_store = get_vector_store()

    try:
        settings = get_settings_for_display()
        friendly_name = settings.target_db.friendly_name
        db_description = settings.target_db.description
        db_keywords = settings.target_db.keywords
        server_name = settings.target_db.server or ""
        database_name = settings.target_db.database_name or ""
    except Exception as e:
        logger.warning(f"Failed to load settings for Python engine: {e}")
        friendly_name = "Target Database"
        db_description = "Business Data"
        db_keywords = []
        server_name = ""
        database_name = ""
    
    # Stage 1: Query Analysis & Intent
    yield AgentStatus(step_id=2, message="Analyzing query and intent...")
    
    # If forceGeneral flag is set
    if request.forceGeneral:
        yield AgentStatus(step_id=3, message="Processing general query...")
        result = _handle_general_query(request, llm_service)
        yield {"type": "result", "payload": result}
        return

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
                query_type="python_code",
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
        yield AgentStatus(step_id=5, message="Identifying filter values and entities...")
        filter_values = llm_service.extract_filter_values(request.query)
        value_tables = []
        if filter_values:
            yield AgentStatus(step_id=5, message=f"Found filters: {', '.join(filter_values)}")
            logger.info(f"Discovery: Extracted filter values: {filter_values}")
            for val in filter_values:
                # Search for each specific entity
                v_res = vector_store.search_values(val, top_k=3)
                value_tables.extend([f"{r.get('schema_name', 'dbo')}.{r.get('table_name')}" for r in v_res if r.get('table_name')])
        else:
            # Fallback to broad search if no entities found
            value_results = vector_store.search_values(request.query, top_k=5)
            value_tables = [f"{r.get('schema_name', 'dbo')}.{r.get('table_name')}" for r in value_results if r.get('table_name')]
            
        # 2. Few-Shot Discovery (Use SQL examples for table discovery as they are likely more abundant/relevant for schema mapping)
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
        
        # 5. Hydrate Context (Initial)
        # We don't pass similar_queries here because we want to fetch Python examples later for the prompt
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
        
        # If missing tables detected, attempt auto-discovery
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
                 # In SQL generation we return error, here we can do the same or proceed with best effort.
                 # Let's return error to be safe as code generation depends on it.
                 missing_list = "\n".join([f"- {t}" for t in tables_not_found])
                 result = GenerateSQLResponse(
                    sql="",
                    explanation=f"I detected that the following referenced tables are missing from the database schema index:\n\n{missing_list}\n\n**Reason:** {validation_analysis}\n\nPlease sync the schemas.",
                    query_type="python_code",
                    context_text=f"Missing schemas: {', '.join(tables_not_found)}"
                )
                 yield {"type": "result", "payload": result}
                 return

            if tables_added:
                logger.info(f"Auto-discovery successful. Added tables: {tables_added}")
        
        # Stage 2.5: Value Index Lookup
        yield AgentStatus(step_id=9, message="Checking value index for specific data mappings...")
        value_mappings = lookup_values_for_query(request.query)
    else:
        value_mappings = {}

    # Step: Search for Python-specific knowledge base examples for the Prompt
    yield AgentStatus(step_id=10, message="Searching knowledge base for Python examples...")
    py_examples = vector_store.search_fewshots(request.query, top_k=3, knowledge_type="python_code")
    
    # If no Python examples found, fall back to LLM general knowledge
    if not py_examples:
        logger.info("No Python-specific examples found, using LLM knowledge")
    
    # Build reference section from Python examples
    reference_text = ""
    if py_examples:
        references = []
        for idx, example in enumerate(py_examples, start=1):
            entity = example.get('entity', example)
            question = entity.get('question', '')
            code = entity.get('sql_query', '')  
            references.append(f"Example {idx}:\nQuestion: {question}\nPython Code:\n```python\n{code}\n```")
        reference_text = "\n\n".join(references)
    
    # Build Schema Text
    schema_parts = []
    for t in context.relevant_tables:
        if use_table_override and t.description:
            schema_parts.append(t.description)
            continue
        t_text = f"Table: {t.schema_name or 'dbo'}.{t.table_name}\nDescription: {t.description or 'No description'}\nColumns:"
        if t.columns:
            for col in t.columns:
                t_text += f"\n  - {col.name} ({col.data_type}): {col.description or ''}"
        else:
             t_text += "\n  (No columns defined)"
        schema_parts.append(t_text)
    
    schema_text = "\n\n".join(schema_parts)

    # Build Value Mappings Text
    value_context = ""
    if value_mappings:
        value_context = "\n### VERIFIED DATA MAPPINGS\n"
        for key, values in list(value_mappings.items())[:5]:
            unique_vals = list(set(values))
            val_str = ", ".join(repr(v) for v in unique_vals)
            value_context += f"- The value(s) {val_str} was found in: {key}\n"
            
    # Build dynamic database info from settings
    keywords_str = ", ".join(db_keywords[:5]) if db_keywords else "business data"
    database_info = f"{friendly_name}: {db_description} ({keywords_str})."

    # Step 3: Build Python generation prompt
    prompt = f"""### ROLE
You are an expert Python Programmer and Data Scientist specializing in **pandas** and **sqlalchemy**.

### TASK
Generate clean, production-ready Python code to answer the user's request. 
Use `pandas` to retrieve data from the database and perform data manipulation.
Use the provided database schema and data mappings.

### DATABASE INFO
{database_info}

### USER REQUEST
{request.query}

### QUERY ANALYSIS
Complexity: {query_complexity}
Entities: {', '.join(entities) if entities else 'None'}
Date Ranges: {', '.join(date_ranges) if date_ranges else 'None'}

### KNOWLEDGE BASE EXAMPLES
{reference_text if reference_text else "No specific examples available. Use your Python knowledge."}
{value_context}

### DATABASE SCHEMA
{schema_text}

### PYTHON CODE GUIDELINES
- **Libraries:** Always include `import pandas as pd`, `import sqlalchemy as sa`, and `import matplotlib.pyplot as plt` (if plotting is implied).
- **Database Connectivity:**
    - Use `sa.create_engine()` with `server = "{server_name}"` and `database = "{database_name}"`.
    - Use Windows authentication with `Trusted_Connection=yes` and do NOT include `user` or `password`.
    - Connection string format: `"mssql+pyodbc://@{server_name}/{database_name}?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes"`.
- **Data Retrieval Strategy:**
    - Prefer fetching raw data using `pd.read_sql_table()` or `pd.read_sql_query()`.
    - You may write a simple SQL query within `pd.read_sql_query()` to filter data at the source if the dataset is large, but prefer doing complex transformations (grouping, pivoting) in Pandas.
    - **CRITICAL**: Use ONLY the tables and columns defined in the DATABASE SCHEMA.
    - Pay attention to the "VERIFIED DATA MAPPINGS" for correct string values.
- **Data Manipulation:**
    - Use Pandas methods (`merge`, `groupby`, `pivot_table`, `loc`) to answer the question.
    - Ensure you handle potential `NaN` values.
    - If the user asks for a chart or visualization, use `matplotlib` to generate it.
- **Execution Flow:** 
    1. Library Imports 
    2. Engine Creation 
    3. Data Loading 
    4. Data Processing 
    5. Clean up (dispose engine).
- **Output:** 
    - The code should print the final result or show the plot.
    - Use `snake_case` for variables.

### OUTPUT FORMAT
1.  Start with a multi-line comment block (using triple quotes) briefly explaining the approach.
2.  Follow with the Python code.
3.  Return raw text. Do NOT include markdown code blocks (```python).
"""
    
    # Call LLM to generate Python code
    yield AgentStatus(step_id=11, message="Generating Python code...")
    python_code = llm_service.chat(prompt, temperature=0.1)
    
    response = GenerateSQLResponse(
        sql=python_code,
        explanation=f"The following Python code uses pandas to analyze your data.",
        query_type="python_code",
        context_text=prompt
    )
    yield {"type": "result", "payload": response}
