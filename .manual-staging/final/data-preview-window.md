# Data Preview Window

The Data Preview window displays table/view rows or query results in a read-only grid. It is used to quickly inspect data, copy selections, export results, run lightweight follow-up views such as chart view or value-frequency view, and discuss the data with an AI assistant.

The window title is `Preview Data - <table or view name>` when it previews a table or view, and `(Query data)` when it previews a query result.

## Menus

### File

| Menu item | Description |
| --- | --- |
| Save as... | Export the current grid to `.xlsx` or `.csv`. |
| Close | Close the window. |

### Edit

| Menu item | Description |
| --- | --- |
| Copy | Copy the current grid selection to the clipboard. Includes headers when multiple cells are selected. |
| Select All | Select all cells in the grid. |

### Column

| Menu item | Description |
| --- | --- |
| Value Frequency | Opens a new preview window showing distinct values and their counts for the current column. Visible only when the result set has more than two rows. |
| Hide Current Column | Hides the column that contains the current cell. The Chart View button visibility is re-evaluated after hiding. |
| Show All Columns | Restores all previously hidden columns so every column is visible again. The Chart View button visibility is re-evaluated afterward. |
| Select Display Columns | Opens a column picker where you tick the columns to display. The Chart View button visibility is re-evaluated afterward. |

### Tools

| Menu item | Description |
| --- | --- |
| Options | Open CSV export options (delimiter and quote behavior). |

## Toolbar

| Item | Description |
| --- | --- |
| Close | Close the window. |
| Preview | Choose how many rows to load: **Top 1000**, **Top 10000**, or **All**. |
| Save | Export the current grid to `.xlsx` or `.csv`. |
| Chart View | Open a chart window for the currently visible result set. Only visible columns are included. See *Chart View conditions* in **Notes** below. |
| Discuss with AI | Show or hide the AI chat panel on the right side of the window for discussing the previewed data with the configured LLM provider. See *Discuss with AI (Chat with the Previewed Data)* below. |
| csv options | Open CSV export options. |

## Discuss with AI (Chat with the Previewed Data)

The **Discuss with AI** toolbar button toggles a chat panel on the right side of the window where you can discuss the currently previewed data with your configured LLM provider: ask questions about the values, request summaries or comparisons, or have the assistant explain patterns in the data.

The chat panel is a web-style chat:

- Type a question in the input box at the bottom and press **Enter** to send it (hold **Shift** and press **Enter** to insert a line break). The reply streams in live as it is generated.
- Click **Stop** to cancel an in-progress reply; the partial answer remains visible.
- Replies are rendered as markdown — headings, lists, tables, code blocks, and http(s) images. Each assistant reply has a **Copy** button that copies the raw markdown of that answer, and a code block has its own copy button.
- The assistant replies in the same language you write in.
- The panel has no mode picker in this window: the chat is bound to the previewed data set.

To answer accurately, the assistant receives context about the current data:

- the table or view name and the SQL statement that produced the data,
- the columns currently visible in the grid with their data types,
- the row count and a bounded sample of the data converted to a markdown table (up to 100 rows and 40,000 characters; at most 30 columns; binary columns and columns hidden in the grid are excluded, and cell values longer than 120 characters are truncated).

The conversation is tied to the previewed data: it is reset automatically whenever the underlying data changes (for example, after re-running the query with a different preview size, or after hiding a column). Toggling the panel open and closed keeps your conversation.

### Requirements

- An LLM provider must be configured. Open **AI Assistant → AI Settings** (the dialog is titled **AI Provider Settings**) and set the endpoint, API key, and model. The chat uses the same provider-agnostic request handling as the other AI features, so OpenAI, Azure OpenAI, Anthropic, Google Gemini, DeepSeek, local Ollama, and other compatible endpoints are supported.
- **Allowing AI to analyze real data** must be enabled, in the **AI Data Analysis** group of the AI provider settings dialog. When it is off, opening the chat shows a consent prompt that explains that the data shown in the preview will be sent to your LLM provider — for commercial providers such as OpenAI this means the data leaves your company and is processed by a third party. The chat opens only after you agree, and your answer is saved to the setting.
- If no LLM provider is configured, the window reports `No LLM provider is configured. Open Tools → AI Provider Settings first.` and does not open the panel.
- The chat panel requires the Microsoft Edge **WebView2** runtime. If the runtime is not installed, the panel is disabled and the reason is shown in its status line.

> **Note:** Streaming chat is not supported for Amazon Bedrock invoke, Google GenerateContent, and Ollama generate endpoints; for those endpoint types the panel reports that streaming is unsupported (`Streaming chat is not supported for this endpoint type.`).

## Context Menu (Data Grid)

| Item | Description |
| --- | --- |
| Value Frequency | Opens a new preview window showing distinct values and counts for the selected column. |
| Hide Current Column | Hides the column that contains the right-clicked cell. |
| Select Display Columns | Opens a column picker where you tick the columns to display. |

## Status Bar

| Item | Description |
| --- | --- |
| Rows | Shows the number of rows currently loaded in the grid (for example, `Rows: 1,000`). |
| Error message | If a grid data-conversion/display error occurs, the error message is shown here. |

Above the grid, the **Results:** label marks the result area.

## Notes

- The data grid is read-only.
- The **Preview** selector is applied by adding the row-limiting clause of the current DBMS to the query (for example `TOP`, `LIMIT`, `FETCH FIRST` or `ROWNUM`).
- If the source is a query that already limits rows, the preview-type controls are hidden and the query runs as written. They are hidden as well for a multi-statement batch that cannot be turned into a single limited statement.
- When the window is opened with an already prepared result set (for example the value-frequency grid), the preview-type controls are hidden.
- Binary columns are converted to a hexadecimal text format for display.
- The window remembers size, location, and window state between sessions.
- The **Discuss with AI** chat sends the previewed data to the configured LLM provider only after the AI data-analysis consent has been given. Columns hidden in the grid are also excluded from the chat context.
- **Chart View conditions** – the Chart View toolbar button is only shown when:
  - the result has more than one visible column,
  - the number of visible columns does not exceed the configured max category limit,
  - and at least one visible column is numeric.
- **Column visibility** – hiding or showing columns via the **Column** menu or context menu also re-evaluates whether the Chart View button should appear, because the charting conditions depend on currently visible columns.

[Back to Windows and Elements](windows-and-elements.md)

## Screenshots

![Data preview window screenshot](images/Octofy_Preview_data.png)
