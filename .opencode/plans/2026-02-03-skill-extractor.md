# Skill Extractor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a CLI tool (`scripts/generate_skills.py`) that scans external code files (.py, .sql, .r, .sas), uses the LLM to classify and summarize them into Business or Data skills, and writes structured markdown skill files with deduplication.

**Architecture:** 
1. **Scanner** - Walks external directory, filters noise, chunks large files
2. **Summarizer** - Batches chunks to LLM with skill extraction prompt  
3. **Writer** - Creates/updates skill files with content-hash deduplication

**Tech Stack:** Python CLI (argparse), LiteLLMService, pathlib, hashlib for content hashing

---

## Design Decisions

Based on user input:

| Decision | Choice |
|----------|--------|
| Integration Strategy | Extend existing skills system (add `business/` and `data/` alongside `data-sources/`) |
| Source Files | Scan `.py`, `.sql`, `.r`, `.sas` files from external path via `--scan-path` flag |
| LLM Provider | Use existing LiteLLM config from `.env` file |
| Execution Mode | CLI script only (`scripts/generate_skills.py`) |
| Skill Discovery | Keyword matching (same as existing `search_data_groups_by_keywords`) |
| Business vs Data Skills | Separate (not linked to existing Data Sources) |
| Deduplication | Content hash (SHA256 of source file content) |
| LLM Batch Size | Small batch (3-5 files per request) |
| Large File Handling | Chunking (split files over 10K chars) |
| Testing | Unit tests with mocked LLM responses |

---

## Directory Structure

```
skills/
├── data-sources/             # (existing) - Data Source skills
│   └── Northwind/
│       └── ...
├── business/                 # (NEW) - Business Skills 
│   ├── _index.md            # Business skills catalog
│   └── {skill-name}.md      # Individual business skills
└── data/                    # (NEW) - Data Skills (code-derived)
    ├── _index.md            # Data skills catalog
    └── {skill-name}.md      # Individual data skills

scripts/
└── generate_skills.py       # (NEW) - Main CLI script
```

---

## Skill File Formats

### Business Skill (`.md`)

```markdown
---
type: business
trigger_keywords:
  - revenue growth
  - quarterly comparison
  - percentage change
version: 1
created: 2026-02-03
source_file: analytics/growth_model.py
content_hash: abc123def456
---

# Revenue Growth Analysis

## Description

Calculates quarter-over-quarter revenue growth by comparing current period revenue to prior period.

## Logic Flow

1. Query `fact_transactions` for current and prior period totals
2. Apply growth formula: (Current - Prior) / Prior * 100
3. Return as percentage with formatting

## Usage Example

"Show me the revenue growth for last quarter"

## Related Tables

- fact_transactions
- dim_calendar
```

### Data Skill (`.md`)

```markdown
---
type: data
trigger_keywords:
  - users
  - active users
  - is_active filter
related_tables:
  - dim_users
  - fact_user_activity
version: 1
created: 2026-02-03
source_file: db/schemas/user_tables.sql
content_hash: def456abc789
---

# User Dimension Tables

## Description

Core user dimension table with standard filters.

## Schema Notes

- Always filter `is_active = 1` when querying active users from `dim_users`
- Join to `fact_user_activity` on `user_id`

## Common Joins

```sql
dim_users u 
JOIN fact_user_activity a ON u.user_id = a.user_id
WHERE u.is_active = 1
```
```

---

## Task 1: Create Pydantic Models for Skills

**Files:**
- Modify: `app/models/schemas.py`
- Test: `tests/test_skill_models.py`

**Step 1.1: Write the failing test**

```python
# tests/test_skill_models.py
"""Tests for skill-related Pydantic models"""

import pytest
from app.models.schemas import BusinessSkill, DataSkill, SkillType


def test_business_skill_creation():
    """Test creating a BusinessSkill with required fields"""
    skill = BusinessSkill(
        name="Revenue Growth Analysis",
        type=SkillType.BUSINESS,
        trigger_keywords=["revenue", "growth", "quarterly"],
        description="Calculates quarter-over-quarter revenue growth",
        logic_flow=["Query fact_transactions", "Apply growth formula", "Return percentage"],
        source_file="analytics/growth_model.py",
        content_hash="abc123"
    )
    assert skill.type == SkillType.BUSINESS
    assert "revenue" in skill.trigger_keywords
    assert len(skill.logic_flow) == 3


def test_data_skill_creation():
    """Test creating a DataSkill with required fields"""
    skill = DataSkill(
        name="User Dimension Tables",
        type=SkillType.DATA,
        trigger_keywords=["users", "active users"],
        related_tables=["dim_users", "fact_user_activity"],
        description="Core user dimension table with standard filters",
        schema_notes="Always filter is_active = 1",
        source_file="db/user_schema.sql",
        content_hash="def456"
    )
    assert skill.type == SkillType.DATA
    assert "dim_users" in skill.related_tables


def test_business_skill_to_markdown():
    """Test converting BusinessSkill to markdown format"""
    skill = BusinessSkill(
        name="Revenue Growth",
        type=SkillType.BUSINESS,
        trigger_keywords=["revenue", "growth"],
        description="Calculates growth",
        logic_flow=["Step 1", "Step 2"],
        source_file="test.py",
        content_hash="hash123"
    )
    md = skill.to_markdown()
    assert "type: business" in md
    assert "# Revenue Growth" in md
    assert "trigger_keywords:" in md


def test_data_skill_to_markdown():
    """Test converting DataSkill to markdown format"""
    skill = DataSkill(
        name="User Tables",
        type=SkillType.DATA,
        trigger_keywords=["users"],
        related_tables=["dim_users"],
        description="User dimension",
        schema_notes="Filter active",
        source_file="schema.sql",
        content_hash="hash456"
    )
    md = skill.to_markdown()
    assert "type: data" in md
    assert "related_tables:" in md
```

**Step 1.2: Run test to verify it fails**

Run: `pytest tests/test_skill_models.py -v`
Expected: FAIL with "cannot import name 'BusinessSkill'"

**Step 1.3: Write minimal implementation**

Add to `app/models/schemas.py`:

```python
from enum import Enum
from datetime import date

class SkillType(str, Enum):
    BUSINESS = "business"
    DATA = "data"


class BaseSkill(BaseModel):
    """Base class for all skills"""
    name: str
    type: SkillType
    trigger_keywords: List[str]
    description: str
    source_file: str
    content_hash: str
    version: int = 1
    created: date = None

    def __init__(self, **data):
        if data.get('created') is None:
            data['created'] = date.today()
        super().__init__(**data)


class BusinessSkill(BaseSkill):
    """Business logic skill - transformations, calculations, workflows"""
    type: SkillType = SkillType.BUSINESS
    logic_flow: List[str] = []
    usage_example: Optional[str] = None
    related_tables: List[str] = []

    def to_markdown(self) -> str:
        yaml_header = f"""---
type: {self.type.value}
trigger_keywords:
{chr(10).join(f'  - {kw}' for kw in self.trigger_keywords)}
version: {self.version}
created: {self.created}
source_file: {self.source_file}
content_hash: {self.content_hash}
---"""
        
        body = f"""
# {self.name}

## Description

{self.description}

## Logic Flow

{chr(10).join(f'{i+1}. {step}' for i, step in enumerate(self.logic_flow))}
"""
        if self.usage_example:
            body += f"""
## Usage Example

"{self.usage_example}"
"""
        if self.related_tables:
            body += f"""
## Related Tables

{chr(10).join(f'- {t}' for t in self.related_tables)}
"""
        return yaml_header + body


class DataSkill(BaseSkill):
    """Data context skill - schema definitions, joins, filters"""
    type: SkillType = SkillType.DATA
    related_tables: List[str] = []
    schema_notes: str = ""
    common_joins: Optional[str] = None

    def to_markdown(self) -> str:
        yaml_header = f"""---
type: {self.type.value}
trigger_keywords:
{chr(10).join(f'  - {kw}' for kw in self.trigger_keywords)}
related_tables:
{chr(10).join(f'  - {t}' for t in self.related_tables)}
version: {self.version}
created: {self.created}
source_file: {self.source_file}
content_hash: {self.content_hash}
---"""
        
        body = f"""
# {self.name}

## Description

{self.description}

## Schema Notes

{self.schema_notes}
"""
        if self.common_joins:
            body += f"""
## Common Joins

```sql
{self.common_joins}
```
"""
        return yaml_header + body
```

**Step 1.4: Run test to verify it passes**

Run: `pytest tests/test_skill_models.py -v`
Expected: PASS

**Step 1.5: Commit**

```bash
git add app/models/schemas.py tests/test_skill_models.py
git commit -m "feat: add BusinessSkill and DataSkill Pydantic models"
```

---

## Task 2: Create Code Scanner Module

**Files:**
- Create: `app/services/code_scanner.py`
- Test: `tests/test_code_scanner.py`

**Step 2.1: Write the failing test**

```python
# tests/test_code_scanner.py
"""Tests for code scanning functionality"""

import pytest
import tempfile
from pathlib import Path
from app.services.code_scanner import CodeScanner, CodeChunk


class TestCodeScanner:
    
    @pytest.fixture
    def sample_directory(self):
        """Create a temp directory with sample code files"""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            
            # Create .py file
            (root / "analysis.py").write_text('''
def calculate_growth(current, previous):
    """Calculate percentage growth between periods"""
    if previous == 0:
        return 0
    return (current - previous) / previous * 100
''')
            
            # Create .sql file  
            (root / "queries.sql").write_text('''
-- Get active users with their activity
SELECT u.user_id, u.name, a.last_login
FROM dim_users u
JOIN fact_user_activity a ON u.user_id = a.user_id
WHERE u.is_active = 1;
''')
            
            # Create file in venv (should be ignored)
            venv_dir = root / "venv" / "lib"
            venv_dir.mkdir(parents=True)
            (venv_dir / "package.py").write_text("# ignored")
            
            # Create __pycache__ (should be ignored)
            cache_dir = root / "__pycache__"
            cache_dir.mkdir()
            (cache_dir / "cached.pyc").write_text("# ignored")
            
            yield root
    
    def test_scan_finds_valid_files(self, sample_directory):
        """Scanner finds .py and .sql files, ignores noise"""
        scanner = CodeScanner(sample_directory)
        files = list(scanner.scan())
        
        filenames = [f.name for f in files]
        assert "analysis.py" in filenames
        assert "queries.sql" in filenames
        assert "package.py" not in filenames  # venv ignored
        assert "cached.pyc" not in filenames  # pycache ignored
    
    def test_scan_with_extensions_filter(self, sample_directory):
        """Scanner respects extension filter"""
        scanner = CodeScanner(sample_directory, extensions=[".sql"])
        files = list(scanner.scan())
        
        assert len(files) == 1
        assert files[0].name == "queries.sql"
    
    def test_read_content_returns_chunks(self, sample_directory):
        """Read content returns CodeChunk with metadata"""
        scanner = CodeScanner(sample_directory)
        files = list(scanner.scan())
        py_file = [f for f in files if f.suffix == ".py"][0]
        
        chunks = scanner.read_content(py_file)
        
        assert len(chunks) >= 1
        assert chunks[0].file_path == str(py_file)
        assert "calculate_growth" in chunks[0].content
        assert chunks[0].content_hash is not None
    
    def test_large_file_chunking(self):
        """Large files are split into manageable chunks"""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            # Create a large file (> 10KB)
            large_content = "-- SQL comment\n" * 1000 + "SELECT * FROM large_table;\n" * 500
            (root / "large.sql").write_text(large_content)
            
            scanner = CodeScanner(root, max_chunk_size=5000)
            files = list(scanner.scan())
            chunks = scanner.read_content(files[0])
            
            assert len(chunks) > 1  # File was chunked
            assert all(len(c.content) <= 5500 for c in chunks)  # Allow some overflow for clean breaks
```

**Step 2.2: Run test to verify it fails**

Run: `pytest tests/test_code_scanner.py -v`
Expected: FAIL with "cannot import name 'CodeScanner'"

**Step 2.3: Write minimal implementation**

```python
# app/services/code_scanner.py
"""
Code Scanner - Walks directories to find and chunk code files for skill extraction
"""

import os
import hashlib
from pathlib import Path
from typing import List, Iterator, Set
from dataclasses import dataclass


@dataclass
class CodeChunk:
    """A chunk of code content with metadata"""
    file_path: str
    content: str
    content_hash: str
    chunk_index: int = 0
    total_chunks: int = 1
    file_extension: str = ""


class CodeScanner:
    """Scans directories for code files and chunks them for LLM processing"""
    
    # Directories to always ignore
    IGNORE_DIRS: Set[str] = {
        'venv', '.venv', 'env', '.env',
        '__pycache__', '.pytest_cache',
        'node_modules', '.git',
        '.idea', '.vscode',
        'build', 'dist', 'target',
        '.docker', 'volumes'
    }
    
    # Default extensions to scan
    DEFAULT_EXTENSIONS: Set[str] = {'.py', '.sql', '.r', '.sas'}
    
    def __init__(
        self, 
        root_path: Path,
        extensions: List[str] = None,
        max_chunk_size: int = 10000,
        ignore_dirs: Set[str] = None
    ):
        """
        Initialize the code scanner.
        
        Args:
            root_path: Root directory to scan
            extensions: File extensions to include (default: .py, .sql, .r, .sas)
            max_chunk_size: Maximum characters per chunk (default: 10000)
            ignore_dirs: Additional directories to ignore
        """
        self.root_path = Path(root_path)
        self.extensions = set(extensions) if extensions else self.DEFAULT_EXTENSIONS
        self.max_chunk_size = max_chunk_size
        self.ignore_dirs = self.IGNORE_DIRS | (ignore_dirs or set())
    
    def scan(self) -> Iterator[Path]:
        """
        Walk the directory tree and yield valid code files.
        
        Yields:
            Path objects for each valid code file
        """
        for root, dirs, files in os.walk(self.root_path):
            # Filter out ignored directories (modifies dirs in-place)
            dirs[:] = [d for d in dirs if d.lower() not in self.ignore_dirs]
            
            for filename in files:
                file_path = Path(root) / filename
                
                # Check extension
                if file_path.suffix.lower() in self.extensions:
                    yield file_path
    
    def read_content(self, file_path: Path) -> List[CodeChunk]:
        """
        Read file content and chunk if necessary.
        
        Args:
            file_path: Path to the code file
            
        Returns:
            List of CodeChunk objects
        """
        try:
            content = file_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            # Try with latin-1 for older files
            content = file_path.read_text(encoding='latin-1')
        
        # Calculate hash of full content
        full_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        
        # If small enough, return single chunk
        if len(content) <= self.max_chunk_size:
            return [CodeChunk(
                file_path=str(file_path),
                content=content,
                content_hash=full_hash,
                chunk_index=0,
                total_chunks=1,
                file_extension=file_path.suffix.lower()
            )]
        
        # Split into chunks at logical boundaries
        chunks = self._split_content(content, file_path.suffix.lower())
        
        return [
            CodeChunk(
                file_path=str(file_path),
                content=chunk,
                content_hash=f"{full_hash}-{i}",
                chunk_index=i,
                total_chunks=len(chunks),
                file_extension=file_path.suffix.lower()
            )
            for i, chunk in enumerate(chunks)
        ]
    
    def _split_content(self, content: str, extension: str) -> List[str]:
        """
        Split content at logical boundaries based on file type.
        
        Args:
            content: Full file content
            extension: File extension for context-aware splitting
            
        Returns:
            List of content chunks
        """
        chunks = []
        
        # Simple chunking by size with boundary awareness
        current_chunk = ""
        for line in content.split('\n'):
            line_with_newline = line + '\n'
            
            # Check if adding this line would exceed limit
            if len(current_chunk) + len(line_with_newline) > self.max_chunk_size:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = line_with_newline
            else:
                current_chunk += line_with_newline
        
        # Don't forget the last chunk
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks if chunks else [content]
```

**Step 2.4: Run test to verify it passes**

Run: `pytest tests/test_code_scanner.py -v`
Expected: PASS

**Step 2.5: Commit**

```bash
git add app/services/code_scanner.py tests/test_code_scanner.py
git commit -m "feat: add CodeScanner for walking and chunking code files"
```

---

## Task 3: Create Skill Extraction Service (LLM Integration)

**Files:**
- Create: `app/services/skill_extraction_service.py`
- Test: `tests/test_skill_extraction_service.py`

**Step 3.1: Write the failing test**

```python
# tests/test_skill_extraction_service.py
"""Tests for skill extraction LLM integration"""

import pytest
from unittest.mock import Mock, patch
from app.services.skill_extraction_service import SkillExtractionService
from app.services.code_scanner import CodeChunk
from app.models.schemas import BusinessSkill, DataSkill, SkillType


class TestSkillExtractionService:
    
    @pytest.fixture
    def mock_llm_service(self):
        """Mock LLM service for testing"""
        with patch('app.services.skill_extraction_service.get_llm_service') as mock:
            llm = Mock()
            mock.return_value = llm
            yield llm
    
    @pytest.fixture
    def service(self, mock_llm_service):
        """Create service with mocked LLM"""
        return SkillExtractionService()
    
    def test_extract_business_skill_from_python(self, service, mock_llm_service):
        """Extract business skill from Python transformation code"""
        mock_llm_service.chat.return_value = '''
{
    "skill_type": "business",
    "name": "Revenue Growth Calculator",
    "trigger_keywords": ["revenue", "growth", "percentage"],
    "description": "Calculates period-over-period revenue growth",
    "logic_flow": ["Get current revenue", "Get prior revenue", "Calculate percentage"],
    "related_tables": ["fact_transactions"]
}
'''
        
        chunk = CodeChunk(
            file_path="analytics/growth.py",
            content="def calculate_growth(current, prior): return (current-prior)/prior*100",
            content_hash="abc123",
            file_extension=".py"
        )
        
        skill = service.extract_skill(chunk)
        
        assert isinstance(skill, BusinessSkill)
        assert skill.name == "Revenue Growth Calculator"
        assert "revenue" in skill.trigger_keywords
        assert skill.source_file == "analytics/growth.py"
    
    def test_extract_data_skill_from_sql(self, service, mock_llm_service):
        """Extract data skill from SQL schema file"""
        mock_llm_service.chat.return_value = '''
{
    "skill_type": "data",
    "name": "User Dimension Schema",
    "trigger_keywords": ["users", "active", "demographics"],
    "description": "User dimension table with activity flags",
    "related_tables": ["dim_users", "fact_user_activity"],
    "schema_notes": "Always filter is_active=1 for current users"
}
'''
        
        chunk = CodeChunk(
            file_path="db/users.sql",
            content="CREATE TABLE dim_users (user_id INT, is_active BIT);",
            content_hash="def456",
            file_extension=".sql"
        )
        
        skill = service.extract_skill(chunk)
        
        assert isinstance(skill, DataSkill)
        assert skill.name == "User Dimension Schema"
        assert "dim_users" in skill.related_tables
    
    def test_extract_batch_processes_multiple_chunks(self, service, mock_llm_service):
        """Batch extraction processes multiple related chunks"""
        mock_llm_service.chat.return_value = '''
[
    {
        "skill_type": "business",
        "name": "Sales Analysis",
        "trigger_keywords": ["sales", "revenue"],
        "description": "Analyzes sales data",
        "logic_flow": ["Query sales", "Aggregate"]
    },
    {
        "skill_type": "data",
        "name": "Sales Tables",
        "trigger_keywords": ["orders", "products"],
        "description": "Sales fact tables",
        "related_tables": ["fact_orders"]
    }
]
'''
        
        chunks = [
            CodeChunk(file_path="a.py", content="sales code", content_hash="h1", file_extension=".py"),
            CodeChunk(file_path="b.sql", content="CREATE TABLE", content_hash="h2", file_extension=".sql"),
        ]
        
        skills = service.extract_batch(chunks)
        
        assert len(skills) == 2
        assert any(isinstance(s, BusinessSkill) for s in skills)
        assert any(isinstance(s, DataSkill) for s in skills)
    
    def test_handles_llm_error_gracefully(self, service, mock_llm_service):
        """Service handles LLM errors without crashing"""
        mock_llm_service.chat.side_effect = Exception("LLM unavailable")
        
        chunk = CodeChunk(
            file_path="test.py",
            content="code",
            content_hash="hash",
            file_extension=".py"
        )
        
        skill = service.extract_skill(chunk)
        
        assert skill is None  # Returns None on error, doesn't crash
    
    def test_handles_invalid_json_response(self, service, mock_llm_service):
        """Service handles malformed LLM response"""
        mock_llm_service.chat.return_value = "This is not valid JSON"
        
        chunk = CodeChunk(
            file_path="test.py",
            content="code",
            content_hash="hash",
            file_extension=".py"
        )
        
        skill = service.extract_skill(chunk)
        
        assert skill is None
```

**Step 3.2: Run test to verify it fails**

Run: `pytest tests/test_skill_extraction_service.py -v`
Expected: FAIL with "cannot import name 'SkillExtractionService'"

**Step 3.3: Write minimal implementation**

```python
# app/services/skill_extraction_service.py
"""
Skill Extraction Service - Uses LLM to classify and summarize code into skills
"""

import json
import re
from typing import List, Optional, Union
from app.services.llm_service import get_llm_service, LLMServiceBase
from app.services.code_scanner import CodeChunk
from app.models.schemas import BusinessSkill, DataSkill, SkillType


SKILL_EXTRACTION_PROMPT = '''Analyze the following code from file `{filename}`.

**Your task:**
1. If it contains business logic (transformations, calculations, models, workflows), classify as a **Business Skill**
2. If it contains table definitions, schema info, or data context, classify as a **Data Skill**
3. If the code is trivial (imports only, config, etc.), respond with: {{"skip": true, "reason": "..."}}

**Code Content:**
```{extension}
{content}
```

**Output JSON format for Business Skill:**
```json
{{
    "skill_type": "business",
    "name": "Descriptive Skill Name",
    "trigger_keywords": ["keyword1", "keyword2", "keyword3"],
    "description": "What this code does in 1-2 sentences",
    "logic_flow": ["Step 1: ...", "Step 2: ...", "Step 3: ..."],
    "related_tables": ["table1", "table2"],
    "usage_example": "Example user query that would trigger this skill"
}}
```

**Output JSON format for Data Skill:**
```json
{{
    "skill_type": "data",
    "name": "Descriptive Skill Name",
    "trigger_keywords": ["keyword1", "keyword2"],
    "description": "What data context this provides",
    "related_tables": ["table1", "table2"],
    "schema_notes": "Important notes about joins, filters, gotchas",
    "common_joins": "SQL snippet showing common join pattern"
}}
```

Return ONLY valid JSON, no markdown formatting or explanation.
'''

BATCH_EXTRACTION_PROMPT = '''Analyze the following code files and extract skills.

For each file, determine if it's a Business Skill or Data Skill.

**Files to analyze:**
{file_contents}

**Return a JSON array of skill objects. Example:**
```json
[
    {{"skill_type": "business", "name": "...", "trigger_keywords": [...], ...}},
    {{"skill_type": "data", "name": "...", "trigger_keywords": [...], ...}}
]
```

Skip trivial files (imports only, config). Return ONLY valid JSON array.
'''


class SkillExtractionService:
    """Service for extracting skills from code using LLM"""
    
    def __init__(self, llm_service: LLMServiceBase = None):
        """
        Initialize the skill extraction service.
        
        Args:
            llm_service: Optional LLM service instance (uses default if not provided)
        """
        self.llm = llm_service or get_llm_service()
    
    def extract_skill(self, chunk: CodeChunk) -> Optional[Union[BusinessSkill, DataSkill]]:
        """
        Extract a skill from a single code chunk.
        
        Args:
            chunk: CodeChunk to analyze
            
        Returns:
            BusinessSkill or DataSkill, or None if extraction fails
        """
        prompt = SKILL_EXTRACTION_PROMPT.format(
            filename=chunk.file_path,
            extension=chunk.file_extension.lstrip('.'),
            content=chunk.content[:8000]  # Limit content size for prompt
        )
        
        try:
            response = self.llm.chat(prompt, temperature=0.1)
            skill_data = self._parse_json_response(response)
            
            if skill_data is None or skill_data.get('skip'):
                return None
            
            return self._create_skill(skill_data, chunk)
            
        except Exception as e:
            print(f"[WARNING] Failed to extract skill from {chunk.file_path}: {e}")
            return None
    
    def extract_batch(self, chunks: List[CodeChunk], batch_size: int = 5) -> List[Union[BusinessSkill, DataSkill]]:
        """
        Extract skills from multiple code chunks in batches.
        
        Args:
            chunks: List of CodeChunks to analyze
            batch_size: Number of chunks to process per LLM call
            
        Returns:
            List of extracted skills
        """
        all_skills = []
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            
            # Format batch content
            file_contents = "\n\n".join([
                f"### File: {c.file_path}\n```{c.file_extension.lstrip('.')}\n{c.content[:3000]}\n```"
                for c in batch
            ])
            
            prompt = BATCH_EXTRACTION_PROMPT.format(file_contents=file_contents)
            
            try:
                response = self.llm.chat(prompt, temperature=0.1)
                skills_data = self._parse_json_response(response)
                
                if isinstance(skills_data, list):
                    for j, skill_data in enumerate(skills_data):
                        if skill_data and not skill_data.get('skip'):
                            # Match skill to corresponding chunk
                            chunk = batch[min(j, len(batch) - 1)]
                            skill = self._create_skill(skill_data, chunk)
                            if skill:
                                all_skills.append(skill)
                                
            except Exception as e:
                print(f"[WARNING] Batch extraction failed: {e}")
                # Fall back to individual extraction
                for chunk in batch:
                    skill = self.extract_skill(chunk)
                    if skill:
                        all_skills.append(skill)
        
        return all_skills
    
    def _parse_json_response(self, response: str) -> Optional[Union[dict, list]]:
        """Parse JSON from LLM response, handling common formatting issues."""
        if not response:
            return None
        
        # Remove markdown code blocks if present
        response = re.sub(r'```json\s*', '', response)
        response = re.sub(r'```\s*', '', response)
        response = response.strip()
        
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Try to find JSON in the response
            json_match = re.search(r'[\[{].*[\]}]', response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
            return None
    
    def _create_skill(
        self, 
        skill_data: dict, 
        chunk: CodeChunk
    ) -> Optional[Union[BusinessSkill, DataSkill]]:
        """Create a skill object from parsed data."""
        try:
            skill_type = skill_data.get('skill_type', '').lower()
            
            common_fields = {
                'name': skill_data.get('name', 'Unnamed Skill'),
                'trigger_keywords': skill_data.get('trigger_keywords', []),
                'description': skill_data.get('description', ''),
                'source_file': chunk.file_path,
                'content_hash': chunk.content_hash,
            }
            
            if skill_type == 'business':
                return BusinessSkill(
                    **common_fields,
                    logic_flow=skill_data.get('logic_flow', []),
                    usage_example=skill_data.get('usage_example'),
                    related_tables=skill_data.get('related_tables', []),
                )
            elif skill_type == 'data':
                return DataSkill(
                    **common_fields,
                    related_tables=skill_data.get('related_tables', []),
                    schema_notes=skill_data.get('schema_notes', ''),
                    common_joins=skill_data.get('common_joins'),
                )
            else:
                print(f"[WARNING] Unknown skill type: {skill_type}")
                return None
                
        except Exception as e:
            print(f"[WARNING] Failed to create skill object: {e}")
            return None
```

**Step 3.4: Run test to verify it passes**

Run: `pytest tests/test_skill_extraction_service.py -v`
Expected: PASS

**Step 3.5: Commit**

```bash
git add app/services/skill_extraction_service.py tests/test_skill_extraction_service.py
git commit -m "feat: add SkillExtractionService for LLM-based skill extraction"
```

---

## Task 4: Create Skill Writer Service

**Files:**
- Create: `app/services/skill_writer_service.py`
- Test: `tests/test_skill_writer_service.py`

**Step 4.1: Write the failing test**

```python
# tests/test_skill_writer_service.py
"""Tests for skill file writing with deduplication"""

import pytest
import tempfile
from pathlib import Path
from app.services.skill_writer_service import SkillWriterService
from app.models.schemas import BusinessSkill, DataSkill, SkillType


class TestSkillWriterService:
    
    @pytest.fixture
    def temp_skills_dir(self):
        """Create temporary skills directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def service(self, temp_skills_dir):
        """Create service with temp directory"""
        return SkillWriterService(skills_root=temp_skills_dir)
    
    def test_write_business_skill_creates_file(self, service, temp_skills_dir):
        """Writing business skill creates correct file structure"""
        skill = BusinessSkill(
            name="Revenue Growth",
            trigger_keywords=["revenue", "growth"],
            description="Calculates growth",
            logic_flow=["Step 1", "Step 2"],
            source_file="test.py",
            content_hash="hash123"
        )
        
        filepath = service.write_skill(skill)
        
        assert filepath.exists()
        assert "business" in str(filepath)
        assert filepath.suffix == ".md"
        content = filepath.read_text()
        assert "type: business" in content
        assert "# Revenue Growth" in content
    
    def test_write_data_skill_creates_file(self, service, temp_skills_dir):
        """Writing data skill creates correct file structure"""
        skill = DataSkill(
            name="User Tables",
            trigger_keywords=["users"],
            related_tables=["dim_users"],
            description="User dimension",
            schema_notes="Filter active",
            source_file="schema.sql",
            content_hash="hash456"
        )
        
        filepath = service.write_skill(skill)
        
        assert filepath.exists()
        assert "data" in str(filepath)
        content = filepath.read_text()
        assert "type: data" in content
        assert "related_tables:" in content
    
    def test_deduplication_by_content_hash(self, service, temp_skills_dir):
        """Same content hash updates existing file instead of creating new"""
        skill1 = BusinessSkill(
            name="Original Name",
            trigger_keywords=["test"],
            description="Original",
            source_file="test.py",
            content_hash="same_hash"
        )
        
        skill2 = BusinessSkill(
            name="Updated Name",
            trigger_keywords=["test", "updated"],
            description="Updated description",
            source_file="test.py",
            content_hash="same_hash"  # Same hash = same content
        )
        
        path1 = service.write_skill(skill1)
        path2 = service.write_skill(skill2)
        
        assert path1 == path2  # Same file updated
        content = path1.read_text()
        assert "Updated Name" in content  # Has new content
    
    def test_different_hash_creates_new_file(self, service, temp_skills_dir):
        """Different content hash creates new skill file"""
        skill1 = BusinessSkill(
            name="Skill One",
            trigger_keywords=["test"],
            description="First",
            source_file="test1.py",
            content_hash="hash_one"
        )
        
        skill2 = BusinessSkill(
            name="Skill Two",
            trigger_keywords=["test"],
            description="Second",
            source_file="test2.py",
            content_hash="hash_two"
        )
        
        path1 = service.write_skill(skill1)
        path2 = service.write_skill(skill2)
        
        assert path1 != path2
        assert path1.exists()
        assert path2.exists()
    
    def test_update_index_file(self, service, temp_skills_dir):
        """Index file is updated after writing skills"""
        skill = BusinessSkill(
            name="Test Skill",
            trigger_keywords=["test"],
            description="A test skill",
            source_file="test.py",
            content_hash="hash"
        )
        
        service.write_skill(skill)
        service.update_index()
        
        index_path = temp_skills_dir / "business" / "_index.md"
        assert index_path.exists()
        content = index_path.read_text()
        assert "Test Skill" in content
    
    def test_get_existing_hashes(self, service, temp_skills_dir):
        """Can retrieve content hashes from existing skill files"""
        skill = BusinessSkill(
            name="Existing Skill",
            trigger_keywords=["existing"],
            description="Already exists",
            source_file="existing.py",
            content_hash="existing_hash_123"
        )
        
        service.write_skill(skill)
        
        # New service instance should find existing hash
        new_service = SkillWriterService(skills_root=temp_skills_dir)
        hashes = new_service.get_existing_hashes()
        
        assert "existing_hash_123" in hashes
```

**Step 4.2: Run test to verify it fails**

Run: `pytest tests/test_skill_writer_service.py -v`
Expected: FAIL with "cannot import name 'SkillWriterService'"

**Step 4.3: Write minimal implementation**

```python
# app/services/skill_writer_service.py
"""
Skill Writer Service - Writes skill files with deduplication
"""

import re
from pathlib import Path
from typing import Dict, Set, Union, Optional
from app.models.schemas import BusinessSkill, DataSkill, SkillType


class SkillWriterService:
    """Service for writing skill files with content-hash deduplication"""
    
    def __init__(self, skills_root: Path = None):
        """
        Initialize the skill writer service.
        
        Args:
            skills_root: Root directory for skills (default: skills/)
        """
        self.skills_root = Path(skills_root) if skills_root else Path("skills")
        self.business_dir = self.skills_root / "business"
        self.data_dir = self.skills_root / "data"
        
        # Ensure directories exist
        self.business_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache of content_hash -> file_path for deduplication
        self._hash_to_path: Dict[str, Path] = {}
        self._load_existing_hashes()
    
    def _load_existing_hashes(self):
        """Load content hashes from existing skill files"""
        for skill_file in self.business_dir.glob("*.md"):
            if skill_file.name.startswith("_"):
                continue
            hash_val = self._extract_hash_from_file(skill_file)
            if hash_val:
                self._hash_to_path[hash_val] = skill_file
        
        for skill_file in self.data_dir.glob("*.md"):
            if skill_file.name.startswith("_"):
                continue
            hash_val = self._extract_hash_from_file(skill_file)
            if hash_val:
                self._hash_to_path[hash_val] = skill_file
    
    def _extract_hash_from_file(self, filepath: Path) -> Optional[str]:
        """Extract content_hash from YAML frontmatter"""
        try:
            content = filepath.read_text(encoding='utf-8')
            match = re.search(r'content_hash:\s*(\S+)', content)
            return match.group(1) if match else None
        except Exception:
            return None
    
    def get_existing_hashes(self) -> Set[str]:
        """Get all existing content hashes"""
        return set(self._hash_to_path.keys())
    
    def write_skill(self, skill: Union[BusinessSkill, DataSkill]) -> Path:
        """
        Write a skill to file with deduplication.
        
        If content_hash already exists, updates the existing file.
        Otherwise creates a new file.
        
        Args:
            skill: The skill to write
            
        Returns:
            Path to the written file
        """
        # Check for existing file with same content hash
        if skill.content_hash in self._hash_to_path:
            filepath = self._hash_to_path[skill.content_hash]
            # Update existing file
            filepath.write_text(skill.to_markdown(), encoding='utf-8')
            return filepath
        
        # Create new file
        target_dir = self.business_dir if skill.type == SkillType.BUSINESS else self.data_dir
        
        # Generate filename from skill name
        filename = self._sanitize_filename(skill.name) + ".md"
        filepath = target_dir / filename
        
        # Handle filename collisions
        counter = 1
        while filepath.exists() and skill.content_hash not in self._hash_to_path:
            filename = f"{self._sanitize_filename(skill.name)}-{counter}.md"
            filepath = target_dir / filename
            counter += 1
        
        # Write file
        filepath.write_text(skill.to_markdown(), encoding='utf-8')
        
        # Update cache
        self._hash_to_path[skill.content_hash] = filepath
        
        return filepath
    
    def _sanitize_filename(self, name: str) -> str:
        """Convert skill name to valid filename"""
        # Remove special characters, replace spaces with hyphens
        sanitized = re.sub(r'[^\w\s-]', '', name.lower())
        sanitized = re.sub(r'[-\s]+', '-', sanitized).strip('-')
        return sanitized[:50]  # Limit length
    
    def update_index(self):
        """Update the _index.md files for business and data skills"""
        self._update_index_for_dir(self.business_dir, "Business Skills")
        self._update_index_for_dir(self.data_dir, "Data Skills")
    
    def _update_index_for_dir(self, directory: Path, title: str):
        """Generate _index.md for a skill directory"""
        skill_files = sorted([
            f for f in directory.glob("*.md")
            if not f.name.startswith("_")
        ])
        
        content = f"""# {title} Catalog

Last updated: {__import__('datetime').datetime.now().isoformat()}

## Available Skills

"""
        for skill_file in skill_files:
            try:
                file_content = skill_file.read_text(encoding='utf-8')
                
                # Extract metadata from frontmatter
                name_match = re.search(r'^#\s+(.+)$', file_content, re.MULTILINE)
                name = name_match.group(1) if name_match else skill_file.stem
                
                keywords_match = re.search(r'trigger_keywords:\s*\n((?:\s+-\s+.+\n)+)', file_content)
                keywords = []
                if keywords_match:
                    keywords = re.findall(r'-\s+(.+)', keywords_match.group(1))
                
                content += f"""### {name}

**File:** [{skill_file.name}]({skill_file.name})  
**Keywords:** {', '.join(keywords[:5])}

"""
            except Exception as e:
                print(f"[WARNING] Failed to read {skill_file}: {e}")
        
        index_path = directory / "_index.md"
        index_path.write_text(content, encoding='utf-8')
```

**Step 4.4: Run test to verify it passes**

Run: `pytest tests/test_skill_writer_service.py -v`
Expected: PASS

**Step 4.5: Commit**

```bash
git add app/services/skill_writer_service.py tests/test_skill_writer_service.py
git commit -m "feat: add SkillWriterService with content-hash deduplication"
```

---

## Task 5: Create Main CLI Script

**Files:**
- Create: `scripts/generate_skills.py`
- Test: `tests/test_generate_skills_cli.py`

**Step 5.1: Write the failing test**

```python
# tests/test_generate_skills_cli.py
"""Tests for generate_skills CLI script"""

import pytest
import tempfile
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, Mock


class TestGenerateSkillsCLI:
    
    @pytest.fixture
    def temp_dirs(self):
        """Create temp source and output directories"""
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as output_dir:
                # Create sample files
                source = Path(source_dir)
                (source / "analysis.py").write_text('''
def calculate_revenue_growth(current, previous):
    """Calculate period-over-period revenue growth percentage"""
    if previous == 0:
        return 0
    return ((current - previous) / previous) * 100
''')
                (source / "schema.sql").write_text('''
-- User dimension table
CREATE TABLE dim_users (
    user_id INT PRIMARY KEY,
    username VARCHAR(50),
    is_active BIT DEFAULT 1
);
''')
                yield {'source': source, 'output': Path(output_dir)}
    
    def test_cli_shows_help(self):
        """CLI shows help with --help flag"""
        result = subprocess.run(
            [sys.executable, "scripts/generate_skills.py", "--help"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "Skill Extractor" in result.stdout or "usage" in result.stdout.lower()
    
    def test_cli_requires_scan_path(self):
        """CLI requires --scan-path argument"""
        result = subprocess.run(
            [sys.executable, "scripts/generate_skills.py"],
            capture_output=True,
            text=True
        )
        assert result.returncode != 0
        assert "required" in result.stderr.lower() or "error" in result.stderr.lower()
    
    def test_cli_dry_run_mode(self, temp_dirs):
        """CLI dry-run mode doesn't create files"""
        result = subprocess.run(
            [
                sys.executable, "scripts/generate_skills.py",
                "--scan-path", str(temp_dirs['source']),
                "--output-dir", str(temp_dirs['output']),
                "--dry-run"
            ],
            capture_output=True,
            text=True
        )
        
        # Dry run should succeed but not create skill files
        assert "DRY RUN" in result.stdout
        assert not (temp_dirs['output'] / "business").exists() or \
               len(list((temp_dirs['output'] / "business").glob("*.md"))) == 0


# Integration test (requires LLM) - skip in CI
@pytest.mark.skip(reason="Integration test - requires LLM API")
class TestGenerateSkillsIntegration:
    
    def test_full_extraction_pipeline(self, temp_dirs):
        """Full pipeline creates skill files from code"""
        result = subprocess.run(
            [
                sys.executable, "scripts/generate_skills.py",
                "--scan-path", str(temp_dirs['source']),
                "--output-dir", str(temp_dirs['output'])
            ],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        # Should have created some skill files
        business_skills = list((temp_dirs['output'] / "business").glob("*.md"))
        data_skills = list((temp_dirs['output'] / "data").glob("*.md"))
        assert len(business_skills) + len(data_skills) > 0
```

**Step 5.2: Run test to verify it fails**

Run: `pytest tests/test_generate_skills_cli.py::TestGenerateSkillsCLI::test_cli_shows_help -v`
Expected: FAIL with "No such file or directory: 'scripts/generate_skills.py'"

**Step 5.3: Write minimal implementation**

```python
#!/usr/bin/env python
"""
Skill Extractor - Generate skill files from code analysis

This script scans external code directories (.py, .sql, .r, .sas files),
sends code to an LLM for classification and summarization, and generates
structured skill files (Business Skills and Data Skills).

Usage:
    python scripts/generate_skills.py --scan-path /path/to/code [--output-dir skills/]
    python scripts/generate_skills.py --scan-path /path/to/code --dry-run
    python scripts/generate_skills.py --scan-path /path/to/code --extensions .sql .r

Examples:
    # Scan analytics code and generate skills
    python scripts/generate_skills.py --scan-path ../analytics-repo/

    # Preview what would be extracted without writing files
    python scripts/generate_skills.py --scan-path ../analytics-repo/ --dry-run

    # Only scan SQL files
    python scripts/generate_skills.py --scan-path ../db-scripts/ --extensions .sql
"""

import sys
import argparse
from pathlib import Path
from typing import List

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.code_scanner import CodeScanner, CodeChunk
from app.services.skill_extraction_service import SkillExtractionService
from app.services.skill_writer_service import SkillWriterService


def print_banner():
    """Print script banner"""
    print("=" * 60)
    print("  Skill Extractor for SQL Agent")
    print("  Analyze code -> Generate Business & Data Skills")
    print("=" * 60)


def scan_files(scan_path: Path, extensions: List[str]) -> List[CodeChunk]:
    """
    Scan directory for code files and return chunks.
    
    Args:
        scan_path: Root directory to scan
        extensions: File extensions to include
        
    Returns:
        List of CodeChunks
    """
    print(f"\n[SCAN] Scanning: {scan_path}")
    print(f"[SCAN] Extensions: {', '.join(extensions)}")
    
    scanner = CodeScanner(scan_path, extensions=extensions)
    files = list(scanner.scan())
    
    print(f"[SCAN] Found {len(files)} code file(s)")
    
    all_chunks = []
    for file_path in files:
        chunks = scanner.read_content(file_path)
        all_chunks.extend(chunks)
        if len(chunks) > 1:
            print(f"  - {file_path.name} (chunked into {len(chunks)} parts)")
        else:
            print(f"  - {file_path.name}")
    
    print(f"[SCAN] Total chunks: {len(all_chunks)}")
    return all_chunks


def extract_skills(chunks: List[CodeChunk], dry_run: bool = False):
    """
    Extract skills from code chunks using LLM.
    
    Args:
        chunks: List of code chunks to analyze
        dry_run: If True, simulate without LLM calls
        
    Returns:
        List of extracted skills
    """
    print(f"\n[EXTRACT] Processing {len(chunks)} chunk(s)...")
    
    if dry_run:
        print("[DRY RUN] Skipping LLM extraction")
        return []
    
    service = SkillExtractionService()
    
    # Use batch extraction for efficiency
    skills = service.extract_batch(chunks, batch_size=5)
    
    business_count = sum(1 for s in skills if s.type.value == 'business')
    data_count = sum(1 for s in skills if s.type.value == 'data')
    
    print(f"[EXTRACT] Extracted {len(skills)} skill(s):")
    print(f"  - Business Skills: {business_count}")
    print(f"  - Data Skills: {data_count}")
    
    return skills


def write_skills(skills, output_dir: Path, dry_run: bool = False):
    """
    Write extracted skills to files.
    
    Args:
        skills: List of skills to write
        output_dir: Output directory for skill files
        dry_run: If True, simulate without writing
    """
    print(f"\n[WRITE] Output directory: {output_dir}")
    
    if dry_run:
        print("[DRY RUN] Would write the following skills:")
        for skill in skills:
            print(f"  - {skill.type.value}/{skill.name}")
        return
    
    if not skills:
        print("[WRITE] No skills to write")
        return
    
    writer = SkillWriterService(skills_root=output_dir)
    
    # Check for existing hashes (deduplication)
    existing_hashes = writer.get_existing_hashes()
    new_count = 0
    updated_count = 0
    
    for skill in skills:
        is_update = skill.content_hash in existing_hashes
        filepath = writer.write_skill(skill)
        
        if is_update:
            print(f"  [UPDATE] {filepath.name}")
            updated_count += 1
        else:
            print(f"  [CREATE] {filepath.name}")
            new_count += 1
    
    # Update index files
    writer.update_index()
    print(f"\n[WRITE] Created: {new_count}, Updated: {updated_count}")
    print("[WRITE] Index files updated")


def main():
    parser = argparse.ArgumentParser(
        description='Skill Extractor - Generate skill files from code analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        '--scan-path',
        type=Path,
        required=True,
        help='Path to directory containing code files to analyze'
    )
    
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('skills'),
        help='Output directory for skill files (default: skills/)'
    )
    
    parser.add_argument(
        '--extensions',
        nargs='+',
        default=['.py', '.sql', '.r', '.sas'],
        help='File extensions to scan (default: .py .sql .r .sas)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview what would be extracted without making LLM calls or writing files'
    )
    
    parser.add_argument(
        '--batch-size',
        type=int,
        default=5,
        help='Number of files to process per LLM batch (default: 5)'
    )
    
    args = parser.parse_args()
    
    # Validate scan path
    if not args.scan_path.exists():
        print(f"[ERROR] Scan path does not exist: {args.scan_path}")
        sys.exit(1)
    
    if not args.scan_path.is_dir():
        print(f"[ERROR] Scan path is not a directory: {args.scan_path}")
        sys.exit(1)
    
    # Run pipeline
    print_banner()
    
    if args.dry_run:
        print("\n" + "=" * 60)
        print("  [DRY RUN MODE] - No files will be created")
        print("=" * 60)
    
    # Phase 1: Scan
    chunks = scan_files(args.scan_path, args.extensions)
    
    if not chunks:
        print("\n[WARNING] No code files found to process")
        sys.exit(0)
    
    # Phase 2: Extract
    skills = extract_skills(chunks, dry_run=args.dry_run)
    
    # Phase 3: Write
    write_skills(skills, args.output_dir, dry_run=args.dry_run)
    
    print("\n" + "=" * 60)
    print("  [COMPLETE] Skill extraction finished")
    print("=" * 60)


if __name__ == '__main__':
    main()
```

**Step 5.4: Run test to verify it passes**

Run: `pytest tests/test_generate_skills_cli.py::TestGenerateSkillsCLI -v`
Expected: PASS

**Step 5.5: Commit**

```bash
git add scripts/generate_skills.py tests/test_generate_skills_cli.py
git commit -m "feat: add generate_skills.py CLI for skill extraction"
```

---

## Task 6: Extend SkillsService to Search New Skills

**Files:**
- Modify: `app/services/skills_service.py`
- Test: `tests/test_skills_service_extended.py`

**Step 6.1: Write the failing test**

```python
# tests/test_skills_service_extended.py
"""Tests for extended SkillsService with business/data skill search"""

import pytest
import tempfile
from pathlib import Path
from app.services.skills_service import SkillsService


class TestSkillsServiceExtended:
    
    @pytest.fixture
    def skills_with_business_data(self):
        """Create temp skills directory with business and data skills"""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            
            # Create business skill
            business_dir = root / "business"
            business_dir.mkdir()
            (business_dir / "revenue-growth.md").write_text('''---
type: business
trigger_keywords:
  - revenue
  - growth
  - quarterly
---

# Revenue Growth Analysis

## Description
Calculates quarter-over-quarter revenue growth.
''')
            
            # Create data skill
            data_dir = root / "data"
            data_dir.mkdir()
            (data_dir / "user-tables.md").write_text('''---
type: data
trigger_keywords:
  - users
  - active
  - demographics
related_tables:
  - dim_users
  - fact_user_activity
---

# User Dimension Schema

## Description
User dimension with activity tracking.

## Schema Notes
Always filter is_active = 1 for current users.
''')
            
            yield root
    
    def test_search_business_skills(self, skills_with_business_data):
        """Search finds relevant business skills by keyword"""
        service = SkillsService(skills_path=str(skills_with_business_data))
        
        results = service.search_business_skills("revenue growth")
        
        assert len(results) >= 1
        assert any("Revenue Growth" in s.name for s in results)
    
    def test_search_data_skills(self, skills_with_business_data):
        """Search finds relevant data skills by keyword"""
        service = SkillsService(skills_path=str(skills_with_business_data))
        
        results = service.search_data_skills("active users")
        
        assert len(results) >= 1
        assert any("dim_users" in s.related_tables for s in results)
    
    def test_combined_skill_search(self, skills_with_business_data):
        """Combined search finds both skill types"""
        service = SkillsService(skills_path=str(skills_with_business_data))
        
        business, data = service.search_all_skills("user growth")
        
        # Should find both since "growth" matches business and "user" matches data
        assert len(business) + len(data) >= 1
```

**Step 6.2: Run test to verify it fails**

Run: `pytest tests/test_skills_service_extended.py -v`
Expected: FAIL with "AttributeError: 'SkillsService' object has no attribute 'search_business_skills'"

**Step 6.3: Write minimal implementation**

Add to `app/services/skills_service.py`:

```python
# Add these imports at top
from app.models.schemas import BusinessSkill, DataSkill, SkillType

# Add these methods to SkillsService class:

    def load_business_skills(self) -> List[BusinessSkill]:
        """
        Load all business skills from skills/business/ directory
        
        Returns:
            List of BusinessSkill objects
        """
        business_dir = self.skills_path.parent / "business"
        if not business_dir.exists():
            return []
        
        skills = []
        for skill_file in business_dir.glob("*.md"):
            if skill_file.name.startswith("_"):
                continue
            skill = self._parse_business_skill_file(skill_file)
            if skill:
                skills.append(skill)
        
        return skills
    
    def load_data_skills(self) -> List[DataSkill]:
        """
        Load all data skills from skills/data/ directory
        
        Returns:
            List of DataSkill objects
        """
        data_dir = self.skills_path.parent / "data"
        if not data_dir.exists():
            return []
        
        skills = []
        for skill_file in data_dir.glob("*.md"):
            if skill_file.name.startswith("_"):
                continue
            skill = self._parse_data_skill_file(skill_file)
            if skill:
                skills.append(skill)
        
        return skills
    
    def _parse_business_skill_file(self, file_path: Path) -> Optional[BusinessSkill]:
        """Parse a business skill markdown file"""
        try:
            content = file_path.read_text(encoding='utf-8')
            
            # Extract YAML frontmatter
            keywords = re.findall(r'trigger_keywords:\s*\n((?:\s+-\s+.+\n)+)', content)
            keyword_list = []
            if keywords:
                keyword_list = re.findall(r'-\s+(.+)', keywords[0])
            
            name_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            desc_match = re.search(r'## Description\s*\n(.*?)(?=\n##|\Z)', content, re.DOTALL)
            
            return BusinessSkill(
                name=name_match.group(1).strip() if name_match else file_path.stem,
                trigger_keywords=keyword_list,
                description=desc_match.group(1).strip() if desc_match else "",
                source_file=str(file_path),
                content_hash=file_path.stem
            )
        except Exception as e:
            print(f"[WARNING] Failed to parse business skill {file_path}: {e}")
            return None
    
    def _parse_data_skill_file(self, file_path: Path) -> Optional[DataSkill]:
        """Parse a data skill markdown file"""
        try:
            content = file_path.read_text(encoding='utf-8')
            
            # Extract YAML frontmatter
            keywords = re.findall(r'trigger_keywords:\s*\n((?:\s+-\s+.+\n)+)', content)
            keyword_list = []
            if keywords:
                keyword_list = re.findall(r'-\s+(.+)', keywords[0])
            
            tables = re.findall(r'related_tables:\s*\n((?:\s+-\s+.+\n)+)', content)
            table_list = []
            if tables:
                table_list = re.findall(r'-\s+(.+)', tables[0])
            
            name_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            desc_match = re.search(r'## Description\s*\n(.*?)(?=\n##|\Z)', content, re.DOTALL)
            notes_match = re.search(r'## Schema Notes\s*\n(.*?)(?=\n##|\Z)', content, re.DOTALL)
            
            return DataSkill(
                name=name_match.group(1).strip() if name_match else file_path.stem,
                trigger_keywords=keyword_list,
                related_tables=table_list,
                description=desc_match.group(1).strip() if desc_match else "",
                schema_notes=notes_match.group(1).strip() if notes_match else "",
                source_file=str(file_path),
                content_hash=file_path.stem
            )
        except Exception as e:
            print(f"[WARNING] Failed to parse data skill {file_path}: {e}")
            return None
    
    def search_business_skills(self, query: str) -> List[BusinessSkill]:
        """
        Search business skills by keyword matching.
        
        Args:
            query: Search query
            
        Returns:
            List of matching BusinessSkill objects, sorted by relevance
        """
        skills = self.load_business_skills()
        query_keywords = self._extract_keywords(query)
        
        scored_skills = []
        for skill in skills:
            score = self._score_skill(skill.trigger_keywords, skill.description, query_keywords)
            if score > 0:
                scored_skills.append((skill, score))
        
        # Sort by score descending
        scored_skills.sort(key=lambda x: x[1], reverse=True)
        return [s[0] for s in scored_skills[:10]]
    
    def search_data_skills(self, query: str) -> List[DataSkill]:
        """
        Search data skills by keyword matching.
        
        Args:
            query: Search query
            
        Returns:
            List of matching DataSkill objects, sorted by relevance
        """
        skills = self.load_data_skills()
        query_keywords = self._extract_keywords(query)
        
        scored_skills = []
        for skill in skills:
            # Include related_tables in search
            searchable = skill.trigger_keywords + skill.related_tables
            score = self._score_skill(searchable, skill.description, query_keywords)
            if score > 0:
                scored_skills.append((skill, score))
        
        scored_skills.sort(key=lambda x: x[1], reverse=True)
        return [s[0] for s in scored_skills[:10]]
    
    def search_all_skills(self, query: str) -> Tuple[List[BusinessSkill], List[DataSkill]]:
        """
        Search both business and data skills.
        
        Args:
            query: Search query
            
        Returns:
            Tuple of (business_skills, data_skills)
        """
        return self.search_business_skills(query), self.search_data_skills(query)
    
    def _score_skill(self, keywords: List[str], description: str, query_keywords: List[str]) -> int:
        """Score a skill based on keyword matching"""
        score = 0
        searchable_text = " ".join(keywords).lower() + " " + description.lower()
        
        for qk in query_keywords:
            if qk in [k.lower() for k in keywords]:
                score += 10  # Exact keyword match
            elif qk in searchable_text:
                score += 3   # Substring match
        
        return score
```

**Step 6.4: Run test to verify it passes**

Run: `pytest tests/test_skills_service_extended.py -v`
Expected: PASS

**Step 6.5: Commit**

```bash
git add app/services/skills_service.py tests/test_skills_service_extended.py
git commit -m "feat: extend SkillsService with business/data skill search"
```

---

## Task 7: Run Full Test Suite and Final Commit

**Step 7.1: Run all tests**

```bash
pytest tests/ -v --ignore=tests/test_generate_skills_cli.py::TestGenerateSkillsIntegration
```

Expected: All tests PASS

**Step 7.2: Final commit**

```bash
git add .
git commit -m "feat: complete Skill Extractor implementation

- Add BusinessSkill and DataSkill Pydantic models
- Add CodeScanner for directory walking and file chunking
- Add SkillExtractionService for LLM-based skill extraction
- Add SkillWriterService with content-hash deduplication
- Add generate_skills.py CLI script
- Extend SkillsService to search new skill types

Usage: python scripts/generate_skills.py --scan-path /path/to/code"
```

---

## Summary

| Task | Files | Purpose |
|------|-------|---------|
| 1 | `app/models/schemas.py` | Pydantic models for BusinessSkill, DataSkill |
| 2 | `app/services/code_scanner.py` | Walk directories, filter noise, chunk large files |
| 3 | `app/services/skill_extraction_service.py` | LLM integration for skill classification |
| 4 | `app/services/skill_writer_service.py` | Write skills with deduplication |
| 5 | `scripts/generate_skills.py` | CLI entry point |
| 6 | `app/services/skills_service.py` | Search new skill types |
| 7 | - | Final integration testing |

---

## CLI Usage

```bash
# Basic usage - scan external code directory
python scripts/generate_skills.py --scan-path /path/to/analytics-code/

# Preview mode - see what would be extracted without LLM calls
python scripts/generate_skills.py --scan-path /path/to/code --dry-run

# Custom extensions - only SQL files
python scripts/generate_skills.py --scan-path /path/to/db-scripts --extensions .sql

# Custom output directory
python scripts/generate_skills.py --scan-path /path/to/code --output-dir ./my-skills/
```

## How the Agent Uses Skills

After generation, the agent's workflow becomes:

1. **User Request:** "Show me the revenue growth for last quarter"
2. **Skill Discovery:** Agent searches `skills/business/` and `skills/data/`
3. **Selection:**
   - Picks **Business Skill**: "Revenue Growth Analysis" (knows the calculation logic)
   - Picks **Data Skill**: "User Tables" (knows to filter `is_active = 1`)
4. **Execution:** Generates SQL using the skill context
