# Build SQL with AI Agent

Use the AI Assistant panel to generate SQL from natural language, refine SQL, and fix SQL errors.

## Before You Start

- Open a query editor tab.
- Make sure the current data source has an AI agent configured.
- If no AI settings are ready, submission is blocked and a warning is shown.

For agent setup, see [AI Agent Manager Window](ai-agent-manager-window.md).

## Open and Use the AI Assistant Panel

The AI Assistant panel is shown on the right side of the query editor.

In the input box:

- Type your request (example: "Show monthly sales by product category for 2024").
- Press **Enter** to submit.
- Press **Ctrl+Enter** to insert a new line without submitting.
- Or click the **?** submit button.

## What Context You Can Send to the AI Agent

The panel can include three context sources with checkboxes:

- **Query**: sends current SQL from the editor.
- **Error**: sends the latest parse/runtime error.
- **Objects**: sends selected database objects.

Behavior:

- A checkbox is enabled only when that context exists.
- When enabled, it is checked by default.
- You can uncheck any box to exclude that context from your request.

## Select Database Objects for AI Context

Click the **+** button beside the context checkboxes to open **Database Objects Selector**.

In this dialog, you can:

- Filter by **Object Type**: `(All)`, `Table`, `View`, `Function`.
- Filter by **Schema**.
- Search by object name using **Filter**.
- Clear filter with **X**.
- Move objects using:
  - **>** add selected object
  - **>>** add all objects
  - **<** remove selected object
  - **<<** remove all selected objects
- Double-click an item to add/remove quickly.

Object inspection tools in the selector:

- **Open Table Schema** (`F4`) from toolbar or right-click menu.
- **Preview Data** (`F8`) from toolbar or right-click menu.

Click **OK** to apply selected objects to AI context, or **Cancel** to discard changes.

## Insert AI Result into SQL Editor

When SQL is generated, it is inserted into the SQL editor automatically.

You can also interact with chat responses:

- Click an AI answer bubble containing SQL to apply that SQL.
- Double-click an AI answer bubble to insert the full answer text as a SQL comment block.

## Fix SQL Errors with AI

When parse/validation/runtime errors are available, the **Error** context can be sent to AI.

Typical flow:

1. Generate or edit SQL.
2. Parse or run and get an error.
3. Ask AI to fix it (the panel may prefill: `Fix this error.`).
4. Review generated SQL and run again.

## Follow-Up Prompts

The assistant keeps conversation history for the current chat session. You can ask follow-up prompts like:

- "Now add top 10 only."
- "Use left join instead."
- "Group by month and region."

## Tips

- Keep requests specific (metrics, filters, date range, grouping).
- Use **Objects** context to reduce ambiguity.
- Keep **Query** checked when asking for modifications to existing SQL.
- Keep **Error** checked when asking for fixes.

For a full walkthrough of the assistant (chat, context, screenshots, and tasks beyond SQL generation), see [How to Use the AI Assistant](how-to-use-ai-assistant.md).

[Back to Octofy User Manual](user-manual.md)
