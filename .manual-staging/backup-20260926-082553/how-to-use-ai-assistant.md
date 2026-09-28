# How to Use the AI Assistant

The **AI Assistant** is a chat-style panel in the query editor. You talk to it in plain language while Octofy sends optional **context** from your session: the SQL you are editing, the latest error message, and any database objects you selected. The assistant uses the **AI agent** assigned to the current data source (see [AI Agent Manager Window](ai-agent-manager-window.md)) and the provider configured under [AI Settings](ai-settings.md).

Use it to draft SQL, refine existing statements, debug failures, and ask for explanations or optimization ideas—not only one-shot query generation.

## Before You Start

- Open a **Visual Query Builder** / query editor tab for a connection that has an AI agent assigned.
- Configure **Tools > AI Settings** so the app can reach your LLM endpoint and model.
- If prerequisites are missing, prompts are blocked and a warning explains what to fix.

## The Chat Panel

The assistant appears on the **right** side of the query editor as a conversation thread (your prompts and the model’s replies).

In the message box at the bottom:

- Type your request (for example: “Show monthly sales by product category for 2024”).
- Press **Enter** to send.
- Press **Ctrl+Enter** to insert a new line without sending.
- Or click the send button.

Earlier messages in the same session stay visible so you can ask **follow-ups** (“now limit to top 10”, “use a left join instead”) without repeating the whole problem.

## Context: Query, Errors, and Objects

Above the input area, **checkboxes** control what Octofy attaches to each request:

| Checkbox | What it sends |
| --- | --- |
| **Query** | The SQL currently in the editor—the statement you are building or editing. |
| **Error** | The latest parse, validation, or runtime error text (when one exists). |
| **Objects** | Metadata for database objects you picked in the **Database Objects Selector** (tables, views, functions). |

Rules:

- A checkbox is **enabled** only when that context is available (for example, **Error** appears after a failed parse or run).
- When enabled, it is **checked by default**; you can clear it if you want a generic answer without that context.

### Including the SQL you are editing

Leave **Query** checked when you want the model to **change**, **extend**, or **review** the statement already in the editor. Clear it when you want a fresh query from a description alone.

### Using error messages

After **Parse** or **Preview data** fails, enable **Error** (when shown) and ask for a fix—for example, the panel may suggest a starter message like “Fix this error.” The assistant sees both the failing SQL (if **Query** is checked) and the error text, which helps correct syntax, missing columns, or invalid expressions.

Always **re-parse** or **preview** after applying suggested SQL.

### Specifying objects with Database Objects Selector

Click the **+** button next to the context row to open **Database Objects Selector**. Choose the tables, views, or functions the assistant should treat as in scope. That reduces guesswork when several similar objects exist or when names alone are ambiguous.

In the dialog you can:

- Filter by **Object Type**: `(All)`, `Table`, `View`, `Function`.
- Filter by **Schema**.
- Search by name with **Filter**; clear with **X**.
- Move items with **>** / **>>** (add) and **<** / **<<** (remove), or **double-click** to toggle.
- Use **Open Table Schema** (**F4**) or **Preview Data** (**F8**) from the toolbar or context menu to inspect objects before adding them.

Click **OK** to apply the selection to **Objects** context, or **Cancel** to discard.

## More Than Generating SQL

The same chat can handle tasks such as:

- **Bug fixes** — incorrect results, wrong joins, or logic mistakes; describe the symptom or paste the error.
- **Optimization** — ask for a more efficient rewrite, better indexes to consider, or simpler equivalent SQL (treat suggestions as advisory until you validate on your data and engine).
- **Explanation** — “What does this query return?” or “Why might this be slow?”
- **Refactoring** — consistent formatting, clearer aliases, breaking a complex statement into steps or comments.

Capabilities depend on your provider and model; **review every answer** before running SQL against production data.

## Apply Replies in the Editor

When the model returns SQL, Octofy can place it in the query editor automatically. You can also:

- **Click** an answer bubble that contains SQL to apply that SQL.
- **Double-click** an answer bubble to insert the **full** reply text as a **SQL comment** block (useful for explanations or notes).

## Add to knowledge base (thumbs up)

When you are satisfied that an assistant reply is **correct** for your question (for example after **Parse** and **Preview data**), you can save that exchange using **Add to knowledge base**—the **thumbs-up** button on the assistant message.

Saving adds your prompt and the approved SQL to the knowledge base for this agent. Those entries are then used in two ways:

1. **Quick query generation** — If you later ask a question that **fully matches** a stored entry, Octofy can return the saved SQL directly, without a full model round-trip.
2. **Few-shot examples** — When there is no exact match, the system can still include relevant saved pairs as **few-shot** context for the model, so new SQL is steered toward the same patterns, naming, and style as queries you have already validated.

Prefer adding only queries you trust; a focused, accurate knowledge base improves both speed and consistency over time.

![Add to knowledge base (thumbs-up) on an assistant reply](images/add_to_knowledgebase.png)

## Tips

- Be specific: metrics, filters, date ranges, grouping, and sort order.
- Use **Objects** when the model might pick the wrong table or schema.
- Keep **Query** checked for edits to the current statement; keep **Error** checked when fixing failures.
- Use short follow-up messages that build on the previous reply.

## Related Topics

- [Build SQL with AI Agent](ai-agent-sql-builder.md)
- [Create Build-in AI Agent](create-build-in-ai-agent.md)
- [Visual Query Builder](visual-query-builder.md#method-4-generate-sql-with-ai-agent-if-set)
- [AI Settings](ai-settings.md)

[Back to Octofy User Manual](user-manual.md)

## Screenshots

![AI Assistant panel in the query editor](images/AI_assistant.png)

![Database Objects Selector for AI context](images/Database_objects_selector.png)
