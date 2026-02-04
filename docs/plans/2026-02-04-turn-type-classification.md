# Turn-Type Classification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement intelligent turn-type classification in planning mode to distinguish between refinements, corrections, pivots, and confirmations—preventing context pollution and improving conversational flow.

**Architecture:** Hybrid classification approach using fast pattern matching (10ms) with LLM fallback (1s) for ambiguous cases. Session-only rejection tracking prevents re-suggesting tables users deselected. Pivot detection with user confirmation prevents accidental context loss.

**Tech Stack:** Python 3.8+, FastAPI, Pydantic, pytest, OpenAI GPT-4o

---

## Phase 1: Core Turn-Type Classification

### Task 1: Add Turn-Type Data Structures

**Goal:** Add TurnType enum and IntentData Pydantic model to support turn-type classification in planning mode.

**Context:** This is the foundation for the turn-type classification system. The existing codebase has planning_conversation() in generation_service.py that uses basic intent detection. We're enhancing it with explicit turn types.

**Files:**
- Modify: `app/models/schemas.py` (add after line 70)
- Test: `tests/test_turn_type_schemas.py` (create new)

**Implementation:**

Add to `app/models/schemas.py` after line 70:

```python
from enum import Enum

class TurnType(str, Enum):
    """Classification of user message intent relative to planning context"""
    REFINEMENT = "refinement"      # Adding detail to existing goal
    CORRECTION = "correction"      # Changing a specific detail
    PIVOT = "pivot"                # Switching topics
    CONFIRMATION = "confirmation"  # Agreeing to proceed
    CLARIFICATION = "clarification" # Answering system questions


class IntentData(BaseModel):
    """Enhanced intent analysis with turn-type classification"""
    # Existing fields (preserve backward compatibility)
    goal_clear: bool
    goal_statement: str
    critical_ambiguities: List[str] = []
    ready_for_search: bool
    required_questions: List[Dict[str, Any]] = []
    requirements_extracted: List[Dict[str, Any]] = []
    
    # NEW: Turn-type classification fields
    turn_type: TurnType
    topic_similarity: float = Field(ge=0.0, le=1.0, description="Similarity to previous goal (0-1)")
    confidence_in_classification: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""
    changed_requirements: List[str] = []
    new_requirements: List[str] = []
    removed_requirements: List[str] = []
    needs_pivot_confirmation: bool = False
```

Create `tests/test_turn_type_schemas.py` with comprehensive tests covering:
- Enum values
- IntentData model validation
- Field constraints (0.0-1.0 range)
- Backward compatibility

**Test Command:** `pytest tests/test_turn_type_schemas.py -v`

**Expected:** 5 tests pass

**Commit:** `git commit -m "feat: add TurnType enum and IntentData model for planning classification"`

---

### Task 2: Add Pattern-Based Turn-Type Detection

**Goal:** Implement fast pattern-based turn-type detection using regex for common phrases (confirmation, correction, pivot, refinement).

**Context:** This is the first stage of hybrid classification. Most turns (70%) should be detected via patterns without calling LLM. Function goes in generation_service.py before planning_conversation().

**Files:**
- Modify: `app/services/generation_service.py` (add before line 415, before `planning_conversation()`)
- Test: `tests/test_turn_type_detection.py` (create new)

**Implementation:**

Add function `_detect_turn_type_fast()` with:
- Confirmation patterns: "yes", "okay", "go ahead"
- Correction patterns: "actually", "I meant", "change to"
- Pivot patterns: "forget", "switch to" + low keyword overlap
- Refinement patterns: "also", "additionally", "filter by"
- Return None if confidence < 0.8 (triggers LLM fallback)

Create comprehensive tests covering:
- All pattern types
- Edge cases (no match, ambiguous)
- Keyword overlap calculation

**Test Command:** `pytest tests/test_turn_type_detection.py -v`

**Expected:** 8 tests pass

**Commit:** `git commit -m "feat: add fast pattern-based turn-type detection with hybrid approach"`

---

### Task 3: Add Topic Similarity Helper

**Goal:** Implement Jaccard similarity calculation to measure topic overlap between current query and previous goal.

**Context:** Used by pivot detection to determine if user is switching topics. Fast keyword-based approach (no embeddings needed).

**Files:**
- Modify: `app/services/generation_service.py` (add after `_detect_turn_type_fast()`)
- Test: `tests/test_topic_similarity.py` (create new)

**Implementation:**

Add function `_compute_topic_similarity()` using:
- Extract keywords (4+ chars) from both strings
- Calculate Jaccard index: intersection / union
- Return float 0.0-1.0

Create tests covering:
- High similarity (shared keywords)
- Low similarity (different topics)
- Edge cases (empty strings)
- Case insensitivity

**Test Command:** `pytest tests/test_topic_similarity.py -v`

**Expected:** 8 tests pass

**Commit:** `git commit -m "feat: add topic similarity calculation using Jaccard index"`

---

## Phase 2: LLM Fallback & Integration

### Task 4: Add LLM-Based Turn-Type Classification

**Goal:** Implement LLM fallback for ambiguous cases when pattern matching is inconclusive (confidence < 0.8).

**Context:** Second stage of hybrid classification. Uses OpenAI to classify turn type when patterns don't match clearly. Includes error handling and fallback to "refinement".

**Files:**
- Modify: `app/services/generation_service.py` (add after `_compute_topic_similarity()`)
- Test: `tests/test_turn_type_llm.py` (create new with mocks)

**Implementation:**

Add function `_classify_turn_type_llm()` that:
- Builds detailed prompt with conversation history
- Calls llm_service.chat() with temperature=0.3
- Cleans markdown code blocks from response
- Parses JSON with validation
- Falls back to refinement on error

Create mocked tests covering:
- Each turn type classification
- Markdown response cleaning
- Error handling
- Default value population

**Test Command:** `pytest tests/test_turn_type_llm.py -v`

**Expected:** 7 tests pass

**Commit:** `git commit -m "feat: add LLM-based turn-type classification fallback with error handling"`

---

### Task 5: Add Planning Context Serialization Helper

**Goal:** Create helper function to serialize planning context to JSON, handling Python sets that aren't JSON-serializable.

**Context:** Planning context now has set fields (rejected_tables, confirmed_tables) that need conversion to lists for JSON. Helper ensures consistent serialization.

**Files:**
- Modify: `app/services/generation_service.py` (add before `planning_conversation()`)
- Test: `tests/test_planning_context_serialization.py` (create new)

**Implementation:**

Add function `_serialize_planning_context()` that:
- Copies context dict
- Converts set fields to lists: rejected_tables, confirmed_tables, last_auto_checked
- Returns json.dumps()

Create tests covering:
- Set conversion
- Empty sets
- Missing fields
- Nested data preservation

**Test Command:** `pytest tests/test_planning_context_serialization.py -v`

**Expected:** 5 tests pass

**Commit:** `git commit -m "feat: add planning context serialization helper for set handling"`

---

### Task 6: Integrate Turn-Type Classification into Planning Conversation (Part 1: Context Init)

**Goal:** Update planning_conversation() initialization to include new tracking fields (goal_history, rejected_tables, confirmed_tables, adjustments, last_auto_checked).

**Context:** Modifying existing function in generation_service.py lines 450-458. Need backward compatibility for existing contexts that don't have these fields.

**Files:**
- Modify: `app/services/generation_service.py` (replace lines 450-458 in `planning_conversation()`)
- Test: Add to `tests/test_generation_service_discovery.py`

**Implementation:**

Replace initialization section with:
- New context: Initialize all tracking fields as sets/lists
- Existing context: Add missing fields with setdefault()
- Convert list→set for rejected_tables, confirmed_tables, last_auto_checked (JSON roundtrip handling)

Add 2 tests to test_generation_service_discovery.py:
- New context has all fields
- Old context gets fields added

**Test Command:** `pytest tests/test_generation_service_discovery.py::test_planning_context_initialization_with_tracking_fields -v`

**Expected:** New tests pass, existing tests still pass

**Commit:** `git commit -m "feat: add intent evolution tracking fields to planning context"`

---

### Task 7: Integrate Turn-Type Classification into Planning Conversation (Part 2: Classification Logic)

**Goal:** Replace existing intent analysis in planning_conversation() with hybrid turn-type classification and pivot detection logic.

**Context:** This is the main integration point. Replace lines 460-522 in planning_conversation() with new flow: fast pattern → LLM fallback → pivot handling → intent analysis.

**Files:**
- Modify: `app/services/generation_service.py` (replace lines 460-522)
- Test: `tests/test_planning_turn_classification.py` (create new with mocks)

**Implementation:**

Replace intent section with:
1. Call _detect_turn_type_fast()
2. If None or low confidence → call _classify_turn_type_llm()
3. Handle pivot: ask confirmation, store pending_pivot
4. Handle pending pivot confirmation
5. Update goal_history for refinement/correction
6. Enhanced intent prompt with turn_type context

Create mocked integration tests covering:
- Pattern matching used (no LLM)
- LLM fallback when ambiguous
- Pivot triggers confirmation
- User confirms pivot (context cleared)
- Correction updates goal history

**Test Command:** `pytest tests/test_planning_turn_classification.py -v`

**Expected:** 6 tests pass

**Commit:** `git commit -m "feat: integrate turn-type classification into planning conversation flow"`

---

### Task 8: Update Return Statements to Use Serialization Helper

**Goal:** Replace all json.dumps(planning_context) calls in planning_conversation() with _serialize_planning_context() helper.

**Context:** Final cleanup to ensure sets are always properly serialized. Update return statements around lines 608-623.

**Files:**
- Modify: `app/services/generation_service.py` (lines 608-623)
- Test: Existing tests should pass

**Implementation:**

Find and replace in planning_conversation():
- Line ~608: `context_text=_serialize_planning_context(planning_context)`
- Line ~620 (error case): `context_text=_serialize_planning_context(planning_context) if planning_context else "{}"`

**Test Command:** `pytest tests/test_generation_service_discovery.py tests/test_planning_context_serialization.py -v`

**Expected:** All existing tests pass

**Commit:** `git commit -m "refactor: use serialization helper for planning context JSON conversion"`

---

## Testing Summary

**Total Tests:** 43 tests across 8 tasks
- Task 1: 5 tests (schemas)
- Task 2: 8 tests (pattern detection)
- Task 3: 8 tests (topic similarity)
- Task 4: 7 tests (LLM classification)
- Task 5: 5 tests (serialization)
- Task 6: 2 tests (context init)
- Task 7: 6 tests (integration)
- Task 8: 2 tests (validation)

**Run Full Suite:** `pytest tests/test_turn_type*.py tests/test_topic_similarity.py tests/test_planning*.py -v`

**Expected:** 100% pass rate, no regressions in existing tests
