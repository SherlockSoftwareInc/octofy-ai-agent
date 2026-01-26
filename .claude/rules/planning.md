# Planning & Thought Process Rules

## 🧠 Pre-Change Analysis

**Rule:** Before proposing any code changes, use a `<thought>` block to:

1. **Summarize the current state** of the code being modified
2. **Identify potential edge cases** relevant to this project:
   - Empty/null query strings
   - Milvus connection failures
   - LLM API timeouts or rate limits
   - SQL validation errors (missing tables/columns)
   - Unicode/Chinese character handling
   - Large result sets from vector search
3. **List existing utilities to reuse** instead of recreating:
   - `get_vector_store()` - singleton Milvus connection
   - `get_llm_service()` - LLM client wrapper
   - `get_db_engine()` - SQLAlchemy engine
   - `validate_sql_with_db()` - SQL parse validation
   - `perform_discovery()` - schema/fewshot retrieval
   - Pydantic models in `app/models/schemas.py`

## 📋 Change Planning Template

```
<thought>
## Current State
- File: [filename]
- Function/Component: [name]
- Current behavior: [what it does now]

## Proposed Change
- Goal: [what we want to achieve]
- Approach: [how we'll implement it]

## Edge Cases to Handle
- [ ] Empty input
- [ ] API/DB connection failure
- [ ] Validation failure recovery
- [ ] Type mismatches

## Reusable Code Check
- [ ] Check existing services in app/services/
- [ ] Check existing schemas in app/models/schemas.py
- [ ] Check frontend utils in frontend/src/utils/
- [ ] Check API client methods in frontend/src/api/client.ts

## Impact Analysis
- Files affected: [list]
- Tests to run: [list]
- Breaking changes: [yes/no + details]
</thought>
```

## 🔄 Multi-File Change Protocol

When changes span multiple files:

1. **Map the dependency chain** - Which files import from which?
2. **Order changes correctly** - Update schemas/types first, then services, then API, then frontend
3. **Identify test coverage** - Which tests validate the changed code?

## ⚡ Quick Checks Before Implementation

| Check | Question |
|-------|----------|
| **Duplication** | Does a similar function already exist? |
| **Schema** | Do I need to update Pydantic models? |
| **Frontend Sync** | Does the API client need updates? |
| **Vector Store** | Will this affect Milvus collections? |
| **Validation** | How will SQL errors be handled? |

## 🎯 SQL Agent-Specific Considerations

Before modifying the generation pipeline:
- **Classification impact** - Will this change how queries are classified?
- **Discovery impact** - Will this affect schema/fewshot retrieval?
- **Retry logic** - Does this interact with the 5-attempt retry loop?
- **Context building** - Are prompts being constructed correctly?
- **Error parsing** - Can validation errors be properly extracted?
