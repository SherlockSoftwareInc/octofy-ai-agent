# Visual Query Builder

Use the Visual Query Builder to create SQL query statements and analyze returned data.

The query builder window includes:

- Object tree (database browser)
- Search panel
- Object data preview
- Column value frequency check
- Visual editor for joins and selected columns
- Query edit box for manual SQL editing
- SQL syntax parser

This feature is designed mainly for `SELECT` statements.

## Ways to Generate a Query Statement

You can build a query in four ways:

1. Select objects and columns from the object tree
2. Build relationships in the visual editor
3. Manually type SQL in the query edit box
4. Use the AI agent (if configured)

You can also combine these methods in the same query.

## Method 1: Build from Object Tree and Search

### Add Tables or Views

From **Object explorer**:

- Open the **Object Explorer** tab.
- Find a table or view.
- Double-click it to add it to the visual editor, or right-click and choose **Add to the visual editor**.
- You can also drag and drop it into the visual editor.

From **Search**:

- Open the **Search** tab.
- Enter a keyword, choose **Table/View**, and press Enter or click the search button.
- In the results, right-click the target object and choose **Add to visual editor**.
- You can also drag and drop to the visual editor.

The query builder's **Add to the visual editor** and the search panel's **Add to visual editor** commands are available for tables and views.

### Select Columns

Objects added to the visual editor are drawn as table panels, each listing its columns.

- Click the checkbox in front of a column name to select or unselect the column.
- Or right-click a column and choose **Select** / **Unselect**.
- Or right-click a column and choose **Select all columns** / **Unselect all columns**.
- Right-click the object title area to use **Select all columns** or **Unselect all columns**.

### Alias an Object

- Right-click the object title area.
- Select **Alias**.

The alias you type is validated: an empty alias is rejected as `Invalid alias`, an over-long alias reports `The length of the alias is too long.`, and a name already used by another object in the diagram reports `The alias already in use` or `Duplicated alias`.

## Method 2: Build in the Visual Editor

After adding objects, define joins visually:

- Drag a column from one object to a related column in another object.
- A join box appears between the objects.

To change a join, right-click its join box:

| Join command | Description |
| --- | --- |
| INNER JOIN | Change the join type to an inner join. |
| LEFT OUTER JOIN | Change the join type to a left outer join. |
| RIGHT OUTER JOIN | Change the join type to a right outer join. |
| FULL OUTER JOIN | Change the join type to a full outer join. |
| Remove | Delete the join. |

The join box is checked on the join type currently in effect. Join types that have no menu command, such as `CROSS JOIN`, `CROSS APPLY` and `OUTER APPLY`, are drawn from the parsed SQL statement.

## Method 3: Manually Edit the SQL Statement

Use the query edit box to directly type or adjust SQL.

Common manual edits:

- Add `WHERE` conditions
- Add `GROUP BY` and `ORDER BY`
- Add expressions, functions, or calculated columns

You can drag column names into the query editor, but direct typing is usually faster for complex statements.

## Method 4: Generate SQL with AI Agent (If Set)

If AI agent is configured in your environment, you can use it to generate a query statement.

Recommended flow:

1. Click **Discuss with AI** on the toolbar to show the AI Assistant panel and select the **Agent** mode.
2. Provide the analysis goal (for example: "monthly sales by region").
3. Let AI generate an initial SQL statement; the generated statement is placed in the active query editor.
4. Review and refine the SQL in the query edit box.
5. Use **Parse** and **Preview data** to validate before analysis.

AI-generated SQL should always be reviewed before execution. For the chat panel, context checkboxes, and **Database Objects Selector**, see [How to Use the AI Assistant](how-to-use-ai-assistant.md).

## Validate and Run

### Parse the Statement

- Click **Parse** on the toolbar, or use **Analysis > Parse**.
- Shortcut: **Ctrl+F5**.
- Syntax errors appear in the error window below the query edit box. Right-click an error row and choose **Go to error** to jump to the failing line.
- The status bar reports `Parse executed successfully.` or `Parse executed with error. Please see the details in the error window.`
- The **Use build-in parser** menu item toggles the built-in parser. When it is off, the server-side parser is used; if the current connection cannot use a server-side parser, the error window reports `Server-side parser is unavailable for the current connection. Enable built-in parser or configure a valid data source.`

### Preview Query Data

- Click **Preview data** on the toolbar, or use **Analysis > Preview data**.
- Shortcut: **F6**.

### Perform Data Analysis

- Click **Analysis** on the toolbar, or use **Analysis > Analysis**.
- Shortcut: **F5**.

## Optional Data Exploration Tools

### Preview Object Data

- Right-click an object title area in the visual editor and click **Preview data**.
- Or right-click the object in the object explorer and click **Data preview** (shortcut **F8**) or choose **Quick analysis on top 10000 rows**.

### Check Column Value Frequency

- Select a column in an object panel in the visual editor.
- Right-click and click **Column values frequency**.
- Or right-click the column in the object explorer and click **Column value frequency**.

Both commands open the [Column Values Frequency Window](column-values-frequency-window.md).

Visual query builder is not available in Octofy Express edition.

[Back to Octofy User Manual](user-manual.md)

## Screenshots

![Query builder and query data analysis windows screenshot](images/Octofy_Query_data_analysis.png)

