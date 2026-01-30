# Skills-Based Data Source Discovery System - Design Document

**Date:** 2026-01-29  
**Status:** Approved  
**Target System:** Octofy AI Agent (Medical Research Data Discovery)

---

## 1. Architecture Overview

### Problem Statement

In complex medical research systems with multiple disease databases, file-based data sources, and external integrations, researchers spend significant time discovering which data sources contain relevant information. Current RAG-only approaches return flat table lists without organizational context.

**Real-World Example:**
A researcher asks: *"Show me ECG data for patients"*

Current system returns a flat list of 8+ tables without context:
- `Legacy.ECG_PreProcedure`
- `Legacy.ECG_PostProcedure`
- `dbo.ECG_PreProcedure`
- `dbo.ECG_PostProcedure`
- ... (4 more tables)

**Challenge:** Researcher doesn't know:
- Which era of data (1990-2000 vs. 2000-present)
- Schema differences between Legacy and dbo
- Which timepoints are available (pre/post/3-month/1-year)

### Solution

A hierarchical skills-based discovery system that provides:
- **Curated data source catalog** (filesystem-based skill files)
- **Three-pronged discovery** (Skills → Value Index → Knowledge Base)
- **Adaptive user interaction** (auto-proceed for simple queries, guided selection for complex)
- **Smart recommendations** (LLM-powered data source suggestions)

### Core Principles

1. **Skills-first with RAG fallback** - Curated metadata guides discovery, vector search fills gaps
2. **Context-aware thresholds** - Cross-schema/cross-database triggers lower table count threshold
3. **Preserve existing investments** - Keep value_index and fewshot_index, deprecate schema_index
4. **User control for ambiguity** - Present grouped recommendations when multiple valid choices exist

---

## 2. Skills File Structure & Metadata Format

**Key Design Decision:** Separate logical organization (data groups) from physical schema storage.

```
skills/data-sources/
├── _index.md                                    # Top-level catalog
├── cardiology-db/
│   ├── _data-source.md                         # Connection info, DB type
│   ├── data-groups/
│   │   ├── _heart-surgery-data-group.md        # Logical group definition
│   │   │   ├── assessment.md                   # Brief description (references schemas/)
│   │   │   ├── booking.md
│   │   │   ├── surgery.md
│   │   │   └── discharge.md
│   │   └── _ecg-data-group.md
│   │       ├── pre-procedure.md                # Brief description
│   │       └── post-procedure.md
│   ├── patient-demographics/
│   │   └── _data-group.md
│   └── schemas/                                # Physical schema storage
│       ├── legacy/
│       │   ├── Legacy.ECG_PreProcedure.md      # Full schema: columns, types, FKs
│       │   └── Legacy.ECG_PostProcedure.md
│       └── dbo/
│           ├── dbo.ECG_PreProcedure.md
│           ├── dbo.ECG_PostProcedure.md
│           ├── dbo.Patients.md
│           └── dbo.PatientHistory.md
├── pharmacy-db/
│   ├── _data-source.md
│   ├── data-groups/
│   │   └── _medications-group.md
│   └── schemas/
│       └── dbo/
│           ├── dbo.Medications.md
│           └── dbo.Prescriptions.md
└── legacy-files/
    ├── _data-source.md
    ├── data-groups/
    │   └── _excel-reports-group.md
    └── schemas/
        └── files/
            ├── RegionalSales_2015.xlsx.md      # Schema for Excel file
            └── PatientOutcomes_Q1.xlsx.md
```

**Benefits of This Structure:**
- **Separation of Concerns:** Data groups define logical organization; schemas/ contains technical details
- **Schema Reusability:** One table schema can belong to multiple data groups
- **Easier Management:** All schemas for a database organized by schema name (legacy/dbo)
- **Cross-Group References:** Data groups can reference the same table without duplication

---

## 3. Discovery Workflow (Skills-First with RAG Fallback)

### Entry Point
User submits query via `/api/v1/generate-sql`

### Stage 1: Query Analysis & Entity Extraction
- Extract keywords (ECG, patients, aspirin)
- Extract date ranges (if present)
- Classify intent (simple vs complex)

### Stage 2: Three-Pronged Discovery (Parallel)

#### 2A. Skills Navigation (Primary)
1. Keyword search all `_data-group.md` files
2. Score matches by keyword frequency
3. Collect matched data groups
4. **Result:** List of data groups + table paths

#### 2B. Value Index Search (Entity Mapping)
1. Extract entities: "aspirin"
2. Search `value_index` in Milvus
3. Map to tables: `dbo.Medications`
4. **Result:** List of tables containing entities

#### 2C. Knowledge Base Search (Query Patterns)
1. Vector search `fewshot_index`
2. Find similar past queries
3. Extract tables from SQL with LLM
4. **Result:** List of tables from similar queries

### Stage 3: LLM Validation & Candidate Selection
- LLM reads matched data groups (`_data-group.md` files)
- Validates: "Does ecg-data group answer the query?"
- Collects candidate tables from validated groups
- Merges with value_index and knowledge base results
- **Result:** Unified candidate table list

### Stage 4: Reranking & Deduplication

**Scoring Logic:**
```
scores[table] = (
    10 * (table in skills_match) +      # Authoritative
    8 * (table in value_index) +        # Exact entity match
    5 * (table in knowledge_base)       # Proven query pattern
)
```

**Deduplication:** Normalize `[dbo].[Table]` vs `dbo.Table`

### Stage 5: Smart Threshold Decision

**Decision Logic:**
```python
IF (cross_schema OR cross_database) AND tables >= 5:
    → Trigger user selection
ELSE IF tables >= 10:
    → Trigger user selection
ELSE IF tables < 3:
    → Request clarification from user
ELSE:
    → Auto-proceed to Stage 7
```

**Thresholds:**
- **Cross-schema/database:** 5 tables (lower threshold for ambiguity)
- **Same database:** 10 tables (higher threshold for speed)
- **Insufficient results:** <3 tables (ask user for more details)

### Stage 6: User Selection (If Threshold Exceeded)

**Presentation Format:**
```
🎯 Recommended (LLM confidence > 80%):
  ☑ dbo.ECG_PreProcedure (2000-present)
  ☑ dbo.Medications

⚠️ Ambiguous - Select Era:
  □ Legacy schema (1990-2000) - 8 tables
  □ Modern schema (2000-present) - 8 tables

📁 Additional Options:
  □ Pharmacy Database (6 tables)
```

User selects → Filter candidate list

### Stage 7: Context Expansion (Reference Tables)
- LLM analyzes selected tables
- Identifies missing FK relationships
- Suggests intermediate tables (e.g., `PatientProcedures`)
- Load table schemas from `skills/{table-name}.md` files
- Add to final context

### Stage 8: Schema Loading & SQL Generation
- Read individual table `.md` files from skills
- Build `DiscoveryContext` with full schemas
- Pass to existing `generation_service.py`
- Iterative validation loop (unchanged)

### Fallback: Insufficient Results (<3 candidates)

**Response to User:**
```
I found limited relevant data for your query:
 - 1 table from skills (dbo.ECG_PreProcedure)
 - 0 results from value index
 - 0 similar queries

To improve results, please provide more details:

1. What specific time period? (e.g., 2010-2020)
2. Which disease area? (cardiology/oncology/etc.)
3. Are you looking for:
   □ Patient demographics
   □ Procedure data
   □ Lab results
   □ Medications
4. Any specific data source you know exists?
```

User provides clarification → Re-run discovery with enhanced query

---

## 4. Skills File Format Specifications

### 4.1 Top-Level Index (`_index.md`)

**Purpose:** Catalog of all available data sources

**Format:**
```markdown
# Data Sources Catalog

Last updated: 2026-01-29

## Available Data Sources

### Cardiology Database
**Type:** SQL Server  
**Status:** Active  
**Description:** Cardiac procedures, ECG data, patient outcomes (1990-present)  
**Keywords:** heart, cardiac, ECG, electrocardiogram, procedure, catheterization  
**Skill File:** [cardiology-db/_data-source.md](cardiology-db/_data-source.md)

### Pharmacy Database  
**Type:** SQL Server  
**Status:** Active  
**Description:** Medication records, prescriptions, drug interactions  
**Keywords:** medication, drug, prescription, pharmacy, dosage  
**Skill File:** [pharmacy-db/_data-source.md](pharmacy-db/_data-source.md)

### Legacy Clinical Files
**Type:** Excel/CSV Files  
**Status:** Archive (read-only)  
**Description:** Pre-2000 clinical trial data, manual data entry  
**Keywords:** legacy, clinical trial, historical, Excel  
**Skill File:** [legacy-files/_data-source.md](legacy-files/_data-source.md)

### External Lab Systems
**Type:** REST API (JSON)  
**Status:** Active  
**Description:** Real-time lab results from Quest/LabCorp integrations  
**Keywords:** lab, laboratory, blood test, pathology, external  
**Skill File:** [external-systems/_data-source.md](external-systems/_data-source.md)
```

---

### 4.2 Data Source File (`_data-source.md`)

**Purpose:** Connection details and data source overview

**Format:**
```markdown
# Cardiology Database

**Type:** Microsoft SQL Server  
**Server:** MEDSQL01.hospital.org  
**Database:** CardiologyDB  
**Status:** Active  
**Maintainer:** Dr. Sarah Chen (cardiology-data@hospital.org)  
**Last Sync:** 2026-01-28

## Description

Primary database for all cardiac-related procedures, diagnostics, and patient outcomes. Contains data from 1990-present with schema migration in 2000.

## Data Coverage

- **Time Range:** 1990-01-01 to present
- **Patient Records:** ~125,000 unique patients
- **Procedure Records:** ~45,000 procedures
- **Update Frequency:** Real-time (procedures), Daily batch (ECG data)

## Schema Notes

- **Legacy schema:** Data from 1990-2000, archived structure
- **dbo schema:** Modern structure from 2000-present
- **Cross-reference:** Legacy.PatientID maps to dbo.PatientID via migration table

## Connection Method

```python
# SQL Server connection via pyodbc
connection_string = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=MEDSQL01.hospital.org;"
    "DATABASE=CardiologyDB;"
    "Trusted_Connection=yes;"
)
```

## Data Groups

### [data-groups/_ecg-data-group.md](data-groups/_ecg-data-group.md)
Electrocardiogram measurements across procedure timeline (pre, post, follow-ups)

### [data-groups/_procedure-data-group.md](data-groups/_procedure-data-group.md)
Cardiac catheterization, angioplasty, stent placement records

### [data-groups/_patient-demographics-group.md](data-groups/_patient-demographics-group.md)
Patient demographics, medical history, risk factors

## Physical Schemas

All table schemas are stored in the `schemas/` directory, organized by database schema:
- **schemas/legacy/** - Legacy schema tables (1990-2000)
- **schemas/dbo/** - Modern dbo schema tables (2000-present)
```

---

### 4.3 Data Group File (`_data-group.md`)

**Purpose:** Logical grouping of related tables with keywords. References physical schemas in `../schemas/` directory.

**Format:**
```markdown
# ECG Data Group

**Data Source:** Cardiology Database  
**Category:** Diagnostic Measurements  
**Status:** Active  
**Keywords:** electrocardiogram, ECG, EKG, cardiac rhythm, QRS, heart rate, baseline, follow-up, pre-procedure, post-procedure

## Description

Electrocardiogram measurements collected at various timepoints in the patient care pathway:
- **Pre-procedure:** Baseline cardiac function before intervention
- **Post-procedure:** Immediate post-intervention assessment
- **3-month follow-up:** Short-term recovery monitoring
- **1-year follow-up:** Long-term outcome assessment

## Schema Migration Notes

Data collection methodology changed in 2000:
- **Legacy (1990-2000):** Analog ECG machines, manual digitization, stored in Legacy schema
- **Modern (2000-present):** Digital ECG systems, automated import, stored in dbo schema

⚠️ **Important:** Legacy and modern schemas have different column structures. Join via CardiologyDB.dbo.PatientMigrationMap for cross-era analysis.

## Data Objects

### Legacy Schema (1990-2000)

- **[Legacy.ECG_PreProcedure](../schemas/legacy/Legacy.ECG_PreProcedure.md)** - Baseline ECG before cardiac procedures (~8,500 records)
- **[Legacy.ECG_PostProcedure](../schemas/legacy/Legacy.ECG_PostProcedure.md)** - Immediate post-procedure ECG (~8,200 records)
- **[Legacy.ECG_3MonthFollowup](../schemas/legacy/Legacy.ECG_3MonthFollowup.md)** - 3-month follow-up ECG (~6,100 records)
- **[Legacy.ECG_1YearFollowup](../schemas/legacy/Legacy.ECG_1YearFollowup.md)** - 1-year follow-up ECG (~4,800 records)

### Modern Schema (2000-present)

- **[dbo.ECG_PreProcedure](../schemas/dbo/dbo.ECG_PreProcedure.md)** - Enhanced baseline with digital storage (~36,500 records)
- **[dbo.ECG_PostProcedure](../schemas/dbo/dbo.ECG_PostProcedure.md)** - Digital post-procedure measurements (~35,800 records)
- **[dbo.ECG_3MonthFollowup](../schemas/dbo/dbo.ECG_3MonthFollowup.md)** - Automated 3-month follow-up (~28,200 records)
- **[dbo.ECG_1YearFollowup](../schemas/dbo/dbo.ECG_1YearFollowup.md)** - Long-term outcome tracking (~22,100 records)

## Common Use Cases

- Longitudinal cardiac function analysis across procedure timeline
- Pre/post procedure comparisons (paired analysis)
- Long-term outcome studies (1-year follow-up)
- Cross-era trend analysis (requires migration mapping)

## Related Data Groups

- [_procedure-data-group.md](_procedure-data-group.md) - Links via ProcedureID
- [_patient-demographics-group.md](_patient-demographics-group.md) - Links via PatientID
```

---

### 4.4 Table Schema File (e.g., `schemas/dbo/dbo.ECG_PreProcedure.md`)

**Purpose:** Complete table schema for SQL generation (replaces Milvus schema_index)

**Location:** Stored in `{data-source}/schemas/{schema-name}/` directory

**Format:**
```markdown
# Table: [dbo].[ECG_PreProcedure]

**Data Source:** Cardiology Database  
**Schema:** dbo  
**Type:** Table  
**Era:** 2000-present  
**Record Count:** ~36,500  
**Update Frequency:** Daily batch

## Description

Baseline electrocardiogram measurements taken before cardiac procedures. Digital recordings from automated ECG systems with standardized measurement protocols. Used for pre-procedure risk assessment and baseline cardiac function evaluation.

## Columns

### ECG_ID (INT) - Primary Key
Unique identifier for each ECG recording. Auto-incremented starting from 100000.

### PatientID (INT) - Foreign Key
References [dbo].[Patients].[PatientID]. Links to patient demographics and medical history.

### ProcedureID (INT) - Foreign Key
References [dbo].[Procedures].[ProcedureID]. Associated cardiac procedure that this ECG precedes.

### RecordingDate (DATETIME)
Timestamp of ECG capture. Typically 1-7 days before procedure date.

### HeartRate (INT)
Heart rate in beats per minute. Normal range: 60-100 bpm.

### QRSDuration (DECIMAL(5,2))
QRS complex duration in milliseconds. Normal range: 80-120ms. Prolonged QRS may indicate conduction abnormalities.

### PRInterval (DECIMAL(5,2))
PR interval in milliseconds. Normal range: 120-200ms. Measures AV conduction time.

### QTInterval (DECIMAL(5,2))
QT interval in milliseconds. Corrected for heart rate using Bazett's formula.

### STSegmentElevation (BIT)
Boolean flag: 1 = ST elevation present (possible acute MI), 0 = normal ST segment.

### RhythmType (VARCHAR(50))
Cardiac rhythm classification: 'Normal Sinus', 'Atrial Fibrillation', 'Atrial Flutter', 'Ventricular Tachycardia', etc.

### InterpretationNotes (VARCHAR(MAX))
Cardiologist interpretation notes. Free-text field with clinical observations.

### TechnicianID (INT)
References [dbo].[MedicalStaff].[StaffID]. Technician who performed the ECG recording.

### DeviceSerialNumber (VARCHAR(50))
ECG machine identifier for quality control and calibration tracking.

### CreatedDate (DATETIME)
Record creation timestamp in database.

### ModifiedDate (DATETIME)
Last modification timestamp.

## Common Queries

- Pre-procedure risk assessment (abnormal rhythms before intervention)
- QRS duration trends for bundle branch block studies
- ST elevation identification for acute MI cases
- Rhythm distribution analysis (AF prevalence)

## Related Tables

- **[dbo.ECG_PostProcedure](dbo.ECG_PostProcedure.md)** - Post-procedure measurements (join on ProcedureID)
- **[dbo.Patients](dbo.Patients.md)** - Patient demographics (join on PatientID)
- **[dbo.Procedures](../../../procedure-data/schemas/dbo/dbo.Procedures.md)** - Procedure details (join on ProcedureID)
- **[dbo.MedicalStaff](../../schemas/dbo/dbo.MedicalStaff.md)** - Staff information (join on TechnicianID)

## Data Quality Notes

- Missing data rate: ~2% for HeartRate, ~5% for QT intervals
- InterpretationNotes are NULL for automated readings (no cardiologist review)
- DeviceSerialNumber standardized in 2015; earlier records may have inconsistent formats
```

---

## 5. Implementation Components

### 5.1 New Service: `skills_service.py`

**Location:** `app/services/skills_service.py`

**Responsibilities:**
- Load and parse skill files from filesystem
- Keyword matching across data groups
- LLM validation of matched groups
- Build candidate table lists from skills

**Key Functions:**
```python
def load_data_sources_index() -> List[DataSource]:
    """Parse _index.md and return all data sources"""

def search_data_groups_by_keywords(query: str, keywords: List[str]) -> List[DataGroup]:
    """Keyword match against all _data-group.md files"""

def validate_groups_with_llm(query: str, matched_groups: List[DataGroup]) -> List[DataGroup]:
    """LLM validates relevance of matched groups"""

def load_table_schemas(table_paths: List[str]) -> List[TableSchema]:
    """Read individual table .md files and parse into TableSchema objects"""

def get_data_group_metadata(group_path: str) -> DataGroupMetadata:
    """Parse _data-group.md file for keywords, description, table list"""
```

---

### 5.2 Modified Service: `discovery_service.py`

**Changes:**
- Replace `schema_index` vector search with skills navigation
- Keep `value_index` and `fewshot_index` searches (unchanged)
- Add three-pronged discovery orchestration
- Implement smart threshold logic
- Generate user selection prompts

**New/Modified Functions:**
```python
def perform_skills_based_discovery(query: str) -> SkillsDiscoveryResult:
    """
    Stage 2A: Skills navigation
    - Extract keywords from query
    - Search data groups via skills_service
    - Return matched tables from skills
    """

def perform_three_pronged_discovery(query: str) -> ThreeProngedResult:
    """
    Orchestrates parallel discovery:
    - Skills navigation (primary)
    - Value index search (entity mapping)
    - Knowledge base search (query patterns)
    Returns merged candidate list
    """

def rerank_candidates(skills_tables, value_tables, kb_tables) -> List[RankedTable]:
    """
    New scoring:
    - Skills match: +10 points
    - Value index: +8 points
    - Knowledge base: +5 points
    """

def check_smart_threshold(candidates: List[RankedTable]) -> ThresholdDecision:
    """
    Analyzes:
    - Total table count
    - Cross-schema detection (Legacy + dbo)
    - Cross-database detection
    Returns: auto_proceed=True/False
    """

def generate_user_selection_prompt(candidates: List[RankedTable], query: str) -> SelectionPrompt:
    """
    Groups candidates by:
    - Recommended (LLM confidence > 80%)
    - Ambiguous (user must choose)
    - Additional options
    """

def apply_user_selection(candidates: List[RankedTable], user_choices: List[str]) -> List[RankedTable]:
    """Filter candidates based on user's checkbox selections"""
```

---

### 5.3 Modified Service: `generation_service.py`

**Changes:**
- Replace `hydrate_discovery_context()` to load from skills instead of Milvus
- Keep iterative validation loop (unchanged)
- Update context expansion to use skills for missing tables

**Modified Functions:**
```python
def hydrate_discovery_context(table_names: List[str], similar_queries: List[Dict]) -> DiscoveryContext:
    """
    OLD: Fetched from Milvus schema_index
    NEW: Load from skills/{data-source}/{group}/{table}.md files
    Returns same DiscoveryContext structure
    """

def expand_context_with_neighbors(selected_tables: List[str], query: str) -> List[str]:
    """
    OLD: Used schema_index for verification
    NEW: Search skills files for suggested intermediate tables
    """
```

---

### 5.4 New Data Models (`models/schemas.py`)

```python
class DataSource(BaseModel):
    """Parsed from _data-source.md"""
    name: str
    type: str  # "SQL Server", "Excel", "JSON API", etc.
    description: str
    keywords: List[str]
    status: str  # "Active", "Archive", "Deprecated"
    connection_info: Optional[Dict]
    data_groups: List[str]  # Paths to group files

class DataGroup(BaseModel):
    """Parsed from _data-group.md"""
    name: str
    data_source: str
    description: str
    keywords: List[str]
    tables: List[str]  # Paths to table .md files
    schema_notes: Optional[str]

class RankedTable(BaseModel):
    """Discovery result with scoring"""
    schema_name: str
    table_name: str
    score: int
    matched_by: List[str]  # ["skills", "value_index", "knowledge_base"]
    data_source: str
    data_group: str

class ThresholdDecision(BaseModel):
    """Smart threshold analysis result"""
    auto_proceed: bool
    total_tables: int
    cross_schema: bool
    cross_database: bool
    trigger_reason: Optional[str]

class SelectionPrompt(BaseModel):
    """User selection UI data"""
    recommended: List[RankedTable]  # LLM confidence > 80%
    ambiguous_groups: List[Dict]  # Requires user choice
    additional_options: List[Dict]  # Extra possibilities
```

---

### 5.5 New API Endpoint Enhancement

**Modified:** `/api/v1/generate-sql` (streaming endpoint)

**New Response Events (SSE):**

```python
# New event: Discovery results require user input
{
    "event": "user_selection_required",
    "data": {
        "threshold_reason": "cross_schema_detected",
        "total_candidates": 18,
        "selection_prompt": {
            "recommended": [...],
            "ambiguous_groups": [...],
            "additional_options": [...]
        }
    }
}

# New event: Insufficient results, ask for clarification
{
    "event": "clarification_needed",
    "data": {
        "found_count": 2,
        "message": "Limited relevant data found. Please provide more details...",
        "suggestions": [
            "What specific time period?",
            "Which disease area?",
            ...
        ]
    }
}

# Existing events remain unchanged:
# - discovery_complete
# - sql_generated
# - validation_complete
# - execution_complete
```

**New Request Parameter:**
```python
class GenerateSQLRequest(BaseModel):
    # ... existing fields ...
    
    user_selected_tables: Optional[List[str]] = None  # NEW: User's checkbox selections
```

---

## 6. Migration Strategy

### 6.1 Deprecate Milvus `schema_index` Collection

**Phase 1: Create Skills Files (Manual/Scripted)**
- Option A: Manual creation for medical databases (curated, high-quality)
- Option B: Auto-generate from existing Milvus data + manual enhancement
- **Recommended:** Hybrid - auto-generate structure, manually enrich with keywords/notes

**Script:** `scripts/migrate_milvus_to_skills.py`
```python
"""
Reads schema_index collection from Milvus
Generates skills file structure:
- _index.md (from all unique data sources)
- _data-source.md (grouped by schema_name)
- _data-group.md (logical grouping by table prefixes/naming conventions)
- {table}.md (individual table schemas from Milvus descriptions)

Manual enhancement needed:
- Add keywords to data groups
- Add schema migration notes
- Add connection info to data sources
- Organize tables into logical groups
"""
```

**Phase 2: Parallel Operation (Testing)**
- Keep schema_index active
- Run skills-based discovery in parallel
- Compare results for accuracy
- Log discrepancies for tuning

**Phase 3: Switch & Archive**
- Enable skills-based discovery as default
- Keep schema_index read-only (fallback)
- After 30 days of stable operation, drop collection

---

### 6.2 Keep `value_index` and `fewshot_index` Unchanged

**Rationale:**
- `value_index`: Entity mapping ("aspirin" → table) is orthogonal to structure
- `fewshot_index`: Query patterns proven effective, no need to migrate

**Enhancement (Optional):**
- Add `data_source` field to both collections for scoped search
- Example: Search fewshots only within "Cardiology Database"

---

## 7. Testing Strategy

### 7.1 Unit Tests

**Test Coverage:**
```python
# test_skills_service.py
- test_load_data_sources_index()
- test_search_data_groups_by_keywords()
- test_validate_groups_with_llm()
- test_load_table_schemas()

# test_discovery_service.py
- test_three_pronged_discovery()
- test_rerank_candidates()
- test_check_smart_threshold()
- test_generate_user_selection_prompt()

# test_skills_parser.py
- test_parse_data_source_markdown()
- test_parse_data_group_markdown()
- test_parse_table_schema_markdown()
```

---

### 7.2 Integration Tests

**Scenario 1: Simple Query (Auto-Proceed)**
```
Query: "Show me all patients in the Cardiology database"
Expected: 
- Skills finds patient-demographics group
- <5 tables, single database
- Auto-proceeds without user selection
- Generates SQL successfully
```

**Scenario 2: Cross-Schema Query (User Selection)**
```
Query: "ECG data for patients with abnormal rhythms"
Expected:
- Skills finds ecg-data group (8 tables: Legacy + dbo)
- Crosses schema boundary, triggers threshold
- Presents user selection UI
- User selects dbo schema only
- Generates SQL with dbo.ECG_* tables
```

**Scenario 3: Entity-Driven Query (Value Index)**
```
Query: "Patients on aspirin"
Expected:
- Skills finds limited matches (no "aspirin" keyword)
- Value index finds: dbo.Medications table
- Merges results, auto-proceeds
- Generates SQL with Medications table
```

**Scenario 4: Knowledge Base Match**
```
Query: "Show me patients with cardiovascular events"
Expected:
- Skills finds procedure-data group
- Knowledge base finds similar query with SQL
- Extracts tables from past SQL
- Merges, high confidence, auto-proceeds
```

**Scenario 5: Insufficient Results**
```
Query: "Genomic data for lung cancer patients"
Expected:
- Skills finds 0 groups (no genomics database)
- Value index finds 0 results
- Knowledge base finds 1 unrelated query
- Total <3 candidates
- Returns clarification request to user
```

---

### 7.3 User Acceptance Testing

**Test with Real Medical Researchers:**
1. Provide 10 sample research questions across disease areas
2. Measure:
   - Time to find correct data sources (vs. current system)
   - Accuracy of auto-selected tables
   - User satisfaction with selection UI
   - False positive rate (wrong tables included)
3. Collect feedback on:
   - Keyword coverage in data groups
   - Usefulness of schema migration notes
   - Clarity of user selection prompts

---

## 8. Deployment Plan

### Prerequisites
- [ ] Skills directory structure created: `skills/data-sources/`
- [ ] Migration script tested on dev environment
- [ ] At least 2 data sources fully documented (e.g., Cardiology + Pharmacy)
- [ ] Unit tests passing (>80% coverage)
- [ ] Integration tests passing (all 5 scenarios)

### Deployment Steps

**Week 1: Skills Creation (Dev Environment)**
- Run migration script to generate initial skills
- Manual enhancement: add keywords, notes, connection info
- Validate markdown parsing

**Week 2: Code Integration (Dev Environment)**
- Implement `skills_service.py`
- Modify `discovery_service.py` (parallel mode)
- Add new API events for user selection
- Deploy to dev, test with Northwind sample database

**Week 3: Testing & Tuning (Staging Environment)**
- Run integration test suite
- Compare skills-based vs. Milvus-based discovery results
- Tune keyword matching and scoring weights
- UAT with 2-3 internal researchers

**Week 4: Production Rollout (Phased)**
- **Phase A:** Enable for 10% of queries (feature flag)
- **Phase B:** If metrics good, increase to 50%
- **Phase C:** Full rollout, deprecate schema_index
- Monitor error rates, user feedback, query success rate

### Rollback Plan
- Feature flag to instantly switch back to Milvus schema_index
- Keep schema_index collection for 30 days post-rollout
- Log comparison data for post-mortem analysis

---

## 9. Future Enhancements (Post-MVP)

### 9.1 Advanced Features
- **Skills versioning**: Track changes to data source schemas over time
- **Access control**: Tag data groups with security levels, filter by user role
- **Data lineage**: Document ETL pipelines in `_data-source.md`
- **Sample queries**: Add common query templates to `_data-group.md`
- **Performance caching**: Cache parsed skills in Redis for faster lookup

### 9.2 UI Enhancements
- **Visual data catalog**: Browse skills hierarchy in frontend
- **Data preview**: Show sample rows from selected tables
- **Selection history**: "You used these tables last time for similar query"
- **Saved selections**: "Save as research template" for common patterns

### 9.3 AI Enhancements
- **Semantic skill search**: Embed data group descriptions for vector search
- **Auto-tagging**: LLM suggests keywords for new data groups
- **Smart defaults**: Learn user preferences (always use dbo, never Legacy)

---

## 10. Summary

This design provides:

✅ **Hierarchical data source discovery** via filesystem-based skills  
✅ **Three-pronged search** (Skills + Value Index + Knowledge Base)  
✅ **Smart user interaction** (context-aware thresholds)  
✅ **Backward compatibility** (keeps existing value_index and fewshot_index)  
✅ **Clear migration path** (deprecate schema_index safely)  
✅ **Medical research optimized** (handles cross-schema, cross-era data)

### Key Design Decisions

- ✅ Skills-first with RAG fallback
- ✅ Keyword matching + LLM validation
- ✅ Skills replace schema_index, keep value/knowledge indices
- ✅ Smart recommendations UI with grouped options
- ✅ Markdown format for all skills (simple, LLM-friendly)
- ✅ Table count threshold: 5 (cross-schema/DB) or 10 (same DB)
- ✅ Insufficient results (<3): Request clarification from user

---

**Document Status:** Ready for Implementation  
**Next Steps:** Begin Week 1 - Skills creation and migration script development
