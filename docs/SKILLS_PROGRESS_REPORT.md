# Skills-Based Discovery Implementation - Progress Report

**Date:** January 29, 2026  
**Status:** Core Implementation Complete - API Integration Pending

---

## ✅ Completed Work

### 1. Migration from Milvus to Skills (100% Complete)

**Script:** `scripts/migrate_milvus_to_skills.py`

- ✅ Successfully migrated 39 tables from Milvus `schema_index` collection
- ✅ Generated complete skills directory structure:
  ```
  skills/data-sources/
  ├── _index.md
  └── dbo-database/
      ├── _data-source.md
      ├── data-groups/       (39 group files)
      └── schemas/dbo/       (39 table files)
  ```
- ✅ Fixed Windows console emoji encoding issues
- ✅ Auto-inferred logical data groups from table names

**Issues Fixed:**
- Unicode encoding errors in Windows console (replaced emojis with `[INFO]`, `[SUCCESS]`, etc.)
- Column parsing from markdown table format

---

### 2. Skills Service Implementation (100% Complete)

**File:** `app/services/skills_service.py` (615 lines)

#### Implemented Features:

**A. Data Source Loading**
- ✅ `load_data_sources_index()` - Parse `_index.md`
- ✅ Singleton pattern with caching (`get_skills_service()`)

**B. Data Group Discovery**
- ✅ `load_all_data_groups()` - Load all `_*-group.md` files
- ✅ `search_data_groups_by_keywords()` - Keyword-based matching with intelligent scoring:
  - **10 points** - Exact keyword match
  - **8 points** - Substring match in name
  - **5 points** - Substring match in description
  - **2 points** - Match anywhere in searchable text
  - **Bonus** - Multiple keyword matches, phrase matching

**C. Table Schema Loading**
- ✅ `load_table_schemas()` - Load table schemas from markdown files
- ✅ `_find_and_parse_table()` - Find table by name (`schema.table` format)
- ✅ `_parse_table_schema_file()` - Parse individual table markdown
- ✅ `_parse_columns_from_table()` - Parse columns from markdown table format (fallback)

**Issues Fixed:**
- Fixed glob pattern to find `_*-group.md` files (was looking for `_data-group.md` exactly)
- Added support for table name lookups (not just file paths)
- Added fallback column parsing from markdown tables (since migrated files had columns in tables, not `### ColumnName (DataType)` format)

---

### 3. Enhanced Discovery Service (100% Complete)

**File:** `app/services/discovery_service.py` (550 lines, complete rewrite)

#### Implemented Three-Pronged Discovery:

**Stage 2A - Skills Navigation (Primary)**
```python
perform_skills_based_discovery(query, llm_service) -> SkillsDiscoveryResult
```
- Keyword matching on data groups
- Returns matched groups + candidate tables with scores

**Stage 2B - Value Index Search**
```python
perform_value_index_search(query, top_k=5) -> List[RankedTable]
```
- Entity-to-table mapping via Milvus `value_index`
- Maps user terms ("North America") to database values

**Stage 2C - Knowledge Base Search**
```python
perform_knowledge_base_search(query, llm_service, top_k=3) -> List[RankedTable]
```
- Similar query pattern matching via Milvus `fewshot_index`
- Extracts tables from similar past queries

**Orchestration & Reranking**
```python
perform_three_pronged_discovery(query, llm_service) -> ThreeProngedResult
```
- Runs all three methods in parallel
- Merges and deduplicates results
- Reranking scores:
  - Skills: +10
  - Value Index: +8
  - Knowledge Base: +5

**Smart Threshold Logic**
```python
check_smart_threshold(candidates) -> ThresholdDecision
```
- **Cross-schema/database + ≥5 tables** → Ask user
- **Same database + ≥10 tables** → Ask user
- **<3 tables** → Request clarification
- **Otherwise** → Auto-proceed

**User Selection Prompt Generation**
```python
generate_user_selection_prompt(candidates, query, llm_service) -> SelectionPrompt
```
- Groups candidates into:
  - **Recommended** (score ≥15, high confidence)
  - **Ambiguous** (cross-schema scenarios requiring user choice)
  - **Additional Options** (other possibilities)

**Selection Application**
```python
apply_user_selection(candidates, user_choices) -> List[RankedTable]
```
- Filters candidates based on user checkbox selections

**Schema Hydration from Skills**
```python
hydrate_discovery_context_from_skills(table_names, similar_queries) -> DiscoveryContext
```
- Loads full table schemas from skills markdown files
- Replaces Milvus `schema_index` lookups

**Issues Fixed:**
- Fixed import: Changed `LLMService` to `LLMServiceBase` (correct type)

---

### 4. Data Models (100% Complete)

**File:** `app/models/schemas.py` (+70 lines)

Added 9 new Pydantic models:
- `DataSource` - Parsed from `_data-source.md`
- `DataGroup` - Parsed from `_data-group.md`
- `RankedTable` - Discovery result with scoring
- `ThresholdDecision` - Smart threshold analysis result
- `SelectionPrompt` - User selection UI data structure
- `SkillsDiscoveryResult` - Skills navigation result
- `ThreeProngedResult` - Combined discovery result
- Updated `GenerateSQLRequest` with `user_selected_tables: Optional[List[str]]`

---

### 5. Testing (100% Complete)

**File:** `test_skills_quick.py` (created for testing)

All tests passing:
- ✅ **TEST 1:** Load data sources from `_index.md` (1 data source found)
- ✅ **TEST 2:** Keyword search (finding 4-10 groups per query)
  - "customer orders" → 10 groups, top score: 16
  - "product categories" → 10 groups, top score: 22
  - "employee information" → 4 groups
  - "sales by region" → 10 groups
- ✅ **TEST 3:** Load table schemas (3 tables loaded with 11+ columns each)
- ✅ **TEST 4:** Three-pronged discovery
  - Query: "Show me customers who ordered products in 1997"
  - Skills: 10 tables, Value Index: 0, Knowledge Base: 0
  - Merged: 10 candidates
  - Threshold decision: `high_table_count` (requires user selection)

---

## 📋 Remaining Work

### High Priority - API Integration

#### Task 4: Wire Discovery into `/api/v1/generate-sql` Endpoint

**File to modify:** `app/services/generation_service.py` (lines 482-525)

**Current Flow (Old Discovery):**
```python
# Lines 485-525: Multi-Source Discovery
value_tables = vector_store.search_values(...)
similar_queries = vector_store.search_fewshots(...)
schema_results = vector_store.search_schemas(...)  # ← REPLACE THIS
final_table_list = rerank_and_select_tables(...)
context = hydrate_discovery_context(...)
```

**New Flow (Skills-Based Discovery):**
```python
from app.services.discovery_service import (
    perform_three_pronged_discovery,
    check_smart_threshold,
    generate_user_selection_prompt,
    apply_user_selection,
    hydrate_discovery_context_from_skills
)

# Replace lines 482-525 with:
yield AgentStatus(step_id=5, message="Running skills-based discovery...")

# Run three-pronged discovery
discovery_result = perform_three_pronged_discovery(request.query, llm_service)

# Check threshold decision
threshold = check_smart_threshold(discovery_result.merged_candidates)

if not threshold.auto_proceed:
    if threshold.trigger_reason == "insufficient_results":
        # Emit clarification_needed event
        yield {
            "event": "clarification_needed",
            "data": {
                "found_count": threshold.total_tables,
                "message": f"Only found {threshold.total_tables} relevant tables...",
                "suggestions": [
                    "What specific time period are you interested in?",
                    "Which subject area or department?",
                    "Any specific data types or categories?"
                ]
            }
        }
        return
    else:
        # Emit user_selection_required event
        selection_prompt = generate_user_selection_prompt(
            discovery_result.merged_candidates,
            request.query,
            llm_service
        )
        yield {
            "event": "user_selection_required",
            "data": {
                "threshold_reason": threshold.trigger_reason,
                "total_candidates": threshold.total_tables,
                "selection_prompt": selection_prompt.dict()
            }
        }
        # Pause and wait for user response
        return

# Handle user selections if provided
if request.user_selected_tables:
    filtered = apply_user_selection(
        discovery_result.merged_candidates,
        request.user_selected_tables
    )
    table_names = [f"{t.schema_name}.{t.table_name}" for t in filtered]
else:
    # Auto-proceed: use top 8 candidates
    table_names = [f"{t.schema_name}.{t.table_name}" 
                   for t in discovery_result.merged_candidates[:8]]

# Hydrate context from skills
context = hydrate_discovery_context_from_skills(table_names, similar_queries)

# Continue with SQL generation...
```

---

#### Task 5: Add New SSE Event Types

**File to modify:** `app/api/endpoints/generation.py`

**New Event Types:**

1. **`clarification_needed`** - When <3 tables found
```json
{
    "event": "clarification_needed",
    "data": {
        "found_count": 2,
        "message": "Limited relevant data found. Please provide more details about your query.",
        "suggestions": [
            "What specific time period?",
            "Which subject area?",
            "Which data types?"
        ]
    }
}
```

2. **`user_selection_required`** - When threshold triggered
```json
{
    "event": "user_selection_required",
    "data": {
        "threshold_reason": "cross_schema_detected",
        "total_candidates": 18,
        "selection_prompt": {
            "recommended": [
                {
                    "schema_name": "dbo",
                    "table_name": "Customers",
                    "score": 25,
                    "sources": ["skills", "value_index"]
                }
            ],
            "ambiguous_groups": [
                {
                    "label": "Select Time Period",
                    "description": "Data spans multiple eras",
                    "options": [
                        {"label": "Legacy (1990-2000)", "tables": ["legacy.ECG", "legacy.Patients"]},
                        {"label": "Modern (2000-present)", "tables": ["dbo.ECG", "dbo.Patients"]}
                    ]
                }
            ],
            "additional_options": [...]
        }
    }
}
```

**Implementation:**
```python
# In app/api/endpoints/generation.py event_generator()
for item in generate_sql_for_request(request, ...):
    if isinstance(item, AgentStatus):
        yield f"data: {json.dumps(item.model_dump())}\n\n"
    elif isinstance(item, dict):
        # Handle new event types
        event_type = item.get("event", item.get("type"))
        
        if event_type == "clarification_needed":
            yield f"data: {json.dumps(item)}\n\n"
        elif event_type == "user_selection_required":
            yield f"data: {json.dumps(item)}\n\n"
        elif event_type == "result":
            # Existing result handling
            payload = item["payload"]
            data = {"type": "result", "payload": payload.model_dump(by_alias=True)}
            yield f"data: {json.dumps(data)}\n\n"
```

---

#### Task 6: Handle `user_selected_tables` Parameter

**Already done in Task 4 code above** - just needs integration testing.

---

### Medium Priority - Frontend Integration

#### Task 7: Update Frontend to Display Selection Prompts

**File:** Frontend chat interface component (React)

**A. Display User Selection Prompt**

```jsx
// When receiving user_selection_required event
const handleUserSelectionRequired = (data) => {
  const { selection_prompt, threshold_reason } = data;
  
  return (
    <div className="selection-prompt">
      <h3 className="text-lg font-bold">🎯 Select Relevant Data Sources</h3>
      <p className="text-sm text-gray-600 mb-4">
        Found {data.total_candidates} potential tables. 
        Reason: {threshold_reason}
      </p>
      
      {/* Recommended Tables */}
      <div className="recommended-section mb-4">
        <h4 className="font-semibold text-green-700">Recommended (High Confidence)</h4>
        {selection_prompt.recommended.map(table => (
          <Checkbox 
            key={`${table.schema_name}.${table.table_name}`}
            label={`${table.schema_name}.${table.table_name}`}
            description={`Score: ${table.score} | Sources: ${table.sources.join(', ')}`}
            defaultChecked={true}
          />
        ))}
      </div>
      
      {/* Ambiguous Groups (Radio/Select) */}
      {selection_prompt.ambiguous_groups.map(group => (
        <div key={group.label} className="ambiguous-section mb-4">
          <h4 className="font-semibold text-yellow-700">⚠️ {group.label}</h4>
          <p className="text-sm text-gray-600">{group.description}</p>
          <RadioGroup>
            {group.options.map(option => (
              <Radio 
                key={option.label}
                label={option.label}
                description={`Tables: ${option.tables.join(', ')}`}
              />
            ))}
          </RadioGroup>
        </div>
      ))}
      
      {/* Additional Options */}
      <details className="additional-section">
        <summary className="cursor-pointer font-semibold text-gray-700">
          Additional Options ({selection_prompt.additional_options.length})
        </summary>
        {selection_prompt.additional_options.map(table => (
          <Checkbox 
            key={`${table.schema_name}.${table.table_name}`}
            label={`${table.schema_name}.${table.table_name}`}
            description={`Score: ${table.score}`}
          />
        ))}
      </details>
      
      <button onClick={handleSubmitSelection} className="btn-primary mt-4">
        Continue with Selection
      </button>
    </div>
  );
};
```

**B. Send Selections Back to API**

```javascript
const handleSubmitSelection = () => {
  const selectedTables = getCheckedTables(); // ["dbo.Customers", "dbo.Orders"]
  
  // Re-submit query with user_selected_tables parameter
  fetch('/api/v1/generate-sql', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query: originalQuery,
      user_selected_tables: selectedTables,
      // ... other params
    })
  });
};
```

**C. Handle Clarification Needed**

```jsx
const handleClarificationNeeded = (data) => {
  return (
    <div className="clarification-prompt">
      <h3 className="text-lg font-bold">🔍 Need More Information</h3>
      <p className="text-gray-700 mb-2">{data.message}</p>
      <p className="text-sm text-gray-600 mb-4">Found {data.found_count} tables.</p>
      
      <div className="suggestions mb-4">
        <p className="font-semibold">Try adding details about:</p>
        <ul className="list-disc ml-6">
          {data.suggestions.map(s => <li key={s}>{s}</li>)}
        </ul>
      </div>
      
      <textarea 
        placeholder="Provide more specific details about your query..."
        onChange={handleClarificationInput}
        className="w-full border rounded p-2 mb-2"
      />
      
      <button onClick={handleResubmit} className="btn-primary">
        Search Again
      </button>
    </div>
  );
};
```

---

### Medium Priority - Testing

#### Task 8: Add Unit Tests

**Files to create:**

**A. `tests/test_skills_service.py`**
```python
def test_load_data_sources_index()
def test_search_data_groups_by_keywords()
def test_load_table_schemas_by_name()
def test_load_table_schemas_by_path()
def test_parse_markdown_table_columns()
def test_keyword_scoring_exact_match()
def test_keyword_scoring_name_match()
def test_keyword_scoring_description_match()
```

**B. `tests/test_discovery_service.py`**
```python
def test_three_pronged_discovery()
def test_rerank_candidates()
def test_check_smart_threshold_cross_schema()
def test_check_smart_threshold_high_count()
def test_check_smart_threshold_insufficient_results()
def test_check_smart_threshold_auto_proceed()
def test_user_selection_filtering()
def test_generate_user_selection_prompt()
def test_hydrate_discovery_context_from_skills()
```

**C. `tests/integration/test_skills_discovery_scenarios.py`**

Based on design document scenarios:
```python
def test_scenario_1_simple_query_auto_proceed():
    """Query: 'Show all customers' → Auto-proceed with <10 tables"""
    
def test_scenario_2_cross_schema_user_selection():
    """Query: 'Show ECG data' → User must choose Legacy vs Modern"""
    
def test_scenario_3_entity_driven_query():
    """Query: 'aspirin prescriptions' → Value index finds Medications"""
    
def test_scenario_4_knowledge_base_match():
    """Query similar to existing KB query → Inherits table selections"""
    
def test_scenario_5_insufficient_results():
    """Query: 'xyzabc123' → <3 tables, request clarification"""
```

---

### Low Priority - Enhancements

1. **LLM Validation of Data Groups**
   - Implement `validate_groups_with_llm()` stub
   - Ask LLM: "Does {group.description} answer the query: {query}?"

2. **Redis Caching**
   - Cache parsed skills for performance
   - Invalidate on file changes

3. **Better Keyword Extraction**
   - Use NLP (spaCy) in migration script
   - Extract technical terms more accurately

4. **Visual Data Catalog**
   - Admin UI to browse skills hierarchy
   - Edit data groups and tables in UI

5. **Skills Versioning**
   - Track schema changes over time
   - Support temporal queries ("data as of 2020")

---

## 🎯 Next Session Action Plan

### Step 1: Test API Integration (1-2 hours)

1. Create a test endpoint or modify existing endpoint
2. Add three-pronged discovery calls
3. Test threshold decisions manually
4. Verify events are emitted correctly

### Step 2: Frontend Prototyping (2-3 hours)

1. Add event listeners for new event types
2. Create selection prompt UI component
3. Wire up user selection submission
4. Test end-to-end flow

### Step 3: Integration Testing (1 hour)

1. Test complete flow: Query → Discovery → User Selection → SQL Generation
2. Test edge cases: no tables, too many tables, cross-schema
3. Performance testing with large skills directories

### Step 4: Documentation & Cleanup (30 min)

1. Update SKILLS_IMPLEMENTATION.md with final state
2. Add API endpoint documentation
3. Clean up test files

---

## 📊 Summary Statistics

- **Total Lines of Code Written:** ~2,000 lines
- **New Files Created:** 4
  - `app/services/skills_service.py` (615 lines)
  - `app/services/discovery_service.py` (550 lines, rewrite)
  - `scripts/migrate_milvus_to_skills.py` (425 lines)
  - `test_skills_quick.py` (150 lines)
- **Files Modified:** 3
  - `app/models/schemas.py` (+70 lines)
  - `app/services/generation_service.py` (imports updated)
  - `app/api/endpoints/generation.py` (pending)
- **Tests Passing:** 4/4
- **Migration Status:** Complete (39 tables migrated)
- **Skills Directory:** 80+ markdown files generated

---

## 🔑 Key Technical Decisions

1. **Skills-first with RAG fallback** - Primary discovery from curated skills, augmented by value index and knowledge base
2. **Filesystem-based** - No database required for skills (just markdown files)
3. **Parallel discovery** - All three methods run simultaneously for speed
4. **Context-aware thresholds** - Different limits based on scenario (cross-schema vs same DB)
5. **Backward compatibility** - Legacy `perform_discovery()` preserved as fallback
6. **Markdown format** - Human-readable, version-control friendly
7. **Weighted scoring** - Skills (10) > Value (8) > Knowledge (5)
8. **Separated data-groups and schemas** - Logical grouping separate from physical storage

---

## 🐛 Known Issues

### Resolved:
- ✅ Unicode emoji encoding in Windows console
- ✅ Wrong import `LLMService` → `LLMServiceBase`
- ✅ Glob pattern not finding `_*-group.md` files
- ✅ Columns not parsing (added markdown table fallback)
- ✅ Table loading by name vs file path

### Open:
- ⚠️ Migration script creates one group per table (should consolidate related tables)
- ⚠️ Keywords extracted are basic (need NLP for better extraction)
- ⚠️ No UI for browsing/editing skills yet

---

## 📝 Important File Locations

```
Core Implementation:
├── app/services/skills_service.py          # Skills loading & search
├── app/services/discovery_service.py       # Three-pronged discovery
├── app/models/schemas.py                   # Data models
├── scripts/migrate_milvus_to_skills.py     # Migration tool
└── skills/data-sources/                    # Generated skills directory

Pending Integration:
├── app/services/generation_service.py      # Lines 482-525 (discovery)
└── app/api/endpoints/generation.py         # Event handler

Testing:
├── test_skills_quick.py                    # Quick integration test
└── tests/ (pending creation)
```

---

**End of Progress Report**
