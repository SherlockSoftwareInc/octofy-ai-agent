# Planning Mode Chat Flow Summary

`queryMode` values `plan` and `ask` do **not** enter the built-in SQL orchestrator. They are handled by `app/services/discuss_service.py` (`discuss_conversation`). SQL generation starts only when the client later sends `queryMode=generate`. See [AGENT_PROCESS.md](AGENT_PROCESS.md).

Based on the codebase, here's the comprehensive chat flow logic for **Plan Mode**:

## Frontend Flow (App.tsx)

### 1. **Mode Selection**

- User selects "📋 Plan" mode via radio button
- `queryMode` state set to `'plan'`
- Planning-specific banner appears with amber/orange color scheme

### 2. **State Management**

- **Planning Context**: Stores conversation state across turns

  ```typescript
  {
    goal: string,
    selected_tables: string[],
    suggested_tables: object[],
    requirements: object[],
    conversation_history: object[],
    turn_count: number
  }
  ```

- **Planning Summary**: Auto-generated when switching to code generation modes
- **Selected Objects**: User's checkbox selections persist in conversation

### 3. **Message Handling**

```typescript
// User sends query → Backend call with planning_context
result = await api.generateSQLStream(
  query,
  queryMode: 'plan',
  planning_context: planningContext
)

// Response updates planning context
if (result.context_text) {
  planningContext = JSON.parse(result.context_text)
}
```

### 4. **Object Selection UI**

- Displays suggested tables with checkboxes
- **Auto-checked** tables (essential, >90% confidence) pre-selected
- Visual indicators: amber color scheme, "Essential" badges
- Schema preview via Eye icon

### 5. **Auto-Generate Transition**

When switching from Plan → Code Generation modes:

```typescript
// Auto-generates planning summary via backend
const summaryResponse = await generatePlanningSummary(planningContext)

// Adds summary as AI message
// Shows "✨ Auto-generate from planning summary" button
```

---

## Backend Flow (generation_service.py)

### 1. **Intent Analysis** (`planning_conversation`)

```python
# LLM analyzes user message
intent_data = {
  "goal_clear": bool,
  "goal_statement": str,
  "critical_ambiguities": list,
  "ready_for_search": bool,
  "required_questions": list,
  "requirements_extracted": list
}
```

### 2. **Smart Question Strategy**

- **Only asks questions if genuinely ambiguous**
- Avoids interrogation-style interaction
- Assumes reasonable defaults (e.g., "sales" = revenue)

### 3. **Semantic Search** (when ready)

```python
if intent_data["ready_for_search"]:
    # Search database objects
    search_result = search_data_objects(query)
    suggested_objects = result.objects
    
    # Auto-check essential tables (>90% confidence)
    confidence_data = llm_service.chat(confidence_prompt)
    auto_checked_tables = confidence_data["essential_tables"]
```

### 4. **Confidence Scoring**

```python
# LLM determines which tables are ESSENTIAL
confidence_prompt = f"""
Given this user goal: {goal}
And these suggested tables: {table_list}
Which tables are ESSENTIAL (>90% confidence)?
Maximum 3 essential tables.
"""
```

### 5. **Response Generation**

```python
# Conversational, not robotic
response_prompt = f"""
1. Acknowledge their input warmly
2. ONLY ask questions from required_questions
3. If tables found, present for review
4. If auto-checked, mention pre-selection
5. If planning complete, suggest next steps
"""
```

### 6. **Planning Summary Creation**

```python
def generate_planning_summary(planning_context):
    """
    CRITICAL: Focus on WHAT USER WANTS (primary request)
    NOT just list tables
    
    Format:
    ## Primary Request
    [User's analysis goal - MAIN FOCUS]
    
    ## Data Sources
    [Selected tables - minimal]
    
    ## Additional Requirements
    [Filters, dates, etc.]
    """
```

---

## Key Design Principles

### ✅ **Do's**

- Ask questions only when truly necessary
- Auto-check high-confidence tables (≥15 score)
- Present top 20 candidates for user selection
- Generate warm, conversational responses
- Focus planning summary on USER'S GOAL, not tables

### ❌ **Don'ts**

- Don't interrogate users with unnecessary questions
- Don't assume all tables need manual selection
- Don't make planning summary a table list
- Don't lose context between conversation turns

---

## Example Flow

```flow
User: "I want to analyze customer purchase patterns"
  ↓
[Intent Analysis]
  goal_clear: true
  ready_for_search: true
  ↓
[Search Objects]
  Found: Customers, Orders, OrderDetails, Products
  ↓
[Auto-Check Essential]
  ✓ Customers (score: 95)
  ✓ Orders (score: 90)
  ☐ OrderDetails (score: 12)
  ↓
[Present to User]
  "I've pre-selected essential tables. Adjust if needed."
  ↓
[User switches to Generate SQL]
  ↓
[Auto-Generate Summary]
  ## Primary Request
  Analyze customer purchase patterns to identify trends
  
  ## Data Sources
  • Customers
  • Orders
  ↓
[Generate SQL with summary as prompt]
```

---

## State Persistence

- Planning context stored in `activeConversation.planningContext`
- Summary stored in `activeConversation.planningSummary`
- Selected objects persist until user clears or starts new chat
- All state saved to localStorage via `conversationStorage`

---

## Technical Implementation Details

### Frontend Components

- **Mode Toggle**: Radio buttons in footer (App.tsx line ~1073)
- **Planning Banner**: Amber-themed alert when summary ready (App.tsx line ~1088)
- **Object Grid**: Checkbox list with auto-checked indicators (App.tsx line ~746)
- **Planning Summary Card**: Displays final summary with action buttons (App.tsx line ~835)

### Backend Endpoints

- **POST /api/v1/generate-sql**: Main endpoint with `queryMode: "plan"`
- **POST /api/v1/generate-planning-summary**: Creates structured summary

### Key Functions

- `planning_conversation()` - Main planning orchestrator (generation_service.py)
- `search_data_objects()` - Semantic search for database objects
- `generate_planning_summary()` - Creates user-focused summary
- `handleSend()` - Frontend request handler with mode routing

---

This creates a **guided, conversational planning experience** that efficiently narrows down the user's data needs before code generation.
