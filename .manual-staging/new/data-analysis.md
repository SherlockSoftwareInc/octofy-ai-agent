# Data Analysis

Use the Data Analysis window to summarize table data, visualize trends, and inspect matching raw rows.

## Analysis Types

Select an analysis type from the toolbar or the **Analysis** menu. The type names below are the names shown in the window.

### Category count

Groups rows by one category column and returns row counts.

### Category sum

Groups rows by one category column and returns the sum of a numeric column.

### Category percentile values

Groups rows by one category column and returns percentile values of a numeric column, drawn as a box plot. The percentile values are configured in **Tools > Percentils**.

### Category distribution count

Groups rows by category and distribution columns and returns counts.

### Category distribution count %

Groups rows by category and distribution columns and returns percentage values (100% stacked result).

### Category distribution sum

Groups rows by category and distribution columns and returns summed values.

### Category distribution sum %

Groups rows by category and distribution columns and returns percentage values based on sums.

### Count scatter

Builds bubbles from X-axis and Y-axis numeric columns. Bubble size is count.

### Sum scatter

Builds bubbles from X-axis and Y-axis numeric columns. Bubble size is the sum of the selected sum column.

## Variable Selector (How to Operate)

The variable selector is the left selector pane above the chart area.

1. Select an analysis type first.
2. Choose the required columns in the selector lists:
   - **Category column:** for category-based analyses.
   - **X-axis column:** and **Y-axis column:** for scatter analyses.
   - **Distribution column:** for distribution analyses.
   - **Sum column:** for sum and sum-scatter analyses; **Value column:** for category percentile values.
3. The result refreshes automatically after selection changes.

### Which selectors appear for each analysis type

- **Category count**: Category
- **Category sum**: Category + Sum
- **Category percentile values**: Category + Value
- **Category distribution count / count %**: Category + Distribution
- **Category distribution sum / sum %**: Category + Distribution + Sum
- **Count scatter**: Y-axis + X-axis (numeric columns)
- **Sum scatter**: Y-axis + X-axis + Sum (numeric columns)

### Date grouping

If the selected column is a DateTime column, a **Group by:** selector appears in the selector pane.

- Available groups: **Day**, **Week**, **Month**, **Quarter**, **Year**
- **Day** means no grouping (one point per date value).
- Changing the date group re-runs the analysis.

### Excluded columns information

If some columns cannot be selected (for example, too many categories, non-numeric for sum, or empty columns), use the **❢** info button in the selector to see the excluded columns and the reason for each one. Reasons include `The number of categories exceeds the maximum setting`, `Category text length exceeds the maximum setting`, `Non-categorical column`, `Date time column`, `Empty column` and `Non-numerical column`.

## Data Filter

Use the data filter panel to analyze a subset of rows.

- Show/hide it from **View > Data filter** or by the splitter.
- In the tree, check/uncheck values to include or exclude data.
- Right-click a date column to **Add Date Range** (or **Change Date Range** when one is already set).
- Other column commands are **Filter to a specific value**, **Remove**, **Re-load all values** and **Reset filter values**.
- `(Blanks)` and `(Null)` are explicit filter choices.
- After filter changes, the **Apply data filter** button turns green.
- Click **Apply data filter** to rebuild the analysis with the filtered data.

## Exclude Blanks

Use **Exclude blanks of Y-axis** on the toolbar to toggle blank category handling.

- Enabled only when the current category column includes blanks.
- You can also exclude blanks by data filter settings.
- **NULL** and blank values can be calculated separately, but this must be set in **Options** before starting analysis.

## Sort the Results

- Click a chart data grid column header to sort.
- For single-value results (for example, category count/sum), use the **Large to small** toggle button.
- For multi-column results (distribution/percentile), use the sort drop-down to choose the sort column.

## Search Categories

Search is available for non-scatter results when the chart data grid has more than 10 rows.

- Enter text in the search box and press **Enter**.
- Press **Enter** again, click **↓**, or press **F3** to move to the next match.
- Click **↑** to move to the previous match.
- Press **Esc** to clear the search. Editing the text clears the previous search too.
- When nothing matches, the window reports `No match found!`.

## Drill Down to Raw Data

The raw data panel shows rows behind chart/grid selections.

- Click chart bars/segments or chart data grid cells to load matching raw rows.
- For distribution analyses:
  - Click first column (category) to show all rows in that category.
  - Click an inner cell to show rows matching both distribution and category.
- For scatter analyses, click a bubble (or scatter row) to show rows matching that XY pair.
- Use **View > Show all raw data**, or the chart's total label, to show all loaded rows.

## Export and Copy

- Right-click the chart data grid or the raw data grid to copy/export.
- Use the **File** menu to export chart data (**Save Chart Data as...**) or raw data (**Save Raw Data as...**).
- Export format supports **Excel Workbook (*.xlsx)** and **CSV files (*.csv)**.
- CSV delimiter/quote options are in **Tools > Options**.
- You can also copy the chart image from **Edit > Copy Chart**, or the grid selections from **Edit > Copy Chart Data** and **Edit > Copy Raw Data Selections**.

[Back to Octofy User Manual](user-manual.md)

## Screenshots

![Category count](images/Octofy_Category_count.png)

![Category sum](images/Octofy_Category_sum.png)

![Category distribution count](images/Octofy_Category_distribution_count.png)

![Category distribution sum](images/Octofy_Category_distribution_sum.png)

![Category percentile values](images/Octofy_Category_percentile.png)

![Category distribution percentage](images/Octofy_Category_distribution_percentage.png)

![Count scatter](images/Octofy_Count_scatter.png)

![Sum scatter](images/Octofy_Sum_scatter.png)

