"""
Skills Service - Handles parsing and discovery of data sources from filesystem-based skill files
"""

import os
import re
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set
from collections import defaultdict

from app.models.schemas import (
    DataSource, DataGroup, TableSchema, ColumnInfo, RankedTable, SkillsDiscoveryResult
)


class SkillsService:
    """Service for managing skills-based data source discovery"""
    
    def __init__(self, skills_path: str = "skills/data-sources"):
        """
        Initialize the skills service
        
        Args:
            skills_path: Path to the skills directory (default: skills/data-sources)
        """
        self.skills_path = Path(skills_path)
        self._data_sources_cache: Optional[List[DataSource]] = None
        self._data_groups_cache: Optional[Dict[str, DataGroup]] = None
        self._schema_indices_cache: Optional[Dict[str, Dict]] = None
        self._object_indices_cache: Optional[Dict[str, Dict]] = None
        
    def load_data_sources_index(self) -> List[DataSource]:
        """
        Parse _index.md and return all data sources
        
        Returns:
            List of DataSource objects
        """
        if self._data_sources_cache is not None:
            return self._data_sources_cache
            
        index_path = self.skills_path / "_index.md"
        if not index_path.exists():
            return []
            
        data_sources = []
        content = index_path.read_text(encoding='utf-8')
        
        # Parse markdown sections for each data source
        # Pattern: ### DataSourceName followed by metadata
        sections = re.split(r'\n### ', content)
        
        for section in sections[1:]:  # Skip first section (header)
            lines = section.strip().split('\n')
            name = lines[0].strip()
            
            # Extract metadata
            type_match = re.search(r'\*\*Type:\*\*\s*(.+)', section)
            status_match = re.search(r'\*\*Status:\*\*\s*(.+)', section)
            desc_match = re.search(r'\*\*Description:\*\*\s*(.+)', section)
            keywords_match = re.search(r'\*\*Keywords:\*\*\s*(.+)', section)
            skill_file_match = re.search(r'\*\*Skill File:\*\*\s*\[(.+?)\]\((.+?)\)', section)
            source_id_match = re.search(r'\*\*Source ID:\*\*\s*(.+)', section)
            
            keywords = []
            if keywords_match:
                keywords_str = keywords_match.group(1)
                keywords = [k.strip() for k in keywords_str.split(',')]
            
            skill_file_path = None
            if skill_file_match:
                skill_file_path = skill_file_match.group(2)
            
            source_id = source_id_match.group(1).strip() if source_id_match else None
            if not source_id and skill_file_path:
                ds = self._parse_data_source_file(self.skills_path / skill_file_path)
                source_id = ds.source_id if ds else None
            
            data_source = DataSource(
                source_id=source_id,
                name=name,
                type=type_match.group(1).strip() if type_match else "Unknown",
                description=desc_match.group(1).strip() if desc_match else "",
                keywords=keywords,
                status=status_match.group(1).strip() if status_match else "Unknown",
                file_path=str(self.skills_path / skill_file_path) if skill_file_path else None
            )
            
            data_sources.append(data_source)
        
        self._data_sources_cache = data_sources
        return data_sources
    
    def load_all_data_groups(self) -> Dict[str, DataGroup]:
        """
        Load all _data-group.md files from the skills directory
        
        Returns:
            Dictionary mapping file path to DataGroup objects
        """
        if self._data_groups_cache is not None:
            return self._data_groups_cache
            
        data_groups = {}
        
        # Recursively find all _*-group.md files
        for group_file in self.skills_path.rglob("_*-group.md"):
            group = self._parse_data_group_file(group_file)
            if group:
                data_groups[str(group_file)] = group
        
        self._data_groups_cache = data_groups
        return data_groups
    
    def load_data_groups_for_source(self, data_source_name: str) -> List[DataGroup]:
        """
        Load data groups for a specific data source by reading .data-groups file
        
        Args:
            data_source_name: Name of the data source (e.g., "Northwind")
            
        Returns:
            List of DataGroup objects for this data source
        """
        # Convert data source name to slug format
        slug = re.sub(r'[^\w\s-]', '', data_source_name.lower()).replace(' ', '-')
        ds_dir = self.skills_path / slug
        
        if not ds_dir.exists():
            return []
        
        data_groups_file = ds_dir / ".data-groups"
        
        if not data_groups_file.exists():
            return []
        
        groups = []
        content = data_groups_file.read_text(encoding='utf-8')
        
        for line in content.strip().split('\n'):
            if not line.strip():
                continue
            
            # Parse format: "Group Name|_filename-group.md"
            if '|' in line:
                name, filename = line.split('|', 1)
                filename = filename.strip()
                
                # Load the group file
                group_file_path = ds_dir / "data-groups" / filename
                group = self._parse_data_group_file(group_file_path)
                
                if group:
                    groups.append(group)
        
        return groups
    
    def load_primary_data_source(self) -> Optional[DataSource]:
        """
        Load the primary data source from _data-source.md file
        
        Returns:
            DataSource object or None if not found
        """
        # Look for _data-source.md in any subdirectory
        data_source_files = list(self.skills_path.rglob("_data-source.md"))
        
        if not data_source_files:
            return None
        
        # For now, return the first one found (could be enhanced to support multiple)
        return self._parse_data_source_file(data_source_files[0])
    
    def _parse_data_source_file(self, file_path: Path) -> Optional[DataSource]:
        """
        Parse a _data-source.md file to extract metadata
        
        Args:
            file_path: Path to the _data-source.md file
            
        Returns:
            DataSource object or None if parsing fails
        """
        if not file_path.exists():
            return None
        
        content = file_path.read_text(encoding='utf-8')
        front_matter = self._parse_front_matter(content)
        
        # Extract metadata
        name_match = re.search(r'^#\s+(.+?)$', content, re.MULTILINE)
        type_match = re.search(r'\*\*Type:\*\*\s*(.+)', content)
        server_match = re.search(r'\*\*Server:\*\*\s*(.+)', content)
        database_match = re.search(r'\*\*Database:\*\*\s*(.+)', content)
        friendly_name_match = re.search(r'\*\*Friendly Name:\*\*\s*(.+)', content)
        keywords_match = re.search(r'\*\*Keywords:\*\*\s*(.+)', content)
        desc_section = re.search(r'## Description\s*\n(.*?)(?=\n##|\Z)', content, re.DOTALL)
        
        # Parse keywords
        keywords = []
        if keywords_match:
            keywords_str = keywords_match.group(1)
            keywords = [k.strip() for k in keywords_str.split(',')]
        
        # Build connection info
        connection_info = {}
        if server_match:
            connection_info['server'] = server_match.group(1).strip()
        if database_match:
            connection_info['database'] = database_match.group(1).strip()
        
        return DataSource(
            source_id=front_matter.get("source_id"),
            name=friendly_name_match.group(1).strip() if friendly_name_match else (name_match.group(1).strip() if name_match else "Unknown"),
            type=type_match.group(1).strip() if type_match else "Unknown",
            description=desc_section.group(1).strip() if desc_section else "",
            keywords=keywords,
            status="Active",
            connection_info=connection_info if connection_info else None,
            file_path=str(file_path)
        )

    def _parse_front_matter(self, content: str) -> Dict[str, str]:
        """
        Parse YAML-style front matter from markdown.
        Only supports simple key: value lines.
        """
        if not content.startswith("---"):
            return {}
        lines = content.splitlines()
        if not lines or lines[0].strip() != "---":
            return {}
        front_matter = {}
        for line in lines[1:]:
            if line.strip() == "---":
                break
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            front_matter[key.strip()] = value.strip()
        return front_matter
    
    def load_primary_data_source_by_name(self, name: str) -> Optional[DataSource]:
        """
        Load a specific data source by name from its _data-source.md file.
        
        Args:
            name: The data source name
            
        Returns:
            DataSource object or None if not found
        """
        slug = re.sub(r'[^\w\s-]', '', name.lower()).replace(' ', '-')
        ds_file = self.skills_path / slug / "_data-source.md"
        if ds_file.exists():
            return self._parse_data_source_file(ds_file)
        
        # Fallback: search all _data-source.md files
        for f in self.skills_path.rglob("_data-source.md"):
            ds = self._parse_data_source_file(f)
            if ds and ds.name.lower() == name.lower():
                return ds
        return None
    
    def _parse_data_group_file(self, file_path: Path) -> Optional[DataGroup]:
        """
        Parse a single _data-group.md file
        
        Args:
            file_path: Path to the _data-group.md file
            
        Returns:
            DataGroup object or None if parsing fails
        """
        if not file_path.exists():
            return None
            
        content = file_path.read_text(encoding='utf-8')
        
        # Extract metadata
        name_match = re.search(r'^#\s+(.+?)(?:\s+Group)?$', content, re.MULTILINE)
        data_source_match = re.search(r'\*\*Data Source:\*\*\s*(.+)', content)
        category_match = re.search(r'\*\*Category:\*\*\s*(.+)', content)
        keywords_match = re.search(r'\*\*Keywords:\*\*\s*(.+)', content)
        desc_section = re.search(r'## Description\s*\n(.*?)(?=\n##|\Z)', content, re.DOTALL)
        schema_notes_section = re.search(r'## Schema (?:Migration )?Notes\s*\n(.*?)(?=\n##|\Z)', content, re.DOTALL)
        
        # Extract table references
        # Pattern: **[TableName](../schemas/schema-name/file.md)** or **[TableName](../schemas/dbo/file.md)**
        table_matches = re.findall(r'\*\*\[(.+?)\]\((.+?\.md)\)\*\*', content)
        
        keywords = []
        if keywords_match:
            keywords_str = keywords_match.group(1)
            # Split by comma and clean up
            keywords = [k.strip() for k in keywords_str.split(',')]
        
        tables = []
        for table_name, table_path in table_matches:
            # Convert relative path to absolute
            # table_path is relative to the data-group file (e.g., "../schemas/dbo/dbo.Table.md")
            abs_path = (file_path.parent / table_path).resolve()
            tables.append(str(abs_path))
        
        return DataGroup(
            name=name_match.group(1).strip() if name_match else file_path.stem.replace('_', ' ').replace('-group', ''),
            data_source=data_source_match.group(1).strip() if data_source_match else "Unknown",
            description=desc_section.group(1).strip() if desc_section else "",
            keywords=keywords,
            tables=tables,
            schema_notes=schema_notes_section.group(1).strip() if schema_notes_section else None,
            category=category_match.group(1).strip() if category_match else None,
            file_path=str(file_path)
        )
    
    def search_data_groups_by_keywords(
        self,
        query: str,
        extract_keywords: bool = True,
        data_source_id: Optional[str] = None
    ) -> SkillsDiscoveryResult:
        """
        Keyword match against all _data-group.md files
        
        Args:
            query: User's natural language query
            extract_keywords: If True, extract keywords from query; otherwise use query as-is
            
        Returns:
            SkillsDiscoveryResult with matched groups and candidate tables
        """
        # Load all data groups
        all_groups = self.load_all_data_groups()

        # Optional filter by data source ID/name
        if data_source_id:
            resolved_source = self._resolve_data_source_name(data_source_id)
            if resolved_source:
                all_groups = {
                    file_path: group
                    for file_path, group in all_groups.items()
                    if group.data_source and group.data_source.lower() == resolved_source.lower()
                }
        
        # Extract keywords from query
        if extract_keywords:
            query_keywords = self._extract_keywords(query)
        else:
            query_keywords = [query.lower()]
        
        # Score each data group
        group_scores = {}
        for file_path, group in all_groups.items():
            score = self._score_group(group, query_keywords, query.lower())
            if score > 0:
                group_scores[file_path] = score
        
        # Sort groups by score
        sorted_groups = sorted(group_scores.items(), key=lambda x: x[1], reverse=True)
        
        # Get top matched groups
        matched_groups = []
        candidate_tables = []
        
        for file_path, score in sorted_groups[:10]:  # Top 10 groups
            group = all_groups[file_path]
            matched_groups.append(group)
            
            # Add tables from this group as candidates
            for table_path in group.tables:
                # Extract schema and table name from path
                table_name = Path(table_path).stem  # e.g., "dbo.Customers" from "dbo.Customers.md"
                schema_name, table = self._parse_table_name(table_name)
                
                candidate_tables.append(RankedTable(
                    schema_name=schema_name,
                    table_name=table,
                    score=score,
                    matched_by=["skills"],
                    data_source=group.data_source,
                    data_group=group.name,
                    file_path=table_path
                ))
        
        return SkillsDiscoveryResult(
            matched_groups=matched_groups,
            candidate_tables=candidate_tables,
            keywords_used=query_keywords
        )
    
    def _extract_keywords(self, query: str) -> List[str]:
        """
        Extract meaningful keywords from user query
        
        Args:
            query: User's natural language query
            
        Returns:
            List of keywords
        """
        # Convert to lowercase
        query_lower = query.lower()
        
        # Remove common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
                     'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during',
                     'show', 'me', 'get', 'find', 'list', 'all', 'what', 'which', 'who', 'where',
                     'when', 'how', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have',
                     'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
                     'i', 'want', 'need', 'data', 'information', 'records'}
        
        # Extract words (alphanumeric sequences)
        words = re.findall(r'\b[a-z0-9]+\b', query_lower)
        
        # Filter stop words and keep meaningful keywords
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        
        return keywords
    
    def _score_group(self, group: DataGroup, query_keywords: List[str], query_full: str) -> int:
        """
        Score a data group based on keyword matching
        
        Args:
            group: DataGroup to score
            query_keywords: Extracted keywords from query
            query_full: Full query string (lowercase)
            
        Returns:
            Score (higher is better)
        """
        score = 0
        
        # Combine all searchable text from the group
        searchable_text = " ".join([
            group.name.lower(),
            group.description.lower(),
            " ".join(group.keywords),
            group.data_source.lower(),
            group.category.lower() if group.category else "",
            group.schema_notes.lower() if group.schema_notes else ""
        ])
        
        # Score based on keyword matches
        for keyword in query_keywords:
            # Exact word match in keywords list (highest priority)
            if keyword in [k.lower() for k in group.keywords]:
                score += 10
            # Substring match in name (high priority)
            elif keyword in group.name.lower():
                score += 8
            # Substring match in description
            elif keyword in group.description.lower():
                score += 5
            # Substring match anywhere in searchable text
            elif keyword in searchable_text:
                score += 2
        
        # Bonus for multiple keyword matches (indicates relevance)
        matched_keywords = sum(1 for k in query_keywords if k in searchable_text)
        if matched_keywords > 1:
            score += matched_keywords * 2
        
        # Phrase matching bonus (if full query appears in description)
        if len(query_full) > 10 and query_full in searchable_text:
            score += 15
        
        return score
    
    def _parse_table_name(self, full_name: str) -> Tuple[str, str]:
        """
        Parse schema.table format
        
        Args:
            full_name: Table name in format "schema.table" or "table"
            
        Returns:
            Tuple of (schema_name, table_name)
        """
        if '.' in full_name:
            parts = full_name.split('.')
            return parts[0], parts[1]
        return "dbo", full_name
    
    def load_table_schemas(self, table_paths: List[str]) -> List[TableSchema]:
        """
        Read individual table .md files and parse into TableSchema objects
        
        Args:
            table_paths: List of file paths to table .md files OR table names (schema.table format)
            
        Returns:
            List of TableSchema objects
        """
        schemas = []
        
        for path_or_name in table_paths:
            # Check if it's a table name (schema.table) or a file path
            if '/' in path_or_name or '\\' in path_or_name or path_or_name.endswith('.md'):
                # It's a file path
                schema = self._parse_table_schema_file(Path(path_or_name))
            else:
                # It's a table name - find the file
                schema = self._find_and_parse_table(path_or_name)
            
            if schema:
                schemas.append(schema)
        
        return schemas
    
    def _find_and_parse_table(self, table_name: str) -> Optional[TableSchema]:
        """
        Find and parse a table by name (schema.table format)
        
        Args:
            table_name: Table name in format "schema.table" or just "table"
            
        Returns:
            TableSchema object or None if not found
        """
        # Parse schema.table format
        if '.' in table_name:
            parts = table_name.replace('[', '').replace(']', '').split('.')
            schema_name = parts[0]
            table = parts[1]
        else:
            schema_name = 'dbo'
            table = table_name.replace('[', '').replace(']', '')
        
        # Search for the table file
        # Pattern: skills/data-sources/{data-source}/schemas/{schema}/{schema}.{table}.md
        matches = list(self.skills_path.rglob(f"schemas/{schema_name}/{schema_name}.{table}.md"))
        
        if matches:
            return self._parse_table_schema_file(matches[0])
        
        return None
    
    def _parse_table_schema_file(self, file_path: Path) -> Optional[TableSchema]:
        """
        Parse a single table schema .md file
        
        Args:
            file_path: Path to the table .md file
            
        Returns:
            TableSchema object or None if parsing fails
        """
        if not file_path.exists():
            return None
            
        content = file_path.read_text(encoding='utf-8')
        
        # Extract table name from first line: # Table: [schema].[table]
        table_match = re.search(r'^#\s+Table:\s+\[?(\w+)\]?\.\[?(\w+)\]?', content, re.MULTILINE)
        if not table_match:
            # Fallback to filename
            table_name = file_path.stem
            schema_name, table = self._parse_table_name(table_name)
        else:
            schema_name = table_match.group(1)
            table = table_match.group(2)
        
        # Extract metadata
        type_match = re.search(r'\*\*Type:\*\*\s*(\w+)', content)
        
        # Extract description (everything between first heading and ## Columns)
        desc_match = re.search(r'^#[^#].*?\n\n(.*?)(?=\n##|\Z)', content, re.DOTALL)
        
        # Extract columns section
        columns_section = re.search(r'## Columns\s*\n(.*?)(?=\n##|\Z)', content, re.DOTALL)
        
        columns = []
        if columns_section and columns_section.group(1).strip():
            # Try parsing from ## Columns section
            columns = self._parse_columns_section(columns_section.group(1))
        
        # If no columns found, try parsing from markdown table in description
        if not columns:
            table_match = re.search(r'\|\s*Ord\s*\|\s*Name\s*\|\s*Data Type\s*\|\s*Description\s*\|.*?\n\|:?-+:?\|.*?\n((?:\|.*?\n)+)', content, re.DOTALL)
            if table_match:
                columns = self._parse_columns_from_table(table_match.group(1))
        
        # Build full description with metadata
        full_description = self._build_full_description(content, desc_match)
        
        return TableSchema(
            schema_name=schema_name,
            table_name=table,
            table_type=type_match.group(1).lower() if type_match else "table",
            description=full_description,
            columns=columns
        )
    
    def _parse_columns_section(self, columns_text: str) -> List[ColumnInfo]:
        """
        Parse the columns section of a table schema markdown
        
        Args:
            columns_text: Text content of the ## Columns section
            
        Returns:
            List of ColumnInfo objects
        """
        columns = []
        
        # Try format 1: ### ColumnName (DataType) - Description
        # Pattern: ### ColumnName (DataType) - [Optional] Primary Key / Foreign Key
        # Followed by description paragraph
        column_blocks = re.split(r'\n### ', columns_text)
        
        if len(column_blocks) > 1:  # Found ### format
            for block in column_blocks:
                if not block.strip():
                    continue
                    
                lines = block.strip().split('\n')
                header = lines[0]
                
                # Parse header: ColumnName (DataType) - Optional tags
                header_match = re.match(r'(.+?)\s*\((.+?)\)(?:\s*-\s*(.+))?', header)
                if not header_match:
                    continue
                
                column_name = header_match.group(1).strip()
                data_type = header_match.group(2).strip()
                tags = header_match.group(3).strip() if header_match.group(3) else ""
                
                # Description is remaining lines
                description_lines = [line.strip() for line in lines[1:] if line.strip()]
                description = " ".join(description_lines)
                
                # Add tags to description if present
                if tags:
                    description = f"{tags}. {description}" if description else tags
                
                columns.append(ColumnInfo(
                    name=column_name,
                    data_type=data_type,
                    description=description
                ))
        
        return columns
    
    def _parse_columns_from_table(self, table_text: str) -> List[ColumnInfo]:
        """
        Parse columns from markdown table format
        
        Format:
        | Ord | Name | Data Type | Description |
        | 1 | `ColumnName` | TYPE | Description text |
        
        Args:
            table_text: Markdown table rows
            
        Returns:
            List of ColumnInfo objects
        """
        columns = []
        
        for line in table_text.strip().split('\n'):
            if not line.strip() or not line.startswith('|'):
                continue
            
            # Split by | and clean up
            parts = [p.strip() for p in line.split('|')]
            # Filter out empty parts
            parts = [p for p in parts if p]
            
            if len(parts) < 4:
                continue
            
            # parts[0] = Ord, parts[1] = Name, parts[2] = Data Type, parts[3] = Description
            column_name = parts[1].strip('`').strip()
            data_type = parts[2].strip()
            description = parts[3].strip()
            
            if column_name and data_type:
                columns.append(ColumnInfo(
                    name=column_name,
                    data_type=data_type,
                    description=description
                ))
        
        return columns
    
    def _build_full_description(self, content: str, desc_match: Optional[re.Match]) -> str:
        """
        Build full table description including metadata
        
        Args:
            content: Full markdown content
            desc_match: Regex match object for description section
            
        Returns:
            Formatted description string
        """
        parts = []
        
        # Extract metadata fields
        metadata_fields = {
            'Data Source': r'\*\*Data Source:\*\*\s*(.+)',
            'Schema': r'\*\*Schema:\*\*\s*(.+)',
            'Type': r'\*\*Type:\*\*\s*(.+)',
            'Era': r'\*\*Era:\*\*\s*(.+)',
            'Record Count': r'\*\*Record Count:\*\*\s*(.+)',
            'Update Frequency': r'\*\*Update Frequency:\*\*\s*(.+)'
        }
        
        metadata_lines = []
        for field, pattern in metadata_fields.items():
            match = re.search(pattern, content)
            if match:
                metadata_lines.append(f"**{field}:** {match.group(1).strip()}")
        
        if metadata_lines:
            parts.append("\n".join(metadata_lines))
        
        # Add main description
        if desc_match:
            # Extract description section (skip metadata lines)
            desc_text = desc_match.group(1).strip()
            # Remove metadata lines from description
            desc_lines = [line for line in desc_text.split('\n') 
                         if not line.strip().startswith('**') or ':' not in line]
            if desc_lines:
                parts.append("\n".join(desc_lines).strip())
        
        return "\n\n".join(parts)
    
    def get_data_group_metadata(self, group_path: str) -> Optional[DataGroup]:
        """
        Parse _data-group.md file for keywords, description, table list
        
        Args:
            group_path: Path to _data-group.md file
            
        Returns:
            DataGroup object or None
        """
        return self._parse_data_group_file(Path(group_path))
    
    def clear_cache(self):
        """Clear cached data sources and groups"""
        self._data_sources_cache = None
        self._data_groups_cache = None
        self._schema_indices_cache = None
        self._object_indices_cache = None
    
    def load_schema_indices(self, force_reload: bool = False) -> Dict[str, Dict]:
        """
        Load all .schema-index.json files from data sources
        
        Args:
            force_reload: Force reload from disk even if cached
            
        Returns:
            Dictionary mapping data source name to schema index data
        """
        if self._schema_indices_cache is not None and not force_reload:
            return self._schema_indices_cache
        
        indices = {}
        
        # Find all .schema-index.json files
        for index_file in self.skills_path.rglob('.schema-index.json'):
            try:
                with open(index_file, 'r', encoding='utf-8') as f:
                    index_data = json.load(f)
                    data_source = index_data.get('data_source', index_file.parent.name)
                    indices[data_source] = index_data
            except Exception as e:
                print(f"Error loading schema index {index_file}: {e}")
        
        self._schema_indices_cache = indices
        return indices
    
    def load_object_indices(self, data_source: str, force_reload: bool = False) -> Dict[str, Dict]:
        """
        Load all .object-index.json files for a specific data source
        
        Args:
            data_source: Name of the data source
            force_reload: Force reload from disk even if cached
            
        Returns:
            Dictionary mapping schema name to object index data
        """
        if self._object_indices_cache is None:
            self._object_indices_cache = {}
        
        resolved_source = self._resolve_data_source_name(data_source)
        # Return from cache if this specific data source was already loaded
        if resolved_source in self._object_indices_cache and not force_reload:
            return self._object_indices_cache[resolved_source]
        
        indices = {}
        
        # Find data source directory
        data_source_dirs = list(self.skills_path.glob(f"*{resolved_source}*"))
        if not data_source_dirs:
            data_source_dirs = list(self.skills_path.glob("*"))
            data_source_dirs = [d for d in data_source_dirs if d.is_dir() and not d.name.startswith('_')]
        
        for ds_dir in data_source_dirs:
            # Find all .object-index.json files in this data source
            for index_file in ds_dir.rglob('.object-index.json'):
                try:
                    with open(index_file, 'r', encoding='utf-8') as f:
                        index_data = json.load(f)
                        schema_name = index_data.get('schema', index_file.parent.name)
                        indices[schema_name] = index_data
                except Exception as e:
                    print(f"Error loading object index {index_file}: {e}")
        
        self._object_indices_cache[resolved_source] = indices
        return indices
    
    def search_objects_by_keyword(self, query: str, data_source: Optional[str] = None, 
                                   object_type: Optional[str] = None, top_k: int = 10) -> List[Dict]:
        """
        Search for data objects using keywords from index files
        
        Args:
            query: Search query (keywords)
            data_source: Optional filter by data source name
            object_type: Optional filter by object type (Table/View)
            top_k: Maximum number of results to return
            
        Returns:
            List of matching objects with metadata
        """
        query_lower = query.lower()
        # Filter out stop words and very short terms for better precision
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
                     'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during',
                     'show', 'me', 'get', 'find', 'list', 'all', 'what', 'which', 'who', 'where',
                     'when', 'how', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have',
                     'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
                     'i', 'want', 'need', 'information', 'records', 'data',
                     'table', 'tables', 'view', 'views', 'column', 'columns',
                     'stored', 'stores', 'store', 'contains', 'contain', 'containing',
                     'database', 'schema', 'object', 'objects', 'field', 'fields'}
        query_terms = set(word for word in re.findall(r'\w+', query_lower) 
                        if word not in stop_words and len(word) > 2)
        
        results = []
        
        # Load schema indices
        schema_indices = self.load_schema_indices()
        
        # Filter by data source if specified
        resolved_source = self._resolve_data_source_name(data_source) if data_source else None
        sources_to_search = [resolved_source] if resolved_source else schema_indices.keys()
        
        for ds_name in sources_to_search:
            if ds_name not in schema_indices:
                continue
            
            # Load object indices for this data source
            object_indices = self.load_object_indices(ds_name)
            
            for schema_name, obj_index in object_indices.items():
                objects = obj_index.get('objects', [])
                
                for obj in objects:
                    # Filter by object type if specified
                    if object_type and obj.get('object_type') != object_type:
                        continue
                    
                    # Calculate relevance score
                    score = self._calculate_keyword_score(obj, query_terms)
                    
                    if score > 0:
                        result = {
                            'data_source': ds_name,
                            'schema_name': obj.get('schema_name'),
                            'object_name': obj.get('object_name'),
                            'object_type': obj.get('object_type'),
                            'description': obj.get('description', ''),
                            'keywords': obj.get('keywords', []),
                            'file_name': obj.get('file_name'),
                            'score': score
                        }
                        results.append(result)
        
        # Sort by score and return top_k
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:top_k]
    
    def _calculate_keyword_score(self, obj: Dict, query_terms: Set[str]) -> float:
        """
        Calculate relevance score for an object based on query terms
        
        Args:
            obj: Object metadata dictionary
            query_terms: Set of query terms
            
        Returns:
            Relevance score (higher is better)
        """
        score = 0.0
        
        # Check object name (weight: 3.0)
        obj_name_lower = obj.get('object_name', '').lower()
        for term in query_terms:
            if term in obj_name_lower:
                score += 3.0
        
        # Check keywords (weight: 2.0)
        keywords = obj.get('keywords', [])
        for keyword in keywords:
            if any(term in keyword.lower() for term in query_terms):
                score += 2.0
        
        # Check description (weight: 1.0)
        description = obj.get('description', '').lower()
        for term in query_terms:
            if term in description:
                score += 1.0
        
        return score
    
    def list_all_objects(self, data_source: Optional[str] = None, 
                         schema_name: Optional[str] = None) -> List[Dict]:
        """
        List all available data objects from index files
        
        Args:
            data_source: Optional filter by data source name
            schema_name: Optional filter by schema name
            
        Returns:
            List of all objects with metadata
        """
        results = []
        
        # Load schema indices
        schema_indices = self.load_schema_indices()
        
        # Filter by data source if specified
        resolved_source = self._resolve_data_source_name(data_source) if data_source else None
        sources_to_search = [resolved_source] if resolved_source else schema_indices.keys()
        
        for ds_name in sources_to_search:
            if ds_name not in schema_indices:
                continue
            
            # Load object indices for this data source
            object_indices = self.load_object_indices(ds_name)
            
            # Filter by schema if specified
            schemas_to_search = [schema_name] if schema_name else object_indices.keys()
            
            for sch_name in schemas_to_search:
                if sch_name not in object_indices:
                    continue
                
                obj_index = object_indices[sch_name]
                objects = obj_index.get('objects', [])
                
                for obj in objects:
                    result = {
                        'data_source': ds_name,
                        'schema_name': obj.get('schema_name'),
                        'object_name': obj.get('object_name'),
                        'object_type': obj.get('object_type'),
                        'description': obj.get('description', ''),
                        'keywords': obj.get('keywords', []),
                        'file_name': obj.get('file_name')
                    }
                    results.append(result)
        
        return results
    
    def get_object_by_name(self, object_name: str, schema_name: str = 'dbo',
                           data_source: Optional[str] = None) -> Optional[Dict]:
        """
        Get a specific object by name using index files
        
        Args:
            object_name: Name of the table/view
            schema_name: Schema name (default: dbo)
            data_source: Optional data source name
            
        Returns:
            Object metadata or None if not found
        """
        # Load schema indices
        schema_indices = self.load_schema_indices()
        
        # Search in all or specific data source
        resolved_source = self._resolve_data_source_name(data_source) if data_source else None
        sources_to_search = [resolved_source] if resolved_source else schema_indices.keys()
        
        for ds_name in sources_to_search:
            # Load object indices for this data source
            object_indices = self.load_object_indices(ds_name)
            
            if schema_name in object_indices:
                obj_index = object_indices[schema_name]
                objects = obj_index.get('objects', [])
                
                for obj in objects:
                    if obj.get('object_name') == object_name:
                        return {
                            'data_source': ds_name,
                            'schema_name': obj.get('schema_name'),
                            'object_name': obj.get('object_name'),
                            'object_type': obj.get('object_type'),
                            'description': obj.get('description', ''),
                            'keywords': obj.get('keywords', []),
                            'file_name': obj.get('file_name')
                        }
        
        return None
    
    def get_schema_statistics(self, data_source: Optional[str] = None) -> Dict:
        """
        Get statistics about available schemas using index files
        
        Args:
            data_source: Optional filter by data source name
            
        Returns:
            Dictionary with schema statistics
        """
        schema_indices = self.load_schema_indices()
        
        resolved_source = self._resolve_data_source_name(data_source) if data_source else None
        if resolved_source and resolved_source in schema_indices:
            # Stats for specific data source
            index_data = schema_indices[resolved_source]
            return {
                'data_source': resolved_source,
                'total_schemas': index_data.get('total_schemas', 0),
                'schemas': index_data.get('schemas', [])
            }
        else:
            # Stats for all data sources
            total_schemas = 0
            total_objects = 0
            total_tables = 0
            total_views = 0
            
            sources = []
            
            for ds_name, index_data in schema_indices.items():
                total_schemas += index_data.get('total_schemas', 0)
                
                for schema in index_data.get('schemas', []):
                    total_objects += schema.get('total_objects', 0)
                    total_tables += schema.get('tables', 0)
                    total_views += schema.get('views', 0)
                
                sources.append({
                    'name': ds_name,
                    'schemas': index_data.get('total_schemas', 0)
                })
            
            return {
                'total_data_sources': len(schema_indices),
                'total_schemas': total_schemas,
                'total_objects': total_objects,
                'total_tables': total_tables,
                'total_views': total_views,
                'data_sources': sources
            }

    def _resolve_data_source_name(self, data_source: str) -> str:
        """
        Resolve a data source name from a GUID if needed.
        """
        if not data_source:
            return data_source
        try:
            for ds in self.load_data_sources_index():
                if ds.source_id == data_source:
                    return ds.name
        except Exception:
            pass
        return data_source


# Singleton instance
_skills_service: Optional[SkillsService] = None

def get_skills_service() -> SkillsService:
    """Get or create the skills service singleton"""
    global _skills_service
    if _skills_service is None:
        _skills_service = SkillsService()
    return _skills_service
