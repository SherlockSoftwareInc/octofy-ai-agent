# Data Analysis

Use the Data Analysis window to summarize table data, visualize trends, and inspect matching raw rows.

## Analysis Types

Select an analysis type from the toolbar or **Analysis** menu.

### Category count

Groups rows by one category column and returns row counts.

### Category sum

Groups rows by one category column and returns the sum of a numeric column.

### Category percentile and average

Groups rows by one category column and returns percentile values and average for a numeric column.

### Category distribution count

Groups rows by category and distribution columns and returns counts.

### Category distribution count %

Groups rows by category and distribution columns and returns percentage values (100% stacked result).

### Category distribution sum

Groups rows by category and distribution columns and returns summed values.

### Category distribution sum %

Groups rows by category and distribution columns and returns percentage values based on sums.

### Scatter plot of count

Builds bubbles from X-axis and Y-axis numeric columns. Bubble size is count.

### Scatter plot of sum

Builds bubbles from X-axis and Y-axis numeric columns. Bubble size is the sum of the selected sum column.

## Variable Selector (How to Operate)

The variable selector is the left selector pane above the chart area.

1. Select an analysis type first.
2. Choose the required columns:
   - **Category column** for category-based analyses.
   - **X-axis / distribution column** for distribution or scatter analyses.
   - **Sum column** for sum/percentile/sum-scatter analyses.
3. The result refreshes automatically after selection changes.

### Which selectors appear for each analysis type

- **Category count**: Category only
- **Category sum**: Category + Sum
- **Category percentile and average**: Category + Sum
- **Category distribution count / count %**: Category + Distribution
- **Category distribution sum / sum %**: Category + Distribution + Sum
- **Scatter count**: Y-axis + X-axis (numeric columns)
- **Scatter sum**: Y-axis + X-axis + Sum (numeric columns)

### Date grouping

If the selected category column is a DateTime column, a date grouping selector appears.

- Available groups: **None**, **Week**, **Month**, **Quarter**, **Calendar Year**
- Changing the date group re-runs the analysis.

### Excluded columns information

If some columns cannot be selected (for example, too many categories, non-numeric for sum, or empty columns), use the **info** button in the selector to see excluded columns and reasons.

## Data Filter

Use the data filter panel to analyze a subset of rows.

- Show/hide it from **View > Data filter** or by the splitter.
- In the tree, check/uncheck values to include or exclude data.
- For DateTime columns, right-click and choose **Add date range**.
- After filter changes, the **Apply** button turns green.
- Click **Apply** to rebuild analysis with filtered data.

## Exclude Blanks

Use **Exclude blanks** on the toolbar to toggle blank category handling.

- Enabled only when the current category column includes blanks.
- You can also exclude blanks by data filter settings.
- **NULL** and blank values can be calculated separately, but this must be set in **Options** before starting analysis.

## Sort the Results

- Click a chart data grid column header to sort.
- For single-value results (for example, category count/sum), use the **Sort** toggle button.
- For multi-column results (distribution/percentile), use the **Sort** drop-down to choose the sort column.

## Search Categories

Search is available for non-scatter results when row count is greater than 10.

- Enter text in the search box and press **Enter**.
- Use **Next** / **Previous** buttons to move through matches.
- Keyboard shortcuts: **Enter** or **F3** for next match, **Esc** to clear.

## Drill Down to Raw Data

The raw data panel shows rows behind chart/grid selections.

- Click chart bars/segments or chart data grid cells to load matching raw rows.
- For distribution analyses:
  - Click first column (category) to show all rows in that category.
  - Click an inner cell to show rows matching both distribution and category.
- For scatter analyses, click a bubble (or scatter row) to show rows matching that XY pair.
- Use **View > Show all data** to show all loaded rows.

## Export and Copy

- Right-click chart data grid or raw data grid to copy/export.
- Use **File** menu to export chart data or raw data.
- Export format supports **Excel (.xlsx)** and **CSV (.csv)**.
- CSV delimiter/quote options are in **Tools > Options**.
- You can also copy chart image from **Edit > Copy chart**.

[Back to Octofy User Manual](user-manual.md)

## Screenshots

![Category count](images/Octofy_Category_count.png)

![Category sum](images/Octofy_Category_sum.png)

![Category distribution count](images/Octofy_Category_distribution_count.png)

![Category distribution sum](images/Octofy_Category_distribution_sum.png)

![Category percentile and average](images/Octofy_Category_percentile.png)

![Category distribution percentage](images/Octofy_Category_distribution_percentage.png)

![Scatter plot of count](images/Octofy_Count_scatter.png)

![Scatter plot of sum](images/Octofy_Sum_scatter.png)

