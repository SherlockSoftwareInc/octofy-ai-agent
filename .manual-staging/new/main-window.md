# Query Data Analysis Window

This page describes the UI components of the Query Data Analysis window (`AdvancedQueryAnalysisForm`).

## Window Layout

The window contains these main areas:

- **Menu bar** (top)
- **Toolbar** (below menu bar)
- **Database object explorer panel** (left)
- **Query editor tabs** (main area)
- **Visual editor panel** (middle/lower area, collapsible)
- **Error window** (bottom area, collapsible)
- **Status bar** (bottom)
- **AI Assistant panel** (right side, collapsible)

The left explorer panel, the visual editor panel, the error window, the toolbar and the status bar can be shown or hidden from the **View** menu. The AI Assistant panel is toggled by the **Discuss with AI** toolbar button, by the panel splitter grip, or by a session command in the **AI Assistant** menu.

## Menus

### File

| Menu item | Description | Shortcut key |
| --- | --- | --- |
| Connect to ... | Drop-down list of saved data sources. Select one to connect. | |
| Add new DB Connection | Open the add-connection dialog. | |
| Manage DB Connections | Open the connection management window. | |
| Manage AI Agents | Open AI agent management. | |
| New | Create a new query tab. | `Ctrl+N` |
| Open | Open a saved SQL file into a tab. | `Ctrl+O` |
| Save | Save current query tab. | `Ctrl+S` |
| Save as... | Save current query tab with a new file name. | |
| Close | Close current query tab. | `Ctrl+W` |
| Close all | Close all query tabs. | |
| Recent files | Open a recently used SQL file. | |
| Open object browser | Open object browser dialog. | |
| Exit | Close the Query Data Analysis window. | |

### Edit

| Menu item | Description | Shortcut key |
| --- | --- | --- |
| Undo | Undo in the active query editor. | `Ctrl+Z` |
| Redo | Redo in the active query editor. | `Ctrl+Y` |
| Cut | Cut selected text. | `Ctrl+X` |
| Copy | Copy selected text. | `Ctrl+C` |
| Paste | Paste from clipboard. | `Ctrl+V` |
| Select All | Select all text. | `Ctrl+A` |
| Select line | Select current line. | |
| Clear Selection | Clear selection in the active editor. | |
| Indent | Indent selected lines. | |
| Outdent | Outdent selected lines. | |
| Uppercase | Convert selected text to uppercase. | |
| Lowercase | Convert selected text to lowercase. | |

### Search

| Menu item | Description | Shortcut key |
| --- | --- | --- |
| Quick Find... | Inline quick search in the active editor. | `Ctrl+F` |
| Find... | Open the find dialog. | `Ctrl+Alt+F` |
| Find and Replace... | Open the find/replace dialog. | `Ctrl+H` |

### Object

| Menu item | Description | Shortcut key |
| --- | --- | --- |
| Data analysis | Run analysis on the selected database object. | `F7` |
| Data preview | Preview the selected database object data. | `F8` |
| Table Schema | Show schema for the selected object. | `F4` |
| Add to the visual editor | Add the selected object to the visual editor diagram. | `F9` |
| Copy object name | Copy the selected object name to the clipboard. | |

### Analysis

| Menu item | Description | Shortcut key |
| --- | --- | --- |
| Analysis | Run analysis for the current SQL (SELECT statements). | `F5` |
| Preview data | Preview data for the current SQL. | `F6` |
| Parse | Parse SQL and sync it to the visual editor. | `Ctrl+F5` |
| Use build-in parser | Toggle the built-in parser on or off for parsing the current statement. | |

### View

| Menu item | Description |
| --- | --- |
| Database object explorer | Show/hide the left object explorer panel. |
| Visual editor window | Show/hide the visual editor panel. |
| Error window | Show/hide the SQL error grid panel. |
| Toolbar | Show/hide the toolbar. |
| Status bar | Show/hide the status bar. |
| Zoom In | Make the query editor text larger. |
| Zoom Out | Make the query editor text smaller. |
| Zoom 100% | Reset the query editor zoom. |
| Collapse All | Collapse all visual editor objects. |
| Expand All | Expand all visual editor objects. |
| Dark Mode | Switch the window to the dark theme. |

### Tools

| Menu item | Description |
| --- | --- |
| Options | Open the application options dialog. |
| Edit box font | Change the query editor font. |

### Windows

The **Windows** menu lists the currently opened query tabs. Selecting an item activates that tab.

### AI Assistant

The **AI Assistant** menu manages the chat sessions of the current data source and the AI configuration. Its session commands are enabled only when the selected data source has an available AI agent.

| Menu item | Description |
| --- | --- |
| Chat Sessions | List the most recent chat sessions of the current data source. The active session is checked; select one to switch to it. Shows a disabled `(no sessions)` item when none exist. |
| New session | Start a new chat session and show the AI Assistant panel. |
| Delete current session | Delete the session currently shown and switch to a remaining or fresh session. |
| Manage Chat Sessions | Open the chat session manager dialog for the current data source. |
| AI Settings | Open the AI provider settings dialog. |
| Manage Schema Library | Open the schema library of a data source that uses a built-in agent. |

### Help

| Menu item | Description | Shortcut key |
| --- | --- | --- |
| Octofy home | Open the Octofy home page. | |
| Octofy online help | Open the online user manual. | |
| About ... | Show the about dialog. | `F1` |

## Toolbar

| Item | Description |
| --- | --- |
| Analysis | Same action as **Analysis > Analysis**. |
| Preview data | Same action as **Analysis > Preview data**. |
| Parse | Same action as **Analysis > Parse**. |
| Data source | Select the active database connection. Its label is **Data source:**. |
| Add connection | Open the add-connection dialog. |
| Discuss with AI | Show the AI Assistant panel. While the panel is shown the button reads **Hide discuss panel**. The button is visible only when the current data source has an available AI agent. |

## Database Object Explorer Panel

The left panel uses `DBObjectPanel` and provides two tabs:

- **Object Explorer** for schema/object navigation.
- **Search** for table, view and column search, and for AI object search.

Selecting an object updates the current selection state and enables the **Object** menu actions.

### Object Explorer tab

Right-click a node to open the tree context menu:

| Menu item | Description |
| --- | --- |
| Quick analysis on top 10000 rows | Run a quick analysis on the top 10,000 rows of the table. |
| Data analysis | Run data analysis on the entire table. |
| Data preview | Preview the data of the table. |
| Table Schema | Show the schema of the table. |
| Copy object name | Copy the name of the object. |
| Build SELECT script | Generate a `SELECT` script for the table and copy it to the clipboard. |
| Add to the visual editor | Add the table to the visual editor. Enabled for tables and views only. |
| Column value frequency | Show the value frequency of the column. Shown for columns only. |
| Refresh | Refresh the object list. |
| Collapse all | Collapse all tree nodes. |

Double-clicking a table or view node adds it to the visual editor.

### Search tab

The search panel contains a search box with a search button, the label **Search for what kind of objects:** with the options **Table/View**, **Column** and **AI**, and a **Results:** counter. Press **Enter** to search and **Esc** to clear the search box. The **AI** option is shown only when the selected data source has an available AI agent.

Right-click a result to open the results context menu:

| Menu item | Description |
| --- | --- |
| Data analysis | Run data analysis on the entire table. |
| Data preview | Preview the data of the table. |
| Table schema | Show the schema of the table. |
| Copy object name | Copy the name of the object. |
| Add to visual editor | Add the table to the visual editor. |
| Column values frequency | Show the value frequency of the column. |

## Query Editor Area

- Multiple SQL tabs are supported (closable tabs).
- Each tab hosts one query editor.
- Right-click a tab to open the tab context menu:
  - **Tab alias** (prompts `Please enter alias:`)
  - **Close**
  - **Save**

## Visual Editor Panel

- Displays the SQL visual diagram.
- Can receive objects from the object panel (**Add to the visual editor**) or by double-clicking an object in the **Object Explorer** tab.
- SQL text and visual diagram are synchronized when parsing and diagram editing occurs.
- When the statement cannot be represented in the diagram (for example a statement containing `UNION`, `EXCEPT` or `INTERSECT`), the panel shows **The query statement cannot be represented in the visual editor.**

## Error Window

The error grid displays SQL execution/parse errors with these columns:

- Line
- Number
- Class
- State
- Message
- Source
- Server
- Procedure

Right-click an error row for **Go to error** (jump to the failing line in the active editor) and **Copy**.

## AI Assistant Panel

The right-hand panel hosts the AI chat control. Its content depends on the selected mode.

- **Mode picker**: **Discuss**, **Discovery** and **Agent**.
- **Discuss** is a general conversation about the current database. Its context checkboxes are **Query**, **Error** and **Objects**; the **+** button opens the database objects selector and the 👍 button adds the answer to the knowledge base.
- **Discovery** finds tables, views and objects by topic and shows the candidate objects in a grid.
- **Agent** generates SQL from a natural-language request. Generated SQL is pushed into the active query editor.
- The input box placeholder reflects the mode, for example `Ask the AI agent to generate SQL…` in Agent mode and `Ask about this data… (Enter to send, Shift+Enter for newline)` in Discuss mode.
- Answers stream in as they are generated; click **Stop** to cancel a reply. Replies are rendered as markdown (including tables and http(s) images) and each reply has a **Copy** button that copies its raw markdown.
- The **⊕ New Session** button at the top of the panel starts a new chat session for the current data source.

Requirements:

- An LLM provider must be configured in the AI provider settings dialog. The **Discuss** mode needs the provider only.
- **Discovery** and **Agent** also need an AI agent assigned to the current data source (a built-in or Octofy agent). When none is assigned, the mode reports that the data source has no AI agent and the panel's input is disabled.
- The chat panel requires the Microsoft Edge **WebView2** runtime.

## Status Bar

The status bar contains:

- **Message/status text** (connection progress such as `Connect to ...`, the selected table/view name, or the current file name)
- **Server indicator** (the server name, or the DSN for an ODBC data source)
- **Database indicator** (shown for SQL Server connections only)

[Back to Windows and Elements](windows-and-elements.md)

## Screenshots

![Query Data Analysis window overview](images/Octofy_main_windows.png)
