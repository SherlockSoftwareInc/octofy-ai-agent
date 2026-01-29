# Re-Visualization Debug Test Plan

## Context
- **Working commit**: ab25516d7ce65d790d473c0e8cb35aa584f83487
- **Issue**: Re-visualization stopped working after refactoring to support R/SAS code types
- **Debug logs added**: Strategic console.log statements at key decision points

## What Changed Between Working and Current

### Code Detection Logic
**Working** (only Python):
```typescript
const lastPythonMessage = [...chatHistory].reverse().find(
  msg => msg.type === 'ai' && 
         msg.queryType === 'python_code' &&
         msg.sqlResult?.sql &&
         msg.executionResult
);
```

**Current** (Python + R + SAS):
```typescript
const lastCodeExecutionMessage = [...chatHistory].reverse().find(
  msg => msg.type === 'ai' && 
         (msg.queryType === 'python_code' || msg.queryType === 'r_code' || msg.queryType === 'sas_code') &&
         msg.sqlResult?.sql &&
         msg.executionResult
);
```

### Rendering Condition
**Working**:
```typescript
{message.queryType === 'python_code' && message.executionResult && message.chartTypeOverride ? (
```

**Current**:
```typescript
{(message.queryType === 'python_code' || message.queryType === 'r_code' || message.queryType === 'sas_code') && message.executionResult && message.chartTypeOverride ? (
```

## Test Scenario

### Step 1: Generate Python Code
1. Open browser console (F12)
2. Type: `"show sales by category in python"`
3. Press Enter
4. **Expected**: Python code generated

### Step 2: Execute Python Code
1. Click "Run" button
2. **Check console for**:
   ```
   ✅ Code execution result added to message: {
     messageId: "msg_xxx",
     queryType: "python_code",
     hasExecutionResult: true,
     hasResults: true
   }
   ```
3. **Expected**: Chart displays successfully

### Step 3: Attempt Re-visualization
1. Type: `"convert to line chart"`
2. **Check console for**:
   ```
   🎨 Chart Intent Detected: {
     query: "convert to line chart",
     chartType: "line",
     isChartOnly: true,
     foundCodeMessage: true/false,     ← Should be TRUE
     codeHasResult: true/false,        ← Should be TRUE
     foundSQLMessage: false,
     sqlHasResult: false,
     shouldRevisualizeCode: true/false, ← Should be TRUE
     shouldRevisualizeSQL: false
   }
   ```
3. **Also check for**:
   ```
   🔍 shouldTriggerRevisualization: YES - explicit chart-only pattern
   ```
4. Press Enter
5. **Expected**: New line chart appears (chartOnly mode)

## Diagnostic Questions

Based on console output, answer:

### Q1: Is executionResult being added to the message?
- Check for: `✅ Code execution result added to message`
- If **NO**: Problem is in `handleExecutionComplete()`
- If **YES**: Continue to Q2

### Q2: Is chart intent detected correctly?
- Check for: `🎨 Chart Intent Detected`
- Check values:
  - `chartType`: Should be "line"
  - `isChartOnly`: Should be `true`
- If **NO**: Problem is in `detectChartIntent()`
- If **YES**: Continue to Q3

### Q3: Is lastCodeExecutionMessage found?
- Check: `foundCodeMessage: true`
- Check: `codeHasResult: true`
- If **NO**: Message doesn't have `executionResult` when we search for it
  - Possible cause: State timing issue
  - Possible cause: localStorage not persisting `executionResult`
- If **YES**: Continue to Q4

### Q4: Does shouldTriggerRevisualization return true?
- Check for: `🔍 shouldTriggerRevisualization: YES`
- If **NO**: Check which path it took (explicit pattern, no previous execution, different data, etc.)
- If **YES**: Continue to Q5

### Q5: Is the re-visualization handler triggered?
- Check: Does `shouldRevisualizeCode` show as `true`?
- If **NO**: Logic error in condition
- If **YES**: Should execute re-visualization

### Q6: Does the new message have chartTypeOverride?
- After submitting "convert to line chart", check the new AI message in React DevTools
- Should have: `chartTypeOverride: "line"`
- If **NO**: Problem in message creation
- If **YES**: Should render in chartOnly mode

## Possible Root Causes

### Hypothesis 1: State Timing Issue
**Symptoms**: `foundCodeMessage: false` or `codeHasResult: false`

**Cause**: `handleExecutionComplete()` updates the message, but `handleSubmit()` runs before the state update completes.

**Test**: Add a small delay before typing "convert to line chart" (wait 1-2 seconds after execution completes)

### Hypothesis 2: localStorage Persistence Issue
**Symptoms**: Works initially, but fails after page refresh

**Cause**: `executionResult` not being saved/loaded from localStorage

**Test**: 
1. Execute Python code
2. Check browser DevTools → Application → Local Storage → Check conversation data
3. Verify `executionResult` exists in the message
4. Refresh page (F5)
5. Check localStorage again - is `executionResult` still there?

### Hypothesis 3: Message Detection Logic Issue
**Symptoms**: `foundCodeMessage: true` but `shouldRevisualizeCode: false`

**Cause**: `shouldTriggerRevisualization()` returning false unexpectedly

**Test**: Check the specific reason logged by `shouldTriggerRevisualization()`

### Hypothesis 4: Rendering Condition Issue
**Symptoms**: Everything logs correctly, but chart doesn't appear

**Cause**: Rendering condition not matching the message

**Test**: Use React DevTools to inspect the message object and verify:
- `queryType === 'python_code'`
- `executionResult` exists
- `chartTypeOverride === 'line'`

## Debug Logs Reference

All logs are prefixed with emojis for easy searching:
- `🎨` = Chart intent detection
- `✅` = Execution result updates
- `🔍` = Re-visualization decision logic

## Next Steps After Testing

1. **Collect console logs** from the test scenario
2. **Take screenshots** of any errors
3. **Check React DevTools** for message structure
4. **Compare results** with diagnostic questions above
5. **Report findings** with specific console output
