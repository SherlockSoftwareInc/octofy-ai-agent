# Build SQL with AI Agent

Use the AI Assistant panel to generate SQL from natural language, refine SQL, and fix SQL errors.

## Before You Start

- Open a query editor tab in the **Visual Query Builder** window.
- The window shows the **Discuss with AI** toolbar button only when the selected data source has an AI agent assigned.
- **Agent** mode also needs a usable agent: either a built-in agent whose LLM settings are configured (in **AI Assistant > AI Settings**, or endpoint and API key on the agent itself), or a ready Octofy agent (endpoint, API key, and source ID).
- When the mode's provider or agent is not usable, the message box is disabled and its placeholder text states what to configure — for example, `No LLM provider is configured. Open Tools → AI Provider Settings first.` or `No AI agent is assigned to this data source. Agent mode requires a built-in or Octofy agent.`

For agent setup, see [AI Agent Manager Window](ai-agent-manager-window.md).

## Open and Use the AI Assistant Panel

Click **Discuss with AI** at the right end of the window's toolbar. The panel opens docked on the right side of the **Visual Query Builder** window, beside the editor. The button then reads **Hide discuss panel**; clicking it again (or dragging the splitter grip) collapses the panel.

The panel belongs to the window, not to a single query tab, and its **Query** context follows whichever editor tab is active.

Select **Agent** in the mode box in the row above the message box. The same box also offers **Discuss** and **Discovery**; for what each mode does, see [How to Use the AI Assistant](how-to-use-ai-assistant.md).

In the message box:

- Type your request (example: "Show monthly sales by product category for 2024").
- Press **Enter** to send.
- Press **Shift+Enter** to insert a new line without sending.
- Or click **Send**. While a reply is streaming, **Send** is replaced by **Stop**, which cancels the request.

Agent mode opens with the greeting "Ready to generate SQL. Describe what you need and I will build the query."

## What Context You Can Send to the AI Agent

Three context checkboxes sit beside the mode box (they are shown in **Agent** and **Discuss** modes):

| Checkbox | What it sends |
| --- | --- |
| **Query** | The SQL currently in the active editor tab. |
| **Error** | The latest parse, validation, or runtime error message. |
| **Objects** | The database objects you picked with the **+** button. |

Behavior:

- A checkbox is enabled only when that context exists.
- **Error** is checked automatically as soon as an error is available, and **Query** is checked together with it when the editor holds a statement. **Objects** is checked as soon as you have selected objects; **Query** on its own starts enabled but unchecked.
- You can clear any box to exclude that context from your request. Editing the query clears **Query** again, so re-check it when you want the assistant to change the statement already in the editor.

## Select Database Objects for AI Context

Click the **+** button beside the context checkboxes (tooltip **Select database objects**) to open **Database Objects Selector**.

In this dialog, you can:

- Filter by **Object Type**: `All`, `Table`, `View`, `Function`.
- Filter by **Schema**.
- Search by object name in **Filter**, and clear the filter with **X**.
- Move objects using:
  - **>** add the selected object
  - **>>** add all objects
  - **<** remove the selected object
  - **<<** remove all selected objects
- Double-click an item in either list to add or remove it quickly.

Object inspection tools in the selector:

- **Open Table Schema** (`F4`) from the toolbar or the right-click menu.
- **Preview Data** (`F8`) from the toolbar or the right-click menu.

Click **OK** to apply the selected objects to the AI context, or **Cancel** to discard the changes. The selection becomes the **Objects** context, and hovering the **Objects** checkbox lists the selected object names. A brand-new chat session starts with no objects selected.

## Insert AI Result into SQL Editor

When Agent mode answers with SQL, Octofy puts that SQL into the active query editor automatically and re-parses it immediately, so a parse error can come straight back to the chat as the **Error** context (see below).

The reply itself is also shown in the chat:

- Generated SQL is rendered as a `sql` code block, which has its own copy button.
- Every assistant reply has a **Copy** button that copies the reply's raw markdown.

## Fix SQL Errors with AI

When parse, validation, or runtime errors are available, the **Error** context can be sent to the AI.

Typical flow:

1. Generate or edit SQL.
2. Parse or run it and get an error.
3. The **Error** box is checked for you, **Query** is checked with it, and — in Agent mode — the message box is pre-filled with `Fix this error.` when it was empty.
4. Press **Enter** to send the pre-filled prompt.
5. Review the generated SQL in the editor and parse or run it again.

If the AI request itself fails, the failure text appears inside the assistant's reply (for example, `AI request failed: …`).

## Follow-Up Prompts

The assistant keeps conversation history for the current chat session. You can ask follow-up prompts like:

- "Now add top 10 only."
- "Use left join instead."
- "Group by month and region."

Agent mode treats a terse follow-up as a continuation of the current topic: the earlier turns of the session are sent with the request together with the context the topic has already established, such as a filter agreed a few turns earlier. Switching to **Discuss** or **Discovery** and back does not start the topic over — the mode switch keeps the visible thread, and Agent mode merges those exchanges into its context.

## Tips

- Keep requests specific (metrics, filters, date range, grouping).
- Use **Objects** context to reduce ambiguity.
- Keep **Query** checked when asking for modifications to existing SQL.
- Keep **Error** checked when asking for fixes.
- Use **Shift+Enter** for a multi-line request; **Enter** sends it.

For a full walkthrough of the assistant (modes, chat sessions, context, screenshots, and tasks beyond SQL generation), see [How to Use the AI Assistant](how-to-use-ai-assistant.md).

[Back to Octofy User Manual](user-manual.md)
