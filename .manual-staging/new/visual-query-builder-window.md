# Visual Query Builder Window

This page describes the current `AdvancedQueryAnalysisForm` window layout and controls.

## Menus

### File

| Menu item | Description | Shortcut key |
| --- | --- | --- |
| Connect to ... | Connect to an existing database connection. | - |
| Add new DB Connection | Create a new database connection. | - |
| Manage DB Connections | Open database connection management. | - |
| Manage AI Agents | Open AI agent management. | - |
| New | Create a new query tab. | Ctrl+N |
| Open | Open a SQL file. | Ctrl+O |
| Save | Save current SQL file. | Ctrl+S |
| Save as... | Save current SQL file with a new name. | - |
| Close | Close current query tab. | Ctrl+W |
| Close all | Close all query tabs. | - |
| Recent files | Open a recent SQL file. | - |
| Open object browser | Open the object browser window. | - |
| Exit | Close the window. | - |

### Edit

| Menu item | Description | Shortcut key |
| --- | --- | --- |
| Undo | Undo last text edit. | Ctrl+Z |
| Redo | Redo last undone edit. | Ctrl+Y |
| Cut | Cut selected query text. | Ctrl+X |
| Copy | Copy selected query text. | Ctrl+C |
| Paste | Paste clipboard text. | Ctrl+V |
| Select All | Select all text. | Ctrl+A |
| Select line | Select current line. | - |
| Clear Selection | Clear current selection. | - |
| Indent | Indent selected lines. | - |
| Outdent | Outdent selected lines. | - |
| Uppercase | Convert selection to uppercase. | - |
| Lowercase | Convert selection to lowercase. | - |

### Search

| Menu item | Description | Shortcut key |
| --- | --- | --- |
| Quick Find... | Inline quick search in the editor. | Ctrl+F |
| Find... | Open the find dialog. | Ctrl+Alt+F |
| Find and Replace... | Open the find/replace dialog. | Ctrl+H |

### Object

| Menu item | Description | Shortcut key |
| --- | --- | --- |
| Data analysis | Analyze selected object data. | F7 |
| Data preview | Preview selected object data. | F8 |
| Table Schema | Open the selected object schema. | F4 |
| Add to the visual editor | Add the selected object to the visual editor. | F9 |
| Copy object name | Copy the selected object name. | - |

### Analysis

| Menu item | Description | Shortcut key |
| --- | --- | --- |
| Analysis | Execute the query and run data analysis. | F5 |
| Preview data | Execute the query and open the data preview. | F6 |
| Parse | Parse the SQL statement and sync it to the visual editor. | Ctrl+F5 |
| Use build-in parser | Toggle the built-in parser on or off. | - |

### View

| Menu item | Description |
| --- | --- |
| Database object explorer | Show or hide the left object explorer panel. |
| Visual editor window | Show or hide the visual editor panel. |
| Error window | Show or hide the SQL error grid panel. |
| Toolbar | Show or hide the toolbar. |
| Status bar | Show or hide the status bar. |
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

Shows a dynamic list of open query tabs for quick switching.

### AI Assistant

| Menu item | Description |
| --- | --- |
| Chat Sessions | List the most recent chat sessions of the current data source and switch to one. |
| New session | Start a new chat session and show the AI Assistant panel. |
| Delete current session | Delete the session currently shown. |
| Manage Chat Sessions | Open the chat session manager dialog for the current data source. |
| AI Settings | Open the AI provider settings dialog. |
| Manage Schema Library | Open the schema library of a data source that uses a built-in agent. |

The session commands are enabled only when the current data source has an available AI agent.

### Help

| Menu item | Description | Shortcut key |
| --- | --- | --- |
| Octofy home | Open the Octofy website. | - |
| Octofy online help | Open the online help documentation. | - |
| About ... | Show the about dialog. | F1 |

## Toolbar

| Item | Description |
| --- | --- |
| Analysis | Execute the query and run analysis (`F5`). |
| Preview data | Execute the query and open the data preview (`F6`). |
| Parse | Parse the SQL statement (`Ctrl+F5`). |
| Data source | Select the current database connection. Its label is **Data source:**. |
| Add connection | Add a new database connection. |
| Discuss with AI | Show the AI Assistant panel; while the panel is shown the button reads **Hide discuss panel**. Only visible when the current data source has an available AI agent. |

## Main Panels

- **Database object explorer (left panel)**
  - **Object Explorer** tab: browse database objects. Right-click an object for **Quick analysis on top 10000 rows**, **Data analysis**, **Data preview**, **Table Schema**, **Copy object name**, **Build SELECT script**, **Add to the visual editor**, **Column value frequency**, **Refresh** and **Collapse all**. Double-click a table or view to add it to the visual editor.
  - **Search** tab: search tables, views and columns (**Table/View**, **Column**), or search by topic with **AI** when the data source has an available AI agent.
- **Visual editor window (top panel)**
  - Build SQL `SELECT` statements visually.
  - Shows **The query statement cannot be represented in the visual editor.** for statements it cannot draw, such as those containing `UNION`, `EXCEPT` or `INTERSECT`.
- **Query editor tabs (center panel)**
  - Edit SQL in tabbed query editors.
  - Tab context menu: `Tab alias`, `Close`, `Save`.
- **Error window (bottom panel)**
  - Shows SQL parse/execute errors (line and message). Right-click a row for `Go to error` and `Copy`.
- **AI Assistant panel (right panel, collapsible)**
  - Discuss the current database, discover objects, or have the agent generate SQL. Generated SQL is pushed into the active query editor.

For the step-by-step workflow, see [Visual Query Builder](visual-query-builder.md).

## Status Bar

The status bar displays:

- Current status message (connection progress, the selected object name, or the current file name)
- Current server name (the DSN for an ODBC data source)
- Current database name (SQL Server connections only)

[Back to Windows and Elements](windows-and-elements.md)

## Screenshots

![Visual query builder window screenshot](images/Octofy_Query_data_analysis.png)

![Object explorer](images/Octofy_Object_explorer.png)

![Object search panel](images/Octofy_Search.png)
