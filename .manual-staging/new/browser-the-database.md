# Browse the Database

The database browser lets you explore and search the objects in a connected database. It has two panels: the **Object Explorer** and the **Search Panel**. Selecting an object in either panel opens its columns in the **Column View**.

You can open the browser window from the **Query Editor** with **File > Open object browser**.

## Connecting to a Database

Select a saved connection from the **Data source** drop-down list in the toolbar. You can also use the **File > Connect to ...** menu to switch connections. When a connection requires a file path (for example, an ODBC file-based source), a file picker opens automatically.

For PostgreSQL, MySQL, and Oracle connections, Octofy asks for the user name and password in a log-on dialog before the connection is made.

The status bar at the bottom of the window shows the connected server name and database name for a SQL Server connection; for other connection types it shows the DSN instead.

## Object Explorer

The Object Explorer displays the database objects for the current connection as a tree. The root node is the connection name, followed by the database schemas, and under each schema the **Table**, **View**, and **Function** groups. A database without schemas lists the **Table** and **View** groups directly under the root node.

Selecting a table, view, or function in the tree loads its columns in the Column View. The full name of the selected object is shown in the status bar.

Right-click an object in the tree to open the object context menu:

- **Quick analysis on top 10000 rows** — Runs a quick analysis on the top 10,000 rows of the table.
- **Data analysis** — Runs data analysis on the entire table or view.
- **Data preview** — Previews the data of the table or view.
- **Table Schema** — Shows the schema of the table.
- **Copy object name** — Copies the fully qualified object name to the clipboard.
- **Build SELECT script** — Generates a SELECT script for the table.
- **Refresh** — Reloads the object list.
- **Collapse all** — Collapses all tree nodes.

When a table or view node is selected, **Data analysis**, **Data preview**, and **Copy object name** are available. The column entries of this menu (**Column value frequency** and **Add to the visual editor**) appear only where the tree also lists columns; the Database Browser keeps columns in the Column View, so they are not offered here.

## Search Panel

The Search Panel provides a fast way to locate database objects by name. It is the **Search** tab of the object panel.

Type the text to look for in the **Search for** box, then click the search button (tooltip **Perform searching**) or press **Enter**. Press **Escape** to clear the box. The number of matches is reported next to **Results:** as **No match found**, **One item found**, or **n items found**, and the matching objects are listed in the search result tree.

### Search Types

Use the radio buttons to select what to search:

| Option | Description |
|--------|-------------|
| **Table/View** | Searches table and view names. |
| **Column** | Searches column names across all tables and views. When a match is found, the matching columns are highlighted in the Column View. |
| **AI** | Uses an AI agent to find relevant objects from a natural-language description. The option is shown only when the selected data source has an AI agent. |

An AI search reports its progress as **Searching database objects...** and finishes with **Found n objects.**, **No matching database objects found.**, or **Search failed.**.

### Schema-Scoped Search

Prefix the search text with a schema name and a dot to limit results to that schema:

```
schema_name.search_text
```

### Search Pattern

The pattern indicator next to the search box shows how the text is matched: **(Starts with)**, **(Ends with)**, **(Contains)**, or **(Equals)**. Click the left arrow of the indicator to move toward **Starts with**, or the right arrow to move toward **Equals**. It is hidden while the **AI** search type is selected.

| Pattern | Description |
|---------|-------------|
| **Starts with** | Object name begins with the search text. |
| **Ends with** | Object name ends with the search text. |
| **Contains** | Object name contains the search text anywhere. |
| **Equals** | Object name exactly matches the search text. |

### Search Results

Select a result to load its columns in the Column View. Right-click a result to open its context menu:

- **Data analysis** — Runs data analysis on the entire table or view.
- **Data preview** — Previews the data of the table or view.
- **Table schema** — Shows the schema of the table.
- **Copy object name** — Copies the object name to the clipboard.
- **Column values frequency** — For a column node, shows the value frequency of the column.

## Column View

When you select an object in the Object Explorer or Search Panel, its columns are displayed in the Column View data grid. The name of the selected object is shown above the grid.

The first column of the grid has no header: it shows the ordinal position of the column in the object, with a key symbol appended for primary key columns.

| Column | Description |
|--------|-------------|
| **Column Name** | Name of the column. |
| **Data Type** | Data type, including length or precision where applicable (for example, `varchar(100)`, `nvarchar(MAX)`, `decimal(18, 2)`). |
| **Nullable** | Indicates whether the column accepts null values. |
| **Description** | Extended property description for the column, if available. |

Double-click a column row to open the **Column Values Frequency** window for that column. Frequencies are not available for all data types; for example, binary and text columns are rejected with a message.

### Looking For

Type in the **Looking for** box in the toolbar to highlight matching column names or descriptions in the currently displayed Column View. The first matching row is scrolled into view and selected.

### Column View Context Menu

Right-click a row in the Column View to access:

- **Frequencies** — Opens the column values frequency analysis for the selected column.
- **Copy column name** — Copies the column name to the clipboard.
- **Copy selection** — Copies the selected rows to the clipboard.

## Table Menu

When a table or view is selected, the **Object** menu provides the following actions:

- **Data analysis** — Opens the analysis form for the full object.
- **Data preview** — Opens a preview of the data in the selected table or view.
- **Copy object name** — Copies the fully qualified object name to the clipboard.

## Column Menu

When a column is selected in the Column View, the **Column** menu provides:

- **Value frequencies** — Opens the column values frequency analysis.
- **Copy Column Name** — Copies the quoted column name to the clipboard.

## View Menu

Use the **View** menu to show or hide the **Toolbar** and **Status Bar**.

[Back to Octofy User Manual](user-manual.md)

## Screenshots

![Database object tree](images/Octofy_Object_explorer.png)

![Database object search panel](images/Octofy_Search.png)

![Column view](images/Octofy_Column_view.png)

