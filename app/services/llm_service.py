from abc import ABC, abstractmethod
from typing import List, Any, Dict
from app.models.schemas import DiscoveryContext
from app.core.config import settings
from openai import OpenAI

import litellm
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
        return validation_result

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
                api_key=self.api_key
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
                api_key=self.api_key
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
                api_key=self.api_key
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
                api_key=self.api_key
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
                api_key=self.api_key
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
                api_key=self.api_key
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
                api_key=self.api_key
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
                api_key=self.api_key
            )
            
            item_str = response.choices[0].message.content.strip()
            log_llm_interaction([{"role": "user", "content": prompt}], item_str)
            
            if not item_str or "NONE" in item_str.upper():
                return []
                
            return [val.strip() for val in item_str.split(",") if val.strip()]
        except Exception as e:
            print(f"LiteLLM Error in extract_filter_values: {e}")
            return []

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
