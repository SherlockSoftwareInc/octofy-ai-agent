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

- Open **Object explorer** tab.
- Find a table or view.
- Double-click it, or right-click and choose **Add**.
- You can also drag and drop it into the visual editor.

From **Search**:

- Open **Search** tab.
- Enter a keyword and press Enter or click **Search**.
- In results, double-click the target object, or right-click and choose **Add**.
- You can also drag and drop to the visual editor.

### Select Columns

- Double-click a column to select or unselect it.
- Or right-click a column and choose **Select** / **Unselect**.
- Or select a column and press **Space**.
- Right-click object title to use **Select all columns** or **Unselect all columns**.

### Alias an Object

- Right-click the object title area.
- Select **Alias**.

## Method 2: Build in the Visual Editor

After adding objects, define joins visually:

- Drag a column from one object to a related column in another object.
- A join connection icon appears between objects.

Supported join types:

| Join type | Icon |
| --- | --- |
| Inner join | inner_join |
| Left join | left_join |
| Right join | right_join |
| Full join | full_join |

- Right-click the join icon to change join type.
- Right-click the join icon and choose **Remove** to delete the join.

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

1. Provide the analysis goal (for example: "monthly sales by region").
2. Let AI generate an initial SQL statement.
3. Review and refine the SQL in the query edit box.
4. Use **Parse** and **Preview data** to validate before analysis.

AI-generated SQL should always be reviewed before execution. For the chat panel, context checkboxes, and **Database Objects Selector**, see [How to Use the AI Assistant](how-to-use-ai-assistant.md).

## Validate and Run

### Parse the Statement

- Click **Parse** on the toolbar, or use **Analysis > Parse**.
- Shortcut: **Ctrl+F5**.
- Syntax errors appear below the query edit box.

### Preview Query Data

- Click **Preview data** on the toolbar, or use **Analysis > Preview data**.
- Shortcut: **F6**.

### Perform Data Analysis

- Click **Analysis** on the toolbar, or use **Analysis > Analysis**.
- Shortcut: **F5**.

## Optional Data Exploration Tools

### Preview Object Data

- Right-click an object title area.
- Click **Preview data**.

### Check Column Value Frequency

- Select a column in an object.
- Right-click and click **Column values frequency**.

Visual query builder is not available in Octofy Express edition.

[Back to Octofy User Manual](user-manual.md)

## Screenshots

![Query builder and query data analysis windows screenshot](images/Octofy_Query_data_analysis.png)


