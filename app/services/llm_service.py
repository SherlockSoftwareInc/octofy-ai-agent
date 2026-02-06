from abc import ABC, abstractmethod
from typing import List, Any, Dict
from app.models.schemas import DiscoveryContext
from app.core.config import settings
from openai import OpenAI

import litellm
import logging
from datetime import datetime
from app.utils.logging_utils import log_llm_interaction

class LLMServiceBase(ABC):
    @abstractmethod
    def generate_sql(self, query: str, context: DiscoveryContext) -> str:
        pass

    @abstractmethod
    def generate_sql_with_context(self, query: str, context_text: str) -> str:
        pass

    @abstractmethod
    def chat(self, prompt: str, temperature: float = 0) -> str:
        pass

    @abstractmethod
    def chat_completion(self, messages: List[Dict[str, str]], temperature: float = 0) -> str:
        pass

    @abstractmethod
    def extract_tables_from_sql(self, sql_queries: List[str]) -> List[str]:
        pass

    @abstractmethod
    def suggest_intermediate_tables(self, selected_tables: List[str], user_query: str) -> List[str]:
        pass

    @abstractmethod
    def extract_filter_values(self, query: str) -> List[str]:
        pass

    @abstractmethod
    def validate_schema_with_join_paths(self, user_query: str, schemas: List[Any], code_type: str = "sql") -> Dict[str, Any]:
        pass

class OpenAILLMService(LLMServiceBase):
    def __init__(self):
        from app.services.settings_service import load_settings
        
        # Load dynamic settings
        agent_settings = load_settings()
        llm_config = agent_settings.llm_config
        
        # Prioritize settings file over env vars
        self.api_key = llm_config.llm_api_key or settings.OPENAI_API_KEY
        self.base_url = llm_config.llm_endpoint
        self.model = llm_config.llm_model
        
        # For development, use a mock if API key is not set properly
        if not self.api_key or (self.api_key.startswith("sk-") and len(self.api_key) < 20):
            self.client = None  # Mock mode
        else:
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def generate_sql(self, query: str, context: DiscoveryContext) -> str:
        # Mock mode for development
        if self.client is None:
            return f"SELECT TOP 10 * FROM users WHERE name LIKE '%{query.split()[-1]}%'"

        system_prompt = self._build_system_prompt(query, context)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            temperature=0  # SQL should be deterministic
        )

        sql = response.choices[0].message.content
        
        # Log the interaction
        log_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ]
        log_llm_interaction(log_messages, sql)
        
        # Basic cleanup: remove markdown code blocks if present
        sql = sql.replace("```sql", "").replace("```", "").strip()
        return sql

    def validate_schema_references(self, schemas: List[Any], user_query: str) -> str:
        """
        Validate if all referenced tables (via foreign keys) are present in the provided schemas.
        
        Args:
            schemas: List of TableSchema objects with descriptions that may contain foreign key references
            user_query: The user's natural language query for context
            
        Returns:
            Structured validation response from LLM indicating missing tables
        """
        # Mock mode for development
        if self.client is None:
            return "SCHEMA_COMPLETE: YES\nMISSING_TABLES: NONE\nANALYSIS: Mock validation - all schemas present"
        
        # Build schema descriptions for analysis
        schema_descriptions = []
        table_names_present = []
        
        for schema in schemas:
            schema_name = getattr(schema, 'schema_name', 'dbo')
            table_name = getattr(schema, 'table_name', '')
            description = getattr(schema, 'description', '')
            
            table_names_present.append(f"[{schema_name}].[{table_name}]")
            schema_descriptions.append(f"{description}\n")
        
        schemas_text = "\n".join(schema_descriptions).replace("\\n", "\n")
        present_tables = "\n".join([f"- {t}" for t in table_names_present])
        
        validation_prompt = f"""You are a database schema analyzer for SQL Server.

### PROVIDED TABLE SCHEMAS:
{schemas_text}

### TABLES CURRENTLY PRESENT:
{present_tables}

### USER QUERY:
{user_query}

### TASK:
Analyze the column descriptions in the provided schemas for references to other tables (foreign key relationships). 
Look for patterns like:
- "References [TableName]"
- "FK to [TableName]"
- "Foreign key to [schema].[table]"
- "Links to [TableName]"
- Or any mention of another table name in the relationship context

For each table referenced in the descriptions, check if that table is in the "TABLES CURRENTLY PRESENT" list above.

**IMPORTANT RULES:**
1. Only flag tables that are EXPLICITLY referenced as foreign keys or relationships in column descriptions
2. Do NOT flag tables mentioned casually or in general text
3. Use exact table names from references (including schema prefix if mentioned)
4. If a referenced table is already in the present list, do NOT flag it as missing

### OUTPUT FORMAT:
Return your analysis in EXACTLY this format:

SCHEMA_COMPLETE: YES or NO
MISSING_TABLES: table1, table2, table3 (comma-separated, or "NONE" if complete)
ANALYSIS: Brief explanation of what's missing and why

**Example outputs:**

Example 1 (complete):
SCHEMA_COMPLETE: YES
MISSING_TABLES: NONE
ANALYSIS: All referenced tables are present in the context.

Example 2 (missing tables):
SCHEMA_COMPLETE: NO
MISSING_TABLES: dbo.Customers, dbo.Products
ANALYSIS: Orders.CustomerID references dbo.Customers (not present), OrderDetails.ProductID references dbo.Products (not present).
"""
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a database schema analyzer. Analyze schemas and identify missing referenced tables."},
                {"role": "user", "content": validation_prompt}
            ],
            temperature=0  # Deterministic analysis
        )
        
        validation_result = response.choices[0].message.content
        
        # Log the interaction
        log_messages = [
            {"role": "system", "content": "You are a database schema analyzer. Analyze schemas and identify missing referenced tables."},
            {"role": "user", "content": validation_prompt}
        ]
        log_llm_interaction(log_messages, validation_result)
        
        return validation_result

    def check_schema_sufficiency(self, user_query: str, schemas: List[Any], code_type: str = "sql") -> Dict[str, Any]:
        """
        Pre-flight check: Validate if the provided schemas contain all columns 
        needed to answer the user's query.
        
        Args:
            user_query: The user's natural language request
            schemas: List of TableSchema objects with column definitions
            code_type: "sql" or "python" - affects the analysis context
            
        Returns:
            Dict with keys: status, required_data_points, missing_data_points, 
                           search_suggestions, analysis
        """
        import json
        import logging
        
        # Mock mode for development
        if self.client is None:
            return {
                "status": "sufficient",
                "required_data_points": [],
                "missing_data_points": [],
                "search_suggestions": [],
                "analysis": "Mock validation - schema assumed sufficient"
            }
        
        # Build schema text with column details
        schema_text_parts = []
        for t in schemas:
            schema_name = getattr(t, 'schema_name', 'dbo')
            table_name = getattr(t, 'table_name', '')
            columns = getattr(t, 'columns', [])
            description = getattr(t, 'description', '')
            
            if columns:
                # Use structured column info if available
                cols = ", ".join([f"{c.name} ({c.data_type})" for c in columns])
                schema_text_parts.append(f"[{schema_name}].[{table_name}]: {cols}")
            elif description:
                # Fall back to description (which contains markdown with column details)
                # Include the full description as it contains column information
                schema_text_parts.append(f"[{schema_name}].[{table_name}]:\n{description}")
            else:
                schema_text_parts.append(f"[{schema_name}].[{table_name}]: (no column information available)")
        
        schema_text = "\n\n".join(schema_text_parts)
        
        # Determine language-specific guidance
        if code_type.lower() == "python":
            derivation_guidance = """### DERIVABLE VALUES - Mark as "found: true" if computable from existing columns:
Python/pandas can compute virtually ANY derived value from raw columns:
- **Aggregations**: df.sum(), df.mean(), df.count(), df.groupby().agg() 
- **Calculated fields**: df['amount'] = df['quantity'] * df['price']
- **Rankings**: df.nlargest(), df.sort_values(), df.rank()
- **Date operations**: pd.to_datetime(), dt.year, dt.month, date arithmetic
- **String operations**: str.contains(), str.upper(), str.split()
- **Statistical analysis**: correlation, percentiles, distributions
- **Pivot tables**: df.pivot_table(), df.crosstab()
- **Window functions**: df.rolling(), df.expanding(), df.shift()

IMPORTANT: If the base columns exist, Python can derive almost anything through code."""
        else:
            derivation_guidance = """### DERIVABLE VALUES - Mark as "found: true" if computable from existing columns:
- **Aggregations**: COUNT(*), SUM(column), AVG(column), MIN/MAX - always available
- **Calculated fields**: quantity * unit_price = amount, date differences, etc.
- **Rankings**: TOP N, ORDER BY, ROW_NUMBER() - always available
- **Date extractions**: YEAR(), MONTH(), DATEPART() from date columns
- **String operations**: CONCAT(), SUBSTRING(), UPPER/LOWER from string columns
- **Conditional logic**: CASE WHEN, IIF() on existing columns
- **Standard joins**: If related tables exist, join operations are available"""

        prompt = f"""### ROLE
You are a database schema analyst performing a pre-flight validation check.

### TASK
Analyze the user's request and determine if the provided database schemas contain 
the columns necessary to answer it - either directly or through computation/derivation.

### CODE TYPE
{code_type.upper()} - Consider what calculations are possible in this language.

### USER REQUEST
{user_query}

### AVAILABLE SCHEMAS
{schema_text}

### VALIDATION PROTOCOL
1. Identify the core data points required to answer the user's request
2. For each data point, check if it can be satisfied by:
   a) A direct column match in the provided schemas, OR
   b) A DERIVABLE/COMPUTABLE value from existing columns using {code_type.upper()} capabilities

{derivation_guidance}

### OUTPUT FORMAT (JSON only, no markdown)
{{
  "status": "sufficient" or "insufficient_data",
  "required_data_points": [
    {{
      "name": "descriptive name of data needed",
      "column_mapping": "[schema].[table].[column]" or "DERIVED: expression" or null,
      "found": true or false,
      "reasoning": "why this data point is needed and how it can be obtained"
    }}
  ],
  "missing_data_points": [
    {{
      "name": "descriptive name of missing data",
      "column_mapping": null,
      "found": false,
      "reasoning": "why this is needed but cannot be obtained from available columns"
    }}
  ],
  "search_suggestions": ["term1", "term2", "term3"],
  "analysis": "Brief explanation of the validation result"
}}

### CRITICAL RULES
- status: "sufficient" if data points are directly available OR computable from existing columns
- status: "insufficient_data" ONLY if the required BASE DATA truly does not exist
- For "top selling products": If you have product info + quantity/price columns -> SUFFICIENT
- For aggregations (sum, count, avg): If base columns exist -> SUFFICIENT  
- For rankings (top N, best, worst): Standard capability -> SUFFICIENT
- Do NOT require explicit pre-calculated columns when code can compute them
- The question is: "Do we have the RAW DATA?" not "Do we have the exact column name?"
- search_suggestions: only needed if status is "insufficient_data"
"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a database schema validator. Output valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Log the interaction
            log_messages = [
                {"role": "system", "content": "You are a database schema validator. Output valid JSON only."},
                {"role": "user", "content": prompt}
            ]
            log_llm_interaction(log_messages, response.choices[0].message.content)
            
            return result
            
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse schema sufficiency response as JSON: {e}")
            # Return sufficient to avoid blocking generation on parse errors
            return {
                "status": "sufficient",
                "required_data_points": [],
                "missing_data_points": [],
                "search_suggestions": [],
                "analysis": f"Validation skipped due to parse error: {e}"
            }
        except Exception as e:
            logging.error(f"Error in schema sufficiency check: {e}")
            return {
                "status": "sufficient",
                "required_data_points": [],
                "missing_data_points": [],
                "search_suggestions": [],
                "analysis": f"Validation skipped due to error: {e}"
            }

    def validate_schema_with_join_paths(self, user_query: str, schemas: List[Any], code_type: str = "sql") -> Dict[str, Any]:
        """
        Enhanced validation with join-path verification (Stage A + Stage B).
        
        Replaces check_schema_sufficiency for new validation flow while 
        keeping the old method for backward compatibility.
        """
        import json
        from app.services.schema_context_utils import (
            build_sufficiency_schema_text, get_derivation_guidance, 
            get_temporal_guidance, prioritize_base_tables
        )
        
        # Mock mode for development
        if self.client is None:
            return {
                "status": "sufficient",
                "join_path": None,
                "validation_details": [],
                "missing_logic": None,
                "search_suggestions": [],
                "analysis": "Mock validation - schema assumed sufficient"
            }
        
        # Prioritize base tables over views for temporal queries
        filtered_schemas = prioritize_base_tables(schemas)
        
        schema_text = build_sufficiency_schema_text(filtered_schemas)
        derivation_guidance = get_derivation_guidance(code_type)
        temporal_guidance = get_temporal_guidance(filtered_schemas)
        
        prompt = _build_join_path_validation_prompt(
            user_query, schema_text, code_type, temporal_guidance, derivation_guidance
        )
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a database schema validator. Output valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Log the interaction
            log_messages = [
                {"role": "system", "content": "You are a database schema validator. Output valid JSON only."},
                {"role": "user", "content": prompt}
            ]
            log_llm_interaction(log_messages, response.choices[0].message.content)
            
            return result
            
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse join-path validation response as JSON: {e}")
            return {
                "status": "sufficient",
                "join_path": None,
                "validation_details": [],
                "missing_logic": None,
                "search_suggestions": [],
                "analysis": f"Validation skipped due to parse error: {e}"
            }
        except Exception as e:
            logging.error(f"Error in join-path validation: {e}")
            return {
                "status": "sufficient",
                "join_path": None,
                "validation_details": [],
                "missing_logic": None,
                "search_suggestions": [],
                "analysis": f"Validation skipped due to error: {e}"
            }

    def generate_sql_with_context(self, query: str, context_text: str) -> str:
        # Mock mode for development
        if self.client is None:
            return f"SELECT TOP 10 * FROM users WHERE name LIKE '%{query.split()[-1]}%'"

        system_prompt = f"""You are an expert T-SQL developer for Microsoft SQL Server.

Your goal is to generate a valid T-SQL SELECT query to answer the user's question.

{context_text}

"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            temperature=0  # Deterministic SQL generation
        )

        sql = response.choices[0].message.content
        
        # Log the interaction
        log_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ]
        log_llm_interaction(log_messages, sql)
        
        # Strip markdown code blocks and extract SQL
        sql = sql.replace("```sql", "").replace("```", "").strip()
        return sql

    def _build_system_prompt(self, query: str, context: DiscoveryContext) -> str:
        northwind_context = "Northwind Database is a sales database for imported and exported specialty foods. It consists of the following data: Customers & Orders, Products & Inventory, Suppliers, Employees, and Shipping & Logistics."

        prompt = ["You are an expert T-SQL developer for Microsoft SQL Server."]
        prompt.append(northwind_context)
        prompt.append("")
        prompt.append("Your goal is to generate a valid T-SQL SELECT query to answer the user's question.")
        prompt.append("Return ONLY the SQL query, no explanation.")
        
        # Add Schema Context
        prompt.append("\n### Database Schema:")
        for table in context.relevant_tables:
            prompt.append(f"Table: {table.schema_name}.{table.table_name}")
            prompt.append(f"Description: {table.description}")
            prompt.append("Columns:")
            for col in table.columns:
                prompt.append(f"  - {col.name} ({col.data_type}): {col.description or ''}")
            prompt.append("") # spacer
            
        # Add Knowledge Base examples (similar queries)
        if context.similar_queries:
            prompt.append("\n### Knowledge Base Examples:")
            for item in context.similar_queries:
                prompt.append(f"Q: {item.get('question')}")
                prompt.append(f"~~~sql\n{item.get('sql_query')}\n~~~")
                prompt.append("")
                
        # Glossary/Values
        # (Optional: Add glossary terms if we had them implemented)
        
        prompt.append("\n### Rules:")
        prompt.append("1. Use T-SQL syntax (e.g., TOP, DATEPART).")
        prompt.append("2. Handle Chinese characters with N'' prefix.")
        prompt.append("3. Do not use DDL/DML (only SELECT).")
        prompt.append("4. ONLY use columns that exist in the provided table schemas above.")
        prompt.append("5. If you cannot find a suitable column for the query, respond with 'COLUMN_VALIDATION_ERROR: Cannot find column [column_name] in any provided table'")
        prompt.append("6. Do not invent or assume column names - they must exist in the schema.")

        return "\n".join(prompt).replace("\\n", "\n")

    def chat(self, prompt: str, temperature: float = 0) -> str:
        # Mock mode for development
        if self.client is None:
            return "# Mock Code\nprint('Hello World')"

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=temperature
        )

        content = response.choices[0].message.content
        
        # Log the interaction
        log_messages = [
            {"role": "user", "content": prompt}
        ]
        log_llm_interaction(log_messages, content)
        
        # Basic cleanup: remove markdown code blocks if present
        return content

    def chat_completion(self, messages: List[Dict[str, str]], temperature: float = 0) -> str:
        # Mock mode for development
        if self.client is None:
            return "Mock response: Valid chat completion."

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature
        )
        return response.choices[0].message.content

    def extract_tables_from_sql(self, sql_queries: List[str]) -> List[str]:
        # Mock mode
        if self.client is None:
            return ["dbo.Orders", "dbo.Customers"]

        if not sql_queries:
            return []

        queries_text = "\n".join([f"Query {i+1}: {q}" for i, q in enumerate(sql_queries)])
        
        prompt = f"""You are a SQL parser.
        
Extract all fully qualified table names (e.g., [dbo].[Table] or schema.Table) from the following SQL scripts.
Ignore partial names or aliases. Return ONLY a comma-separated list of unique table names.

SQL SCRIPTS:
{queries_text}

OUTPUT FORMAT:
schema.table, schema.table2
"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a SQL parser."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        
        item_str = response.choices[0].message.content.strip()
        log_llm_interaction([{"role": "user", "content": prompt}], item_str)
        
        # Clean and parse
        tables = []
        if item_str and "NONE" not in item_str.upper():
            parts = [t.strip() for t in item_str.split(',')]
            for p in parts:
                # Remove brackets if present
                clean_name = p.replace('[', '').replace(']', '').strip()
                if clean_name:
                    tables.append(clean_name)
                    
        return list(set(tables))
        
    def suggest_intermediate_tables(self, selected_tables: List[str], user_query: str) -> List[str]:
        # Mock mode
        if self.client is None:
            return ["dbo.Orders", "dbo.Order Details"] # Mock glue tables
            
        tables_str = ", ".join(selected_tables)
        
        prompt = f"""You are a Database expert.
        
I have selected the following tables based on the user's query:
{tables_str}

User Query: "{user_query}"

Analyze if these tables are sufficient to answer the query, or if I am missing "intermediate" or "glue" tables to join them.
For example, if I have [Customers] and [Products], I likely need [Orders] and [OrderDetails] to join them.

Return a comma-separated list of MISSING intermediate tables only.
If no extra tables are needed, return "NONE".

Output Format:
schema.Table1, schema.Table2
"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a database expert."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        
        item_str = response.choices[0].message.content.strip()
        log_llm_interaction([{"role": "user", "content": prompt}], item_str)
        
        suggestions = []
        if item_str and "NONE" not in item_str.upper():
            parts = [t.strip() for t in item_str.split(',')]
            for p in parts:
                clean = p.replace('[', '').replace(']', '').strip()
                if clean and clean not in selected_tables:
                   suggestions.append(clean)
                   
        return suggestions

    def extract_filter_values(self, query: str) -> List[str]:
        # Mock mode
        if self.client is None:
            return []
            
        prompt = f"Identify all specific filter values or entities in this query (e.g., countries, categories, names). Query: {query}. Return as a comma-separated list."
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a data extractor."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        
        item_str = response.choices[0].message.content.strip()
        log_llm_interaction([{"role": "user", "content": prompt}], item_str)
        
        if not item_str or "NONE" in item_str.upper():
            return []
            
        return [val.strip() for val in item_str.split(",") if val.strip()]

class LiteLLMService(LLMServiceBase):
    def __init__(self):
        from app.services.settings_service import load_settings
        
        # Load dynamic settings
        agent_settings = load_settings()
        llm_config = agent_settings.llm_config
        

        # Prioritize settings file over env vars
        self.api_key = llm_config.llm_api_key or settings.OPENAI_API_KEY
        self.base_url = llm_config.llm_endpoint
        self.model = llm_config.llm_model
        
        # If using a custom endpoint, ensure litellm knows to use generic OpenAI protocol
        # unless a specific provider is already defined in the model name.
        if self.base_url and "/" not in self.model:
            self.model = f"openai/{self.model}"
        
        # Configure litellm
        if self.api_key:
            litellm.api_key = self.api_key
        if self.base_url:
            litellm.api_base = self.base_url
            
    def generate_sql(self, query: str, context: DiscoveryContext) -> str:
        system_prompt = self._build_system_prompt(query, context)

        try:
            response = litellm.completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                temperature=0,
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=60
            )
            
            sql = response.choices[0].message.content
            
            # Log the interaction
            log_messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ]
            log_llm_interaction(log_messages, sql)

            # Basic cleanup
            sql = sql.replace("```sql", "").replace("```", "").strip()
            return sql
        except Exception as e:
            print(f"LiteLLM Error in generate_sql: {e}")
            raise e

    def validate_schema_references(self, schemas: List[Any], user_query: str) -> str:
        # Build schema descriptions
        schema_descriptions = []
        table_names_present = []
        
        for schema in schemas:
            schema_name = getattr(schema, 'schema_name', 'dbo')
            table_name = getattr(schema, 'table_name', '')
            description = getattr(schema, 'description', '')
            
            table_names_present.append(f"[{schema_name}].[{table_name}]")
            schema_descriptions.append(f"{description}\n")
        
        schemas_text = "\n".join(schema_descriptions).replace("\\n", "\n")
        present_tables = "\n".join([f"- {t}" for t in table_names_present])
        
        validation_prompt = f"""You are a database schema analyzer for SQL Server.

### PROVIDED TABLE SCHEMAS:
{schemas_text}

### TABLES CURRENTLY PRESENT:
{present_tables}

### USER QUERY:
{user_query}

### TASK:
Analyze the column descriptions in the provided schemas for references to other tables (foreign key relationships). 
Look for patterns like:
- "References [TableName]"
- "FK to [TableName]"
- "Foreign key to [schema].[table]"
- "Links to [TableName]"
- Or any mention of another table name in the relationship context

For each table referenced in the descriptions, check if that table is in the "TABLES CURRENTLY PRESENT" list above.

**IMPORTANT RULES:**
1. Only flag tables that are EXPLICITLY referenced as foreign keys or relationships in column descriptions
2. Do NOT flag tables mentioned casually or in general text
3. Use exact table names from references (including schema prefix if mentioned)
4. If a referenced table is already in the present list, do NOT flag it as missing

### OUTPUT FORMAT:
Return your analysis in EXACTLY this format:

SCHEMA_COMPLETE: YES or NO
MISSING_TABLES: table1, table2, table3 (comma-separated, or "NONE" if complete)
ANALYSIS: Brief explanation of what's missing and why
"""
        try:
            response = litellm.completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a database schema analyzer. Analyze schemas and identify missing referenced tables."},
                    {"role": "user", "content": validation_prompt}
                ],
                temperature=0,
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=30
            )
            
            content = response.choices[0].message.content
            
            # Log the interaction
            log_messages = [
                {"role": "system", "content": "You are a database schema analyzer. Analyze schemas and identify missing referenced tables."},
                {"role": "user", "content": validation_prompt}
            ]
            log_llm_interaction(log_messages, content)
            
            return content
        except Exception as e:
            return f"SCHEMA_COMPLETE: YES\nMISSING_TABLES: NONE\nANALYSIS: Error in validation: {str(e)}"

    def check_schema_sufficiency(self, user_query: str, schemas: List[Any], code_type: str = "sql") -> Dict[str, Any]:
        """
        Pre-flight check: Validate if the provided schemas contain all columns 
        needed to answer the user's query.
        
        Args:
            user_query: The user's natural language request
            schemas: List of TableSchema objects with column definitions
            code_type: "sql" or "python" - affects the analysis context
            
        Returns:
            Dict with keys: status, required_data_points, missing_data_points, 
                           search_suggestions, analysis
        """
        import json
        import logging
        
        # Build schema text with column details
        schema_text_parts = []
        for t in schemas:
            schema_name = getattr(t, 'schema_name', 'dbo')
            table_name = getattr(t, 'table_name', '')
            columns = getattr(t, 'columns', [])
            description = getattr(t, 'description', '')
            
            if columns:
                # Use structured column info if available
                cols = ", ".join([f"{c.name} ({c.data_type})" for c in columns])
                schema_text_parts.append(f"[{schema_name}].[{table_name}]: {cols}")
            elif description:
                # Fall back to description (which contains markdown with column details)
                # Include the full description as it contains column information
                schema_text_parts.append(f"[{schema_name}].[{table_name}]:\n{description}")
            else:
                schema_text_parts.append(f"[{schema_name}].[{table_name}]: (no column information available)")
        
        schema_text = "\n\n".join(schema_text_parts)
        
        # Determine language-specific guidance
        if code_type.lower() == "python":
            derivation_guidance = """### DERIVABLE VALUES - Mark as "found: true" if computable from existing columns:
Python/pandas can compute virtually ANY derived value from raw columns:
- **Aggregations**: df.sum(), df.mean(), df.count(), df.groupby().agg() 
- **Calculated fields**: df['amount'] = df['quantity'] * df['price']
- **Rankings**: df.nlargest(), df.sort_values(), df.rank()
- **Date operations**: pd.to_datetime(), dt.year, dt.month, date arithmetic
- **String operations**: str.contains(), str.upper(), str.split()
- **Statistical analysis**: correlation, percentiles, distributions
- **Pivot tables**: df.pivot_table(), df.crosstab()
- **Window functions**: df.rolling(), df.expanding(), df.shift()

IMPORTANT: If the base columns exist, Python can derive almost anything through code."""
        else:
            derivation_guidance = """### DERIVABLE VALUES - Mark as "found: true" if computable from existing columns:
- **Aggregations**: COUNT(*), SUM(column), AVG(column), MIN/MAX - always available
- **Calculated fields**: quantity * unit_price = amount, date differences, etc.
- **Rankings**: TOP N, ORDER BY, ROW_NUMBER() - always available
- **Date extractions**: YEAR(), MONTH(), DATEPART() from date columns
- **String operations**: CONCAT(), SUBSTRING(), UPPER/LOWER from string columns
- **Conditional logic**: CASE WHEN, IIF() on existing columns
- **Standard joins**: If related tables exist, join operations are available"""

        prompt = f"""### ROLE
You are a database schema analyst performing a pre-flight validation check.

### TASK
Analyze the user's request and determine if the provided database schemas contain 
the columns necessary to answer it - either directly or through computation/derivation.

### CODE TYPE
{code_type.upper()} - Consider what calculations are possible in this language.

### USER REQUEST
{user_query}

### AVAILABLE SCHEMAS
{schema_text}

### VALIDATION PROTOCOL
1. Identify the core data points required to answer the user's request
2. For each data point, check if it can be satisfied by:
   a) A direct column match in the provided schemas, OR
   b) A DERIVABLE/COMPUTABLE value from existing columns using {code_type.upper()} capabilities

{derivation_guidance}

### OUTPUT FORMAT (JSON only, no markdown)
{{
  "status": "sufficient" or "insufficient_data",
  "required_data_points": [
    {{
      "name": "descriptive name of data needed",
      "column_mapping": "[schema].[table].[column]" or "DERIVED: expression" or null,
      "found": true or false,
      "reasoning": "why this data point is needed and how it can be obtained"
    }}
  ],
  "missing_data_points": [
    {{
      "name": "descriptive name of missing data",
      "column_mapping": null,
      "found": false,
      "reasoning": "why this is needed but cannot be obtained from available columns"
    }}
  ],
  "search_suggestions": ["term1", "term2", "term3"],
  "analysis": "Brief explanation of the validation result"
}}

### CRITICAL RULES
- status: "sufficient" if data points are directly available OR computable from existing columns
- status: "insufficient_data" ONLY if the required BASE DATA truly does not exist
- For "top selling products": If you have product info + quantity/price columns -> SUFFICIENT
- For aggregations (sum, count, avg): If base columns exist -> SUFFICIENT  
- For rankings (top N, best, worst): Standard capability -> SUFFICIENT
- Do NOT require explicit pre-calculated columns when code can compute them
- The question is: "Do we have the RAW DATA?" not "Do we have the exact column name?"
- search_suggestions: only needed if status is "insufficient_data"
"""
        
        try:
            response = litellm.completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a database schema validator. Output valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                response_format={"type": "json_object"},
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=30
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Log the interaction
            log_messages = [
                {"role": "system", "content": "You are a database schema validator. Output valid JSON only."},
                {"role": "user", "content": prompt}
            ]
            log_llm_interaction(log_messages, response.choices[0].message.content)
            
            return result
            
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse schema sufficiency response as JSON: {e}")
            return {
                "status": "sufficient",
                "required_data_points": [],
                "missing_data_points": [],
                "search_suggestions": [],
                "analysis": f"Validation skipped due to parse error: {e}"
            }
        except Exception as e:
            logging.error(f"Error in schema sufficiency check: {e}")
            return {
                "status": "sufficient",
                "required_data_points": [],
                "missing_data_points": [],
                "search_suggestions": [],
                "analysis": f"Validation skipped due to error: {e}"
            }

    def validate_schema_with_join_paths(self, user_query: str, schemas: List[Any], code_type: str = "sql") -> Dict[str, Any]:
        """
        Enhanced validation with join-path verification (Stage A + Stage B).
        
        Replaces check_schema_sufficiency for new validation flow while 
        keeping the old method for backward compatibility.
        """
        import json
        from app.services.schema_context_utils import (
            build_sufficiency_schema_text, get_derivation_guidance, 
            get_temporal_guidance, prioritize_base_tables
        )
        
        # Prioritize base tables over views for temporal queries
        filtered_schemas = prioritize_base_tables(schemas)
        
        schema_text = build_sufficiency_schema_text(filtered_schemas)
        derivation_guidance = get_derivation_guidance(code_type)
        temporal_guidance = get_temporal_guidance(filtered_schemas)
        
        prompt = _build_join_path_validation_prompt(
            user_query, schema_text, code_type, temporal_guidance, derivation_guidance
        )
        
        try:
            response = litellm.completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a database schema validator. Output valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                response_format={"type": "json_object"},
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=30
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Log the interaction
            log_messages = [
                {"role": "system", "content": "You are a database schema validator. Output valid JSON only."},
                {"role": "user", "content": prompt}
            ]
            log_llm_interaction(log_messages, response.choices[0].message.content)
            
            return result
            
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse join-path validation response as JSON: {e}")
            return {
                "status": "sufficient",
                "join_path": None,
                "validation_details": [],
                "missing_logic": None,
                "search_suggestions": [],
                "analysis": f"Validation skipped due to parse error: {e}"
            }
        except Exception as e:
            logging.error(f"Error in join-path validation: {e}")
            return {
                "status": "sufficient",
                "join_path": None,
                "validation_details": [],
                "missing_logic": None,
                "search_suggestions": [],
                "analysis": f"Validation skipped due to error: {e}"
            }

    def generate_sql_with_context(self, query: str, context_text: str) -> str:
        system_prompt = f"""You are an expert T-SQL developer for Microsoft SQL Server.

Your goal is to generate a valid T-SQL SELECT query to answer the user's question.

{context_text}

"""
        try:
            response = litellm.completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                temperature=0,
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=60
            )
            
            sql = response.choices[0].message.content
            
            # Log the interaction
            log_messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ]
            log_llm_interaction(log_messages, sql)
            
            sql = sql.replace("```sql", "").replace("```", "").strip()
            return sql
        except Exception as e:
            print(f"LiteLLM Error in generate_sql_with_context: {e}")
            raise e

    def _build_system_prompt(self, query: str, context: DiscoveryContext) -> str:
        # Reuse the logic from OpenAILLMService (or verify it can be shared)
        # For now, duplicate or delegate. 
        # Easier to duplicate to avoid class coupling issues for this Refactor step, 
        # but cleaner to have a helper. 
        # Let's use the same logic by copying the implementation for safety and independence.
        
        northwind_context = "Northwind Database is a sales database for imported and exported specialty foods. It consists of the following data: Customers & Orders, Products & Inventory, Suppliers, Employees, and Shipping & Logistics."

        prompt = ["You are an expert T-SQL developer for Microsoft SQL Server."]
        prompt.append(northwind_context)
        prompt.append("")
        prompt.append("Your goal is to generate a valid T-SQL SELECT query to answer the user's question.")
        prompt.append("Return ONLY the SQL query, no explanation.")
        
        # Add Schema Context
        prompt.append("\n### Database Schema:")
        for table in context.relevant_tables:
            prompt.append(f"Table: {table.schema_name}.{table.table_name}")
            prompt.append(f"Description: {table.description}")
            prompt.append("Columns:")
            for col in table.columns:
                prompt.append(f"  - {col.name} ({col.data_type}): {col.description or ''}")
            prompt.append("") # spacer
            
        # Add Knowledge Base examples (similar queries)
        if context.similar_queries:
            prompt.append("\n### Knowledge Base Examples:")
            for item in context.similar_queries:
                prompt.append(f"Q: {item.get('question')}")
                prompt.append(f"~~~sql\n{item.get('sql_query')}\n~~~")
                prompt.append("")
        
        prompt.append("\n### Rules:")
        prompt.append("1. Use T-SQL syntax (e.g., TOP, DATEPART).")
        prompt.append("2. Handle Chinese characters with N'' prefix.")
        prompt.append("3. Do not use DDL/DML (only SELECT).")
        prompt.append("4. ONLY use columns that exist in the provided table schemas above.")
        prompt.append("5. If you cannot find a suitable column for the query, respond with 'COLUMN_VALIDATION_ERROR: Cannot find column [column_name] in any provided table'")
        prompt.append("6. Do not invent or assume column names - they must exist in the schema.")

        return "\n".join(prompt).replace("\\n", "\n")

    def chat(self, prompt: str, temperature: float = 0) -> str:
        try:
            response = litellm.completion(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=60
            )
            
            content = response.choices[0].message.content
            
            # Log the interaction
            log_messages = [
                {"role": "user", "content": prompt}
            ]
            log_llm_interaction(log_messages, content)
            

            content = content.replace("```r", "").replace("```sas", "").replace("```", "").strip()
            return content
        except Exception as e:
            print(f"LiteLLM Error in chat: {e}")
            raise e

    def chat_completion(self, messages: List[Dict[str, str]], temperature: float = 0) -> str:
        try:
            response = litellm.completion(
                model=self.model,
                messages=messages,
                temperature=temperature,
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=60
            )
            
            content = response.choices[0].message.content
            log_llm_interaction(messages, content)
            
            return content
        except Exception as e:
            print(f"LiteLLM Error in chat_completion: {e}")
            raise e

    def extract_tables_from_sql(self, sql_queries: List[str]) -> List[str]:
        if not sql_queries:
            return []

        queries_text = "\n".join([f"Query {i+1}: {q}" for i, q in enumerate(sql_queries)])
        
        prompt = f"""You are a SQL parser.
        
Extract all fully qualified table names (e.g., [dbo].[Table] or schema.Table) from the following SQL scripts.
Ignore partial names or aliases. Return ONLY a comma-separated list of unique table names.

SQL SCRIPTS:
{queries_text}

OUTPUT FORMAT:
schema.table, schema.table2
"""

        try:
            response = litellm.completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a SQL parser."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=30
            )
            
            item_str = response.choices[0].message.content.strip()
            log_llm_interaction([{"role": "user", "content": prompt}], item_str)
            
            # Clean and parse
            tables = []
            if item_str and "NONE" not in item_str.upper():
                parts = [t.strip() for t in item_str.split(',')]
                for p in parts:
                    clean_name = p.replace('[', '').replace(']', '').strip()
                    if clean_name:
                        tables.append(clean_name)
                        
            return list(set(tables))
        except Exception as e:
            print(f"LiteLLM Error in extract_tables_from_sql: {e}")
            return []

    def suggest_intermediate_tables(self, selected_tables: List[str], user_query: str) -> List[str]:
        tables_str = ", ".join(selected_tables)
        
        prompt = f"""You are a Database expert.
        
I have selected the following tables based on the user's query:
{tables_str}

User Query: "{user_query}"

Analyze if these tables are sufficient to answer the query, or if I am missing "intermediate" or "glue" tables to join them.
For example, if I have [Customers] and [Products], I likely need [Orders] and [OrderDetails] to join them.

Return a comma-separated list of MISSING intermediate tables only.
If no extra tables are needed, return "NONE".

Output Format:
schema.Table1, schema.Table2
"""
        try:
            response = litellm.completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a database expert."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=30
            )
            
            item_str = response.choices[0].message.content.strip()
            # Log it
            log_llm_interaction([{"role": "user", "content": prompt}], item_str)
            
            suggestions = []
            if item_str and "NONE" not in item_str.upper():
                parts = [t.strip() for t in item_str.split(',')]
                for p in parts:
                    clean = p.replace('[', '').replace(']', '').strip()
                    if clean and clean not in selected_tables:
                        suggestions.append(clean)
            
            return suggestions
        except Exception as e:
            print(f"LiteLLM Error in suggest_intermediate_tables: {e}")
            return []

    def extract_filter_values(self, query: str) -> List[str]:
        prompt = f"Identify all specific filter values or entities in this query (e.g., countries, categories, names). Query: {query}. Return as a comma-separated list."
        
        try:
            response = litellm.completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a data extractor."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=30
            )
            
            item_str = response.choices[0].message.content.strip()
            log_llm_interaction([{"role": "user", "content": prompt}], item_str)
            
            if not item_str or "NONE" in item_str.upper():
                return []
                
            return [val.strip() for val in item_str.split(",") if val.strip()]
        except Exception as e:
            error_msg = str(e)
            if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                logging.warning(f"LLM timeout in extract_filter_values after 30s: {e}")
            else:
                logging.error(f"LLM Error in extract_filter_values: {e}")
            return []

def _build_join_path_validation_prompt(user_query: str, schema_text: str, code_type: str, temporal_guidance: str, derivation_guidance: str) -> str:
    """Build the join-path validation prompt used by both LLM service implementations."""
    return f"""### ROLE
You are a database schema analyst performing a two-stage validation check.

### TASK
Analyze the user's request against the provided schemas using TWO validation stages:
- **Stage A (Structural):** Do the schemas contain the required columns/data points?
- **Stage B (Relational):** Can the required tables be joined together via a valid path?

### CODE TYPE
{code_type.upper()} - Consider what calculations are possible in this language.

### USER REQUEST
{user_query}

### AVAILABLE SCHEMAS
{schema_text}
{temporal_guidance}

### VALIDATION PROTOCOL

**Stage A - Structural Check:**
1. Identify the core data points required to answer the user's request
2. For each data point, check if it exists directly or can be derived
3. If ANY required base data is truly missing -> status: "insufficient_data"

**Stage B - Relational Check (only if Stage A passes):**
1. If the query requires data from multiple tables, verify a join path exists
2. Look for shared columns (especially columns ending in 'ID' marked [FK])
3. Trace the path: Table_A -> shared_key -> Table_B -> shared_key -> Table_C
4. If tables cannot be connected -> status: "insufficient_joins"

{derivation_guidance}

### OUTPUT FORMAT (JSON only, no markdown)
{{
  "status": "sufficient" or "insufficient_data" or "insufficient_joins",
  "join_path": "TableA -> TableB ON ColumnX -> TableC ON ColumnY" or null,
  "validation_details": [
    {{
      "requirement": "descriptive name of what's needed",
      "mapping": "[schema].[table].[column]" or "DERIVED: expression" or null,
      "found": true or false,
      "reason": "explanation"
    }}
  ],
  "missing_logic": "explanation of what join path is missing" or null,
  "search_suggestions": ["term1", "term2"],
  "analysis": "Brief overall assessment"
}}

### CRITICAL RULES
- status: "sufficient" if all data points exist AND tables can be joined
- status: "insufficient_data" if required BASE DATA does not exist in any schema
- status: "insufficient_joins" if data exists but tables CANNOT be connected
- join_path: REQUIRED when query involves 2+ tables, null for single-table queries
- For single-table queries: skip Stage B, just report Stage A result
- Do NOT require pre-calculated columns when {code_type.upper()} can compute them
- The question is: "Do we have the RAW DATA and can we JOIN it?" not "Do we have the exact column name?"
- search_suggestions: only populate if status is NOT "sufficient"
"""


def get_llm_service() -> LLMServiceBase:
    return LiteLLMService()

def fetch_available_models(endpoint: str, api_key: str = None) -> List[Any]:
    """
    Fetch available models from an OpenAI-compatible endpoint.
    """
    try:
        from app.core.config import settings
        
        # Use provided key or fallback to env var
        final_api_key = api_key or settings.OPENAI_API_KEY
        
        if not final_api_key:
            # Some local endpoints (like standard Ollama) might not need a key, but OpenAI client requires one.
            # We can use a dummy key if strictly necessary, but let's see.
            final_api_key = "dummy-key"
            
        client = OpenAI(base_url=endpoint, api_key=final_api_key)
        response = client.models.list()
        
        # Return simplified list
        return [{"id": m.id, "name": m.id} for m in response.data]
    except Exception as e:
        print(f"Failed to fetch models: {e}")
        # Return empty list or raise? Let's return empty and let caller handle.
        # But caller might want to know error. 
        raise e
