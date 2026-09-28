# Data Preview Window

The Data Preview window displays table/view rows or query results in a read-only grid. It is used to quickly inspect data, copy selections, export results, run lightweight follow-up views such as chart view or value-frequency view, and discuss the data with an AI assistant.

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
| Ask AI | Show or hide the AI chat panel on the right side of the window for discussing the previewed data with the configured LLM provider. See *Ask AI (Chat with the Previewed Data)* below. |
| CSV options | Open CSV export options. |

## Ask AI (Chat with the Previewed Data)

The **Ask AI** toolbar button toggles a chat panel on the right side of the window where you can discuss the currently previewed data with your configured LLM provider: ask questions about the values, request summaries or comparisons, or have the assistant explain patterns in the data.

The chat panel is a web-style chat:

- Type a question in the input box at the bottom and press **Enter** to send it (hold **Shift** and press **Enter** to insert a line break). The reply streams in live as it is generated.
- Click **Stop** to cancel an in-progress reply; the partial answer remains visible.
- Replies are rendered as markdown — headings, lists, tables, code blocks, and http(s) images. Each assistant reply has a **Copy** button that copies the raw markdown of that answer.
- The assistant replies in the same language you write in.

To answer accurately, the assistant receives context about the current data:

- the table or view name and the SQL statement that produced the data,
- the columns currently visible in the grid with their data types,
- the row count and a bounded sample of the data converted to a markdown table (up to 100 rows and 40,000 characters; binary columns and columns hidden in the grid are excluded, and long values are truncated).

The conversation is tied to the previewed data: it is reset automatically whenever the underlying data changes (for example, after re-running the query with a different preview size). Toggling the panel open and closed keeps your conversation.

### Requirements

- An LLM provider must be configured. Open **Tools → AI Provider Settings** and set the endpoint, API key, and model. The chat uses the same provider-agnostic request handling as the other AI features, so OpenAI, Azure OpenAI, Anthropic, Google Gemini, DeepSeek, local Ollama, and other compatible endpoints are supported.
- **Allowing AI to analyze real data** must be enabled in **Tools → AI Provider Settings** (Preview group). When you enable it, a consent prompt explains that the data shown in the preview will be sent to your LLM provider — for commercial providers such as OpenAI this means the data leaves your company and is processed by a third party. If the option is off, a privacy banner is shown in the chat panel and sending is disabled.
- The chat panel requires the Microsoft Edge **WebView2** runtime. If the runtime is not installed, the panel is disabled and the reason is shown in its status line.

> **Note:** Streaming chat is not supported for Amazon Bedrock invoke, Google GenerateContent, and Ollama generate endpoints; for those endpoint types the panel reports that streaming is unsupported.

## Context Menu (Data Grid)

| Item | Description |
| --- | --- |
| Value Frequency | Opens a new preview window showing distinct values and counts for the selected column. |
| Hide Current Column | Hides the column that contains the right-clicked cell. |

## Status Bar

| Item | Description |
| --- | --- |
| Rows | Shows the number of rows currently loaded in the grid (for example, `Rows: 1,000`). |
| Error message | If a grid data-conversion/display error occurs, the error message is shown here. |

## Notes

- The data grid is read-only.
- For SQL Server, preview limits can be applied through the **Preview** selector. For non-SQL Server connections, preview-type selection is disabled and the query is executed without that selector.
- If the source is a query that already contains `TOP`, preview-type controls are hidden.
- Binary columns are converted to a hexadecimal text format for display.
- The window remembers size, location, and window state between sessions.
- The **Ask AI** chat sends the previewed data to the configured LLM provider only when **Allowing AI to analyze real data** is enabled in **Tools → AI Provider Settings**. Columns hidden in the grid are also excluded from the chat context.
- **Chart View conditions** – the Chart View toolbar button is only shown when:
  - the result has more than one visible column,
  - the number of visible columns does not exceed the configured max category limit,
  - and every visible column except the first is numeric.
- **Column visibility** – hiding or showing columns via the **Column** menu or context menu also re-evaluates whether the Chart View button should appear, because the charting conditions depend on currently visible columns.

[Back to Windows and Elements](windows-and-elements.md)

## Screenshots

![Data preview window screenshot](images/Octofy_Preview_data.png)
