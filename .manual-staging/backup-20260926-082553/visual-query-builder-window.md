# Visual Query Builder Window

This page describes the current `AdvancedQueryAnalysisForm` window layout and controls.

## Menus

### File

| Menu item | Description | Shortcut key |
| --- | --- | --- |
| Connect to... | Connect to an existing database connection. | - |
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
| Select all | Select all text. | Ctrl+A |
| Select line | Select current line. | - |
| Clear selection | Clear current selection. | - |
| Indent | Indent selected lines. | - |
| Outdent | Outdent selected lines. | - |
| Uppercase | Convert selection to uppercase. | - |
| Lowercase | Convert selection to lowercase. | - |

### Search

| Menu item | Description | Shortcut key |
| --- | --- | --- |
| Quick Find... | Inline quick search in editor. | Ctrl+F |
| Find... | Open find dialog. | Ctrl+Alt+F |
| Find and Replace... | Open find/replace dialog. | Ctrl+H |

### Object

| Menu item | Description | Shortcut key |
| --- | --- | --- |
| Data analysis | Analyze selected object data. | F7 |
| Data preview | Preview selected object data. | F8 |
| Table Schema | Open selected object schema. | F4 |
| Add to the visual editor | Add selected object to visual editor. | F9 |
| Copy object name | Copy selected object name. | - |

### Analysis

| Menu item | Description | Shortcut key |
| --- | --- | --- |
| Analysis | Execute query and run data analysis. | F5 |
| Parse | Parse SQL syntax. | Ctrl+F5 |
| Preview data | Execute query and open preview data. | F6 |

### View

| Menu item | Description |
| --- | --- |
| Database object explorer | Show or hide the left object explorer panel. |
| Visual editor window | Show or hide the visual editor panel. |
| Error window | Show or hide SQL error grid panel. |
| Toolbar | Show or hide toolbar. |
| Status bar | Show or hide status bar. |

### Tools

| Menu item | Description |
| --- | --- |
| Options | Open query builder options. |
| AI Settings | Open AI settings. |
| Edit box font | Change query editor font. |

### Windows

Shows a dynamic list of open query tabs for quick switching.

### Help

| Menu item | Description | Shortcut key |
| --- | --- | --- |
| Octofy home | Open Octofy website. | - |
| Octofy online help | Open online help documentation. | - |
| About... | Show about dialog. | F1 |

## Toolbar

| Control | Description |
| --- | --- |
| Analysis | Execute query and run analysis (`F5`). |
| Preview data | Execute query and open preview data (`F6`). |
| Parse | Parse SQL (`Ctrl+F5`). |
| Data source | Select current database connection. |
| Add connection | Add a new database connection. |

## Main Panels

- **Database object explorer (left panel)**
  - Browse database objects.
  - Search for tables, views, and columns.
- **Visual editor window (top panel)**
  - Build SQL `SELECT` statements visually.
- **Query editor tabs (center panel)**
  - Edit SQL in tabbed query editors.
  - Tab context menu: `Tab alias`, `Close`, `Save`.
- **Error window (bottom panel)**
  - Shows SQL parse/execute errors (line and message).

## Status Bar

The status bar displays:

- Current status message
- Current server name
- Current database name

[Back to Windows and Elements](windows-and-elements.md)

## Screenshots

![Visual query builder window screenshot](images/Octofy_Query_data_analysis.png)

![Object explorer](images/Octofy_Object_explorer.png)

![Object search panel](images/Octofy_Search.png)

