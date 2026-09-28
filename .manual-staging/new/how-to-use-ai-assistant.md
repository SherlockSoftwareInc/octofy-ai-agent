# How to Use the AI Assistant

The **AI Assistant** is a chat-style panel that Octofy opens beside your work. You talk to it in plain language while Octofy sends optional **context** from your session: the SQL you are editing, the latest error message, and any database objects you selected. The assistant uses the **AI agent** assigned to the current data source (see [AI Agent Manager Window](ai-agent-manager-window.md)) and the provider configured under [AI Settings](ai-settings.md).

Use it to draft SQL, refine existing statements, debug failures, and ask for explanations or optimization ideas—not only one-shot query generation.

The same chat surface appears in several windows:

- **Visual Query Builder** window — opened with the **Discuss with AI** toolbar button, docked on the right side of the window. This is the assistant that offers the **Discuss**, **Discovery**, and **Agent** modes and keeps saved chat sessions.
- **Data Preview** window — opened with its own **Discuss with AI** toolbar button, docked on the right; it discusses the previewed data (see [Data Preview Window](data-preview-window.md)).
- **Data Analysis** window — opened with the **AI Assistant** toolbar button or **View > AI Assistant** (the button then reads **Hide AI Chat**); there it can change the chart, filter and sort the data, and explain the analysis (see [Data Analysis Window](data-analysis-window.md)).
- **Schema Library** form and the tool function editor — their own assistant panes; see [Schema Library Form](schema-library-form.md) and [Tool Functions](tool-functions.md).

## Before You Start

- Open the window that hosts the assistant. For query work, open a **Visual Query Builder** tab for a connection that has an AI agent assigned.
- Configure **AI Assistant > AI Settings** so the app can reach your LLM endpoint and model.
- **Discuss** needs a configured LLM provider. **Discovery** and **Agent** additionally need an AI agent that is usable for the data source: a built-in agent with LLM settings (or its own endpoint and API key), or a ready Octofy agent (endpoint, API key, and source ID).
- The **Data Preview** and **Data Analysis** windows ask for your consent the first time you open their chat, because the data shown there is sent to your LLM provider. The consent choice is remembered (see **Allowing AI to analyze real data** in [AI Settings](ai-settings.md)). The **Visual Query Builder** window does not ask.
- When the prerequisites are missing, the message box is disabled and its placeholder text states what to fix.

## The Chat Panel

The assistant appears on the **right** side of the window as a conversation thread (your prompts and the model's replies). It belongs to the window rather than to a single query tab, so switching editor tabs does not close it.

In the **Visual Query Builder** window the panel has:

- a **⊕ New Session** button at the top, when the assistant keeps saved chat sessions;
- a row above the message box holding the **mode box** and the context checkboxes (see below);
- the message box at the bottom.

In the message box:

- Type your request (for example: “Show monthly sales by product category for 2024”).
- Press **Enter** to send.
- Press **Shift+Enter** to insert a new line without sending.
- Or click **Send**. While a reply is streaming, **Send** is replaced by **Stop**, which cancels the request; the part already received stays in the conversation.

Replies stream in as they are generated and are rendered as formatted markdown: headings, **bold**, lists, pipe tables, `inline code`, and fenced code blocks with their own copy button. Every reply also has a **Copy** button that copies the reply's raw markdown. The message box keeps the focus after each reply, so you can type the next question without clicking.

Earlier messages in the same session stay visible so you can ask **follow-ups** (“now limit to top 10”, “use a left join instead”) without repeating the whole problem.

## Chat Modes

In the **Visual Query Builder** window the mode box above the message box chooses what the assistant does. Your choice is remembered for the next time you open Octofy, and switching modes keeps the visible conversation.

| Mode | What it does | Use it when |
| --- | --- | --- |
| **Discuss** | Holds a general conversation about the data and the database: what the data contains, which KPIs and metrics make sense, dashboards and reports, or how to accomplish something in Octofy. It receives the previewed data or the database schema, plus the **Query**, **Error**, and **Objects** context. SQL can appear in its answers as an illustration, but this mode does not write to the editor. | You want ideas, explanations, or guidance rather than a finished statement. |
| **Discovery** | Searches your database with the AI agent for objects relevant to your question and shows the candidates as a table before the assistant's summary. A short conversational summary of what was found, why it matters, and what to do next follows. | You do not know which table, view, or function holds the data you need. |
| **Agent** | Generates SQL with the AI agent assigned to the data source and puts the result into the active query editor. It is the only mode that offers the **👍 Add to knowledge base** button, and the only one that shows the “what the agent is doing” progress row. See [Build SQL with AI Agent](ai-agent-sql-builder.md). | You want a runnable statement. |

The other windows run their own mode and have no mode box: the **Data Preview** window discusses the previewed data, the **Data Analysis** window drives the analysis, and the Schema Library form and tool function editor assist their own editors.

### What Discovery shows

Describe the objects you are looking for — by topic ("sales and customers") or by the columns they should contain ("a table with an order date and a customer id").

- The answer starts with a **Candidate Objects** table, above the assistant's summary. Its columns are **#**, **Object**, **Match**, **Type**, and **Matched Columns**.
- **Match** is a percentage relative to the best match in the current result set, so the closest object reads 100% and the others are scaled down; a dash is shown when no score is available.
- **Matched Columns** lists the columns that matched your description.
- The assistant then writes a short summary of what it found and suggests next steps. If a genuinely new request finds nothing, the assistant says that no matching database objects were found.
- Discovery needs an AI agent assigned to the data source and the schema index for it; when the semantic search is unavailable, Octofy still searches the schema by keyword instead.

## Context: Query, Errors, and Objects

Above the input area, **checkboxes** control what Octofy attaches to each request. They are shown in **Discuss** and **Agent** modes (the **Data Preview** window shows none, and the **Data Analysis** window shows its own **Include chart data** and **Include raw data** checkboxes instead):

| Checkbox | What it sends |
| --- | --- |
| **Query** | The SQL currently in the active editor tab—the statement you are building or editing. |
| **Error** | The latest parse, validation, or runtime error text (when one exists). |
| **Objects** | Metadata for database objects you picked in the **Database Objects Selector** (tables, views, functions). |

Rules:

- A checkbox is **enabled** only when that context is available (for example, **Error** appears after a failed parse or run).
- **Error** is checked automatically as soon as an error is available, and **Query** is checked together with it when the editor holds a statement. **Objects** is checked as soon as you have selected objects; **Query** on its own starts enabled but unchecked.
- You can clear any box if you want an answer without that context. Editing the query clears **Query** again, so re-check it when you want the model to change the statement already in the editor.

### Including the SQL you are editing

Leave **Query** checked when you want the model to **change**, **extend**, or **review** the statement already in the editor. Clear it when you want a fresh query from a description alone.

### Using error messages

After **Parse** or **Preview data** fails, **Error** is checked for you, and—in **Agent** mode—the panel pre-fills the message box with “Fix this error.” so you can press **Enter** straight away to ask for a fix. The assistant sees both the failing SQL (when **Query** is checked) and the error text, which helps correct syntax, missing columns, or invalid expressions.

Always **re-parse** or **preview** after applying suggested SQL.

### Specifying objects with Database Objects Selector

Click the **+** button next to the context row (tooltip **Select database objects**) to open **Database Objects Selector**. Choose the tables, views, or functions the assistant should treat as in scope. That reduces guesswork when several similar objects exist or when names alone are ambiguous.

In the dialog you can:

- Filter by **Object Type**: `All`, `Table`, `View`, `Function`.
- Filter by **Schema**.
- Search by name in **Filter**; clear it with **X**.
- Move items with **>** / **>>** (add) and **<** / **<<** (remove), or **double-click** an item in either list to toggle it.
- Use **Open Table Schema** (**F4**) or **Preview Data** (**F8**) from the toolbar or context menu to inspect objects before adding them.

Click **OK** to apply the selection to the **Objects** context, or **Cancel** to discard. Hover the **Objects** checkbox to see the names of the selected objects. A brand-new chat session starts with no objects selected.

## More Than Generating SQL

The same chat can handle tasks such as:

- **Bug fixes** — incorrect results, wrong joins, or logic mistakes; describe the symptom or paste the error.
- **Optimization** — ask for a more efficient rewrite, better indexes to consider, or simpler equivalent SQL (treat suggestions as advisory until you validate on your data and engine).
- **Explanation** — “What does this query return?” or “Why might this be slow?”
- **Refactoring** — consistent formatting, clearer aliases, breaking a complex statement into steps or comments.

Capabilities depend on your provider and model; **review every answer** before running SQL against production data.

## Apply Replies in the Editor

When **Agent** mode answers with SQL, Octofy puts that SQL into the active query editor automatically and re-parses it immediately, so a problem with the new statement comes back to the chat as the **Error** context. You can also work with a reply directly in the chat:

- Generated SQL is rendered as a `sql` code block, which has its own copy button.
- Click **Copy** on a reply to copy its raw markdown—useful for explanations or notes.

**Discuss** mode does not write to the editor; any SQL in its answers is illustrative and stays in the chat.

## Add to knowledge base (thumbs up)

When you are satisfied that an assistant reply is **correct** for your question (for example after **Parse** and **Preview data**), you can save that exchange using **Add to knowledge base**—the **👍** button in the context row. The button appears in **Agent** mode only, and only while the last Agent reply contains generated SQL.

Clicking it opens the **Add to Knowledge Base** dialog, pre-filled with the first question of the session and the generated SQL. There you can:

- edit the **Question:** and the **SQL:**;
- review **Similar existing entries:**, because Octofy checks the knowledge base for a duplicate first and refuses an identical one with “An identical entry already exists in the knowledge base.”;
- use the small AI button (tooltip **Using AI to verify**) to have AI write the question from the SQL;
- check **Build a semantic model from this query** (built-in agents only) to extract a semantic model from the query and open it in the semantic model editor afterwards—see [Semantic Models](semantic-models.md);
- click **Add to KB** to save, or **Cancel** to close without adding.

Saving adds your prompt and the approved SQL to the knowledge base for this agent (the local vector database for a built-in agent, the Octofy agent service for an Octofy agent). Those entries are then used in two ways:

1. **Quick query generation** — If you later ask a question that **fully matches** a stored entry, Octofy can return the saved SQL directly, without a full model round-trip.
2. **Few-shot examples** — When there is no exact match, the system can still include relevant saved pairs as **few-shot** context for the model, so new SQL is steered toward the same patterns, naming, and style as queries you have already validated.

Prefer adding only queries you trust; a focused, accurate knowledge base improves both speed and consistency over time.

See [Add to Knowledge Base](add-to-knowledge-base.md) for the same dialog opened from the Schema Library form.

![Add to knowledge base (thumbs-up) on an assistant reply](images/add_to_knowledgebase.png)

## Chat Sessions

In the **Visual Query Builder** window the assistant keeps **chat sessions**: separate conversations you can switch between, so one topic does not have to share a thread with another. Sessions belong to the data source, so changing the data source shows that data source's own conversations.

- **⊕ New Session** at the top of the panel starts a new, empty session and switches to it; it does nothing while the current session is still empty.
- **AI Assistant > New session** does the same from the menu bar.
- **AI Assistant > Chat Sessions** lists the recent sessions of the current data source (up to 25, most recent first). Click one to switch to it; the session on screen is checked. When there are none yet the list shows `(no sessions)`.
- **AI Assistant > Delete current session** deletes the session on screen and starts a fresh empty one.
- **AI Assistant > Manage Chat Sessions** opens the **Manage Chat Sessions** dialog described below.

The first question you ask in a session becomes its title in these lists (shortened if it is long), so a conversation is recognised by what was asked. There is no rename command. A brand-new session starts from a clean slate: the **Query**, **Error**, and **Objects** checkboxes are cleared and the selected objects are dropped, so nothing from the previous conversation is carried over. Switching to an existing session keeps the current selection.

Sessions are saved on your computer and restored the next time you open Octofy, which also reopens the session you used last. They are stored per data source in the app-level chat folder (`…\Sherlock Software Inc\Octofy\ChatSessions`).

### Manage Chat Sessions dialog

**AI Assistant > Manage Chat Sessions** opens a dialog that lists every session of the data source the chat is bound to (there is no data-source picker in it).

- **Search:** filters the list as you type, matching the topic or the first question (the field's placeholder is `Search topics…`).
- The list has the columns **Topic**, **Created**, **Last used**, and **Messages**. Click a column header to sort; the default order is most recently used first.
- **Delete** permanently deletes the selected session after a confirmation that ends with “This cannot be undone.” (pressing the **Delete** key on the list does the same.) If the deleted session was the one on screen, the assistant switches to the most recently used remaining session (or starts a fresh one).
- **Open**—or double-clicking a row—opens the selected session in the assistant and switches the chat to it.
- **Cancel** closes the dialog without changing the session on screen.
- The line under the list shows `Sessions: n`, or `No saved chat sessions for this data source` / `No matching chat sessions found`.

Deleting a session removes that conversation; knowledge base entries you added from it are kept.

## Progress and Tool Calls

While an **Agent**-mode request runs, a single status row appears inside the assistant's pending reply—in the conversation, at the point the answer will appear—naming what the agent is doing right now, for example:

- `Preparing the request…`, `Understanding the request…`
- `Checking the knowledge base…`, `Checking saved answers…`
- `Analyzing the data needed…`, `Preparing the schema context…`
- `Searching for relevant objects…`
- `Generating SQL… (attempt 1 of 3)`
- `Checking the generated SQL…`, `Reviewing the result…`, `Validating against the database…`
- `Recovering from an error…`, `Preparing the vector database…`
- `Finalizing the answer…`

The row updates in place as the agent moves on, and it disappears when the answer arrives, when you press **Stop**, or when the request fails. It is a live indicator only: it is never saved with the conversation.

**Tool calls.** When the assistant uses one of the data source's [Tool Functions](tool-functions.md) (an MCP server or a sub-agent) to answer a question, a small chip with the tool's name appears above the reply so you can see that a lookup happened. Automatic tool selection needs an endpoint that supports native function calling—an OpenAI-compatible chat endpoint (including Azure OpenAI and Gemini's OpenAI-compatible endpoint) or the OpenAI Responses API.

**Analysis commands.** In the **Data Analysis** window the assistant reports each change it makes the same way, with a chip such as `Chart changed to cat-sum.`, `Filtered Region to: North, South.`, `Filter cleared.`, `Sorted by Category ascending.`, or `Analysis command failed: …` when a command cannot be applied. Failures do not close the chat; you can rephrase the request.

## Tips

- Be specific: metrics, filters, date ranges, grouping, and sort order.
- Use **Objects** when the model might pick the wrong table or schema.
- Keep **Query** checked for edits to the current statement; keep **Error** checked when fixing failures.
- Use short follow-up messages that build on the previous reply.
- Use **Shift+Enter** for a multi-line request; **Enter** sends it.
- Start a new session when you change topic, so each conversation keeps its own context.

## Related Topics

- [Build SQL with AI Agent](ai-agent-sql-builder.md)
- [Create Build-in AI Agent](create-build-in-ai-agent.md)
- [Visual Query Builder](visual-query-builder.md#method-4-generate-sql-with-ai-agent-if-set)
- [Visual Query Builder Window](visual-query-builder-window.md)
- [Data Preview Window](data-preview-window.md)
- [Data Analysis Window](data-analysis-window.md)
- [Add to Knowledge Base](add-to-knowledge-base.md)
- [Tool Functions](tool-functions.md)
- [AI Settings](ai-settings.md)

[Back to Octofy User Manual](user-manual.md)

## Screenshots

![AI Assistant panel docked on the right of the Visual Query Builder window](images/AI_assistant.png)

![Database Objects Selector for AI context](images/Database_objects_selector.png)
