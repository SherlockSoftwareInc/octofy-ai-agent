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

The left explorer panel, visual editor panel, and error window can be shown or hidden from the **View** menu.

## Menus

### File

| Menu item | Description | Shortcut key |
| --- | --- | --- |
| Connect to... | Drop-down list of saved data sources. Select one to connect. | |
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
| Clear Selection | Clear selection in active editor. | |
| Indent | Indent selected lines. | |
| Outdent | Outdent selected lines. | |
| Uppercase | Convert selected text to uppercase. | |
| Lowercase | Convert selected text to lowercase. | |

### Search

| Menu item | Description | Shortcut key |
| --- | --- | --- |
| Quick Find... | Inline quick search in active editor. | `Ctrl+F` |
| Find... | Open find dialog. | `Ctrl+Alt+F` |
| Find and Replace... | Open find/replace dialog. | `Ctrl+H` |

### Object

| Menu item | Description | Shortcut key |
| --- | --- | --- |
| Data analysis | Run analysis on selected database object. | `F7` |
| Data preview | Preview selected database object data. | `F8` |
| Table Schema | Show schema for selected object. | `F4` |
| Add to the visual editor | Add selected object to visual editor diagram. | `F9` |
| Copy object name | Copy selected object name to clipboard. | |

### Analysis

| Menu item | Description | Shortcut key |
| --- | --- | --- |
| Analysis | Run analysis for current SQL (SELECT statements). | `F5` |
| Parse | Parse SQL and sync to visual editor. | `Ctrl+F5` |
| Preview data | Preview data for current SQL. | `F6` |

### View

| Menu item | Description |
| --- | --- |
| Database object explorer | Show/hide the left object explorer panel. |
| Visual editor window | Show/hide the visual editor panel. |
| Error window | Show/hide SQL error grid panel. |
| Toolbar | Show/hide toolbar. |
| Status bar | Show/hide status bar. |

### Tools

| Menu item | Description |
| --- | --- |
| Options | Open application options dialog. |
| AI Settings | Open AI settings dialog. |
| Edit box font | Change query editor font. |

### Windows

The **Windows** menu lists currently opened query tabs. Selecting an item activates that tab.

### Help

| Menu item | Description | Shortcut key |
| --- | --- | --- |
| Octofy home | Open Octofy home page. | |
| Octofy online help | Open online user manual. | |
| About ... | Show about dialog. | `F1` |

## Toolbar

| Item | Description |
| --- | --- |
| Analysis | Same action as **Analysis > Analysis**. |
| Preview data | Same action as **Analysis > Preview data**. |
| Parse | Same action as **Analysis > Parse**. |
| Data source | Select active database connection. |
| Add connection | Open add-connection dialog. |

## Database Object Explorer Panel

The left panel uses `DBObjectPanel` and provides:

- **Object tree tab** for schema/object navigation.
- **Search tab** for table/view/column search.

Selecting an object updates the current selection state and enables Object menu actions.

## Query Editor Area

- Multiple SQL tabs are supported (closable tabs).
- Each tab hosts one query editor.
- Right-click a tab to open tab context menu:
  - **Alias**
  - **Close**
  - **Save**

## Visual Editor Panel

- Displays the SQL visual diagram.
- Can receive objects from the Object panel (**Add to the visual editor**).
- SQL text and visual diagram are synchronized when parsing and diagram editing occurs.

## Error Window

The error grid displays SQL execution/parse errors with columns such as:

- Line
- Number
- Class
- State
- Message
- Source
- Server
- Procedure

## Status Bar

The status bar contains:

- **Message/status text** (including selected object name and operation messages)
- **Server indicator**
- **Database indicator** (shown for SQL Server connections)

[Back to Windows and Elements](windows-and-elements.md)

## Screenshots

![Query Data Analysis window overview](images/Octofy_main_windows.png)

