"""
Service for enhancing table and column descriptions using AI.
Combines markdown parsing, database schema queries, and LLM generation.
"""

import re
import json
import logging
from typing import Dict, Any, Optional, List
from sqlalchemy import text
from app.core.database import get_db_engine
from app.services.llm_service import get_llm_service

logger = logging.getLogger(__name__)


class SchemaEnhancementService:
    """Service to enhance database schema documentation using AI."""
    
    def __init__(self):
        self.llm_service = get_llm_service()
        self.db_engine = get_db_engine()
    
    def enhance_schema(
        self, 
        file_path: str, 
        current_content: str, 
        user_context: Optional[str] = None
    ) -> str:
        """
        Main orchestration method to enhance schema descriptions.
        
        Args:
            file_path: Path to the markdown file being edited
            current_content: Current markdown content
            user_context: Optional user-provided context (URLs, notes, etc.)
            
        Returns:
            Enhanced markdown content with improved descriptions
        """
        logger.info(f"Starting schema enhancement for {file_path}")
        
        # Step 1: Parse markdown to extract table info
        table_info = self._parse_markdown(current_content)
        logger.debug(f"Parsed table info: {table_info['table_name']}")
        
        # Step 2: Query database for live schema (if table exists)
        db_schema = None
        if table_info.get('schema_name') and table_info.get('table_name'):
            try:
                db_schema = self._get_database_schema(
                    table_info['schema_name'],
                    table_info['table_name']
                )
                logger.debug(f"Retrieved DB schema with {len(db_schema.get('columns', []))} columns")
            except Exception as e:
                logger.warning(f"Could not retrieve database schema: {e}")
        
        # Step 3: Build LLM prompt
        prompt = self._build_enhancement_prompt(
            table_info,
            db_schema,
            user_context
        )
        
        # Step 4: Call LLM
        logger.info("Calling LLM for schema enhancement")
        llm_response = self.llm_service.chat(
            prompt=prompt,
            temperature=0.1
        )
        
        # Step 5: Parse LLM JSON response
        enhancements = self._parse_llm_response(llm_response)
        logger.debug(f"Received enhancements for {len(enhancements.get('columns', []))} columns")
        
        # Step 6: Apply enhancements to markdown
        enhanced_md = self._apply_enhancements(
            current_content,
            enhancements
        )
        
        logger.info("Schema enhancement completed successfully")
        return enhanced_md
    
    def _parse_markdown(self, content: str) -> Dict[str, Any]:
        """
        Extract table and column information from markdown.
        
        Parses:
        - Table name from "# Table: [schema].[table]"
        - Current table description
        - Column list with current descriptions from the markdown table
        
        Returns:
            Dict with table_name, schema_name, description, columns[]
        """
        result = {
            'table_name': None,
            'schema_name': None,
            'description': '',
            'columns': []
        }
        
        # Extract table name and schema from title
        # Pattern: # Table: [dbo].[TableName] or # **Table:** `[dbo].[TableName]`
        title_patterns = [
            r'#\s+Table:\s*\[(\w+)\]\.\[(\w+)\]',
            r'#\s+\*\*Table:\*\*\s*`\[(\w+)\]\.\[(\w+)\]`',
            r'#\s+\*\*Table:\*\*\s*\[(\w+)\]\.\[(\w+)\]',
        ]
        
        for pattern in title_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                result['schema_name'] = match.group(1)
                result['table_name'] = match.group(2)
                break
        
        # Extract description from the Description section
        # Look for text between "## Description" and next "##" heading
        desc_match = re.search(
            r'##\s+Description\s*\n(.*?)(?=\n##|\Z)',
            content,
            re.DOTALL | re.IGNORECASE
        )
        if desc_match:
            desc_text = desc_match.group(1).strip()
            # Remove the embedded table section if it exists
            desc_text = re.sub(
                r'#\s+\*\*Table:\*\*.*?---\s*$',
                '',
                desc_text,
                flags=re.DOTALL | re.MULTILINE
            )
            result['description'] = desc_text.strip()
        
        # Extract columns from markdown table
        # Pattern: | 1 | `ColumnName` | TYPE | Description here |
        # or: | 1 | ColumnName | TYPE | Description here |
        column_pattern = r'\|\s*(\d+)\s*\|\s*`?(\w+)`?\s*\|\s*([^|]+)\s*\|\s*([^|]*)\s*\|'
        
        for match in re.finditer(column_pattern, content):
            ord_num = match.group(1).strip()
            col_name = match.group(2).strip()
            data_type = match.group(3).strip()
            description = match.group(4).strip()
            
            result['columns'].append({
                'ord': ord_num,
                'name': col_name,
                'data_type': data_type,
                'description': description
            })
        
        logger.debug(f"Parsed {len(result['columns'])} columns from markdown")
        return result
    
    def _get_database_schema(self, schema: str, table: str) -> Dict[str, Any]:
        """
        Query SQL Server for live metadata.
        
        Retrieves:
        - Column names, data types, nullable
        - Primary keys
        - Foreign keys with references
        
        Returns:
            Dict with columns array containing metadata
        """
        query = text("""
            SELECT 
                c.COLUMN_NAME,
                c.DATA_TYPE,
                CASE 
                    WHEN c.CHARACTER_MAXIMUM_LENGTH IS NOT NULL 
                    THEN c.DATA_TYPE + '(' + CAST(c.CHARACTER_MAXIMUM_LENGTH AS VARCHAR) + ')'
                    WHEN c.NUMERIC_PRECISION IS NOT NULL
                    THEN c.DATA_TYPE + '(' + CAST(c.NUMERIC_PRECISION AS VARCHAR) + ',' + CAST(c.NUMERIC_SCALE AS VARCHAR) + ')'
                    ELSE c.DATA_TYPE
                END AS FULL_DATA_TYPE,
                c.IS_NULLABLE,
                c.ORDINAL_POSITION,
                CASE WHEN pk.COLUMN_NAME IS NOT NULL THEN 1 ELSE 0 END AS IS_PRIMARY_KEY
            FROM INFORMATION_SCHEMA.COLUMNS c
            LEFT JOIN (
                SELECT ku.COLUMN_NAME
                FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku 
                    ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME
                WHERE tc.TABLE_SCHEMA = :schema 
                    AND tc.TABLE_NAME = :table
                    AND tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
            ) pk ON c.COLUMN_NAME = pk.COLUMN_NAME
            WHERE c.TABLE_SCHEMA = :schema 
                AND c.TABLE_NAME = :table
            ORDER BY c.ORDINAL_POSITION
        """)
        
        # Query foreign keys separately
        fk_query = text("""
            SELECT 
                COL_NAME(fc.parent_object_id, fc.parent_column_id) AS COLUMN_NAME,
                OBJECT_SCHEMA_NAME(fc.referenced_object_id) AS REFERENCED_SCHEMA,
                OBJECT_NAME(fc.referenced_object_id) AS REFERENCED_TABLE,
                COL_NAME(fc.referenced_object_id, fc.referenced_column_id) AS REFERENCED_COLUMN
            FROM sys.foreign_key_columns fc
            JOIN sys.objects o ON fc.parent_object_id = o.object_id
            WHERE OBJECT_SCHEMA_NAME(fc.parent_object_id) = :schema
                AND OBJECT_NAME(fc.parent_object_id) = :table
        """)
        
        with self.db_engine.connect() as conn:
            # Get columns
            result = conn.execute(query, {"schema": schema, "table": table})
            columns = []
            for row in result:
                columns.append({
                    'name': row.COLUMN_NAME,
                    'data_type': row.FULL_DATA_TYPE,
                    'is_nullable': row.IS_NULLABLE == 'YES',
                    'ordinal_position': row.ORDINAL_POSITION,
                    'is_primary_key': bool(row.IS_PRIMARY_KEY)
                })
            
            # Get foreign keys
            fk_result = conn.execute(fk_query, {"schema": schema, "table": table})
            foreign_keys = {}
            for row in fk_result:
                foreign_keys[row.COLUMN_NAME] = {
                    'referenced_schema': row.REFERENCED_SCHEMA,
                    'referenced_table': row.REFERENCED_TABLE,
                    'referenced_column': row.REFERENCED_COLUMN
                }
            
            # Merge foreign key info into columns
            for col in columns:
                if col['name'] in foreign_keys:
                    col['foreign_key'] = foreign_keys[col['name']]
        
        return {'columns': columns}
    
    def _build_enhancement_prompt(
        self, 
        table_info: Dict, 
        db_schema: Optional[Dict], 
        user_context: Optional[str]
    ) -> str:
        """
        Build comprehensive prompt for LLM.
        
        Includes:
        - Task description
        - Current table and column descriptions
        - Live database schema metadata
        - User-provided context
        - JSON output format specification
        """
        # Format database schema info if available
        db_info = "Not available"
        if db_schema and db_schema.get('columns'):
            db_info = json.dumps(db_schema['columns'], indent=2)
        
        # Format current columns
        current_cols = json.dumps(table_info.get('columns', []), indent=2)
        
        prompt = f"""You are a database documentation expert. Your task is to enhance table and column descriptions for a SQL Server database.

**Current Table Information:**
- Schema: {table_info.get('schema_name', 'Unknown')}
- Table Name: {table_info.get('table_name', 'Unknown')}
- Current Table Description: {table_info.get('description', 'No description provided')}

**Database Schema Metadata (Live from Database):**
{db_info}

**Current Column Descriptions from Markdown:**
{current_cols}

**Additional Context from User:**
{user_context or 'None provided'}

**Instructions:**
1. Review the current table and column descriptions carefully
2. Use the database schema metadata (data types, keys, relationships) to inform your enhancements
3. If user context is provided (URLs, documentation, notes), incorporate relevant information
4. Write clear, concise, professional descriptions that explain the PURPOSE and MEANING of the data
5. For the table description:
   - Explain what the table stores and its business purpose
   - Mention key relationships if applicable
   - Keep it to 2-3 sentences
6. For each column description:
   - Explain the purpose and meaning of the data stored
   - Note if it's a primary key, foreign key, or has special constraints
   - For foreign keys, reference the related table explicitly
   - Be specific and actionable
   - Keep each description to 1-2 sentences
7. Return ONLY valid JSON (no markdown code blocks, no additional text)

**Required JSON Output Format:**
{{
  "table_description": "Enhanced table description here (2-3 sentences explaining purpose and business context)",
  "columns": [
    {{
      "column_name": "ColumnName1",
      "enhanced_description": "Enhanced description for this column"
    }},
    {{
      "column_name": "ColumnName2",
      "enhanced_description": "Enhanced description for this column"
    }}
  ]
}}

Remember: Return ONLY the JSON object, nothing else."""
        
        return prompt
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """
        Parse JSON from LLM response.
        
        Handles:
        - Potential markdown code blocks
        - Structure validation
        
        Returns:
            Dict with table_description and columns array
        """
        # Remove markdown code blocks if present
        cleaned = response.strip()
        if cleaned.startswith('```'):
            cleaned = re.sub(r'^```json?\s*\n', '', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'\n```\s*$', '', cleaned)
        
        try:
            data = json.loads(cleaned)
            
            # Validate structure
            if 'table_description' not in data:
                raise ValueError("Missing 'table_description' in LLM response")
            if 'columns' not in data or not isinstance(data['columns'], list):
                raise ValueError("Missing or invalid 'columns' array in LLM response")
            
            return data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"LLM response: {response}")
            raise ValueError(f"LLM returned invalid JSON: {str(e)}")
    
    def _apply_enhancements(
        self, 
        original_md: str, 
        enhancements: Dict[str, Any]
    ) -> str:
        """
        Apply enhanced descriptions to the markdown content.
        
        Replaces:
        1. Table description in the Description section
        2. Each column description in the markdown table
        
        Preserves all other markdown formatting.
        """
        enhanced_md = original_md
        
        # Step 1: Replace table description
        # Find the Description section and replace content between ## Description and next ##
        table_desc = enhancements.get('table_description', '').strip()
        if table_desc:
            # Pattern to find description section
            desc_pattern = r'(##\s+Description\s*\n)(.*?)(\n##|\Z)'
            
            def replace_description(match):
                section_header = match.group(1)
                next_section = match.group(3)
                
                # Build new description with the embedded table if it exists in original
                # First, check if original had the embedded table format
                original_desc = match.group(2)
                embedded_table_match = re.search(
                    r'(#\s+\*\*Table:\*\*.*?---\s*\n)',
                    original_desc,
                    re.DOTALL
                )
                
                if embedded_table_match:
                    # Keep the embedded table format
                    embedded_table = embedded_table_match.group(1)
                    new_content = f"{table_desc}\n{embedded_table}"
                else:
                    new_content = table_desc
                
                return f"{section_header}{new_content}\n{next_section}"
            
            enhanced_md = re.sub(
                desc_pattern,
                replace_description,
                enhanced_md,
                count=1,
                flags=re.DOTALL | re.IGNORECASE
            )
        
        # Step 2: Replace column descriptions in the markdown table
        # Pattern: | ord | `ColumnName` | TYPE | Description |
        for col_enhancement in enhancements.get('columns', []):
            col_name = col_enhancement.get('column_name', '')
            new_desc = col_enhancement.get('enhanced_description', '').strip()
            
            if not col_name or not new_desc:
                continue
            
            # Pattern to match the column row with flexible spacing and backticks
            # Captures: | ord | `ColName` or ColName | TYPE | old description |
            pattern = rf'\|(\s*\d+\s*\|)\s*`?{re.escape(col_name)}`?\s*\|([^|]+\|)\s*[^|]*\|'
            
            def replace_col_desc(match):
                ord_part = match.group(1)  # "1 |"
                type_part = match.group(2)  # "VARCHAR(50) |"
                return f"|{ord_part} `{col_name}` |{type_part} {new_desc} |"
            
            enhanced_md = re.sub(
                pattern,
                replace_col_desc,
                enhanced_md,
                count=1
            )
        
        return enhanced_md
