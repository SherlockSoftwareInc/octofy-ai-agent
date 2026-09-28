# Browse the Database

The database browser lets you explore and search the objects in a connected database. It has two panels: the **Object Explorer** and the **Search Panel**. Selecting an object in either panel opens its columns in the **Column View**.

## Connecting to a Database

Select a saved connection from the data source drop-down list in the toolbar. You can also use the **File > Connect To** menu to switch connections. When a connection requires a file path (for example, an ODBC file-based source), a file picker opens automatically.

The status bar at the bottom of the window shows the connected server name and database name.

## Object Explorer

The Object Explorer displays the database objects for the current connection as a tree, organized by schema and then by object type (Tables, Views, Functions). Selecting a table, view, or function in the tree loads its columns in the Column View.

## Search Panel

The Search Panel provides a fast way to locate database objects by name.

### Search Types

Use the radio buttons to select what to search:

| Option | Description |
|--------|-------------|
| **Table** | Searches table and view names. |
| **Column** | Searches column names across all tables and views. When a match is found, the matching columns are highlighted in the Column View. |
| **AI** | Uses an AI agent to find relevant objects by natural language description (available when an AI-enabled connection is configured). |

### Schema-Scoped Search

Prefix the search text with a schema name and a dot to limit results to that schema:

```
schema_name.search_text
```

### Search Pattern

Click the search pattern indicator to open the Search Options dialog and choose a matching method:

| Pattern | Description |
|---------|-------------|
| **Starts with** | Object name begins with the search text. |
| **Ends with** | Object name ends with the search text. |
| **Contains** | Object name contains the search text anywhere. |
| **Equals** | Object name exactly matches the search text. |

## Column View

When you select an object in the Object Explorer or Search Panel, its columns are displayed in the Column View data grid. The grid shows the following information for each column:

| Column | Description |
|--------|-------------|
| **#** | Sequence number (ordinal position) of the column in the object. |
| **Column Name** | Name of the column. |
| **Data Type** | Data type, including length or precision where applicable (for example, `varchar(100)`, `nvarchar(MAX)`, `decimal(18, 2)`). |
| **Nullable** | Indicates whether the column accepts null values. |
| **Description** | Extended property description for the column, if available. |

Double-click a column row to open the **Column Frequency** analysis for that column.

### Looking For

Type in the **Looking For** box in the toolbar to highlight matching column names or descriptions in the currently displayed Column View. The first matching row is scrolled into view and selected.

### Column View Context Menu

Right-click a row in the Column View to access:

- **Frequency** — Opens the Column Frequency analysis for the selected column.
- **Copy** — Copies the column name to the clipboard.
- **Copy Selection** — Copies the selected rows to the clipboard.

## Table Menu

When a table or view is selected, the **Table** menu provides the following actions:

- **Analysis on Entire Table/View** — Opens the analysis form for the full object.
- **Preview Data** — Opens a preview of the data in the selected table or view.
- **Copy Table/View Name** — Copies the fully qualified object name to the clipboard.

## Column Menu

When a column is selected in the Column View, the **Column** menu provides:

- **Frequencies** — Opens the Column Frequency analysis.
- **Copy Column Name** — Copies the quoted column name to the clipboard.

## View Menu

Use the **View** menu to show or hide the toolbar and status bar.

[Back to Octofy User Manual](user-manual.md)

## Screenshots

![Database object tree](images/Octofy_Object_explorer.png)

![Database object search panel](images/Octofy_Search.png)

![Column view](images/Octofy_Column_view.png)

