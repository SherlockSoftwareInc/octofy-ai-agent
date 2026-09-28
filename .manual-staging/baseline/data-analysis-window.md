# Data Analysis Window

This page describes the UI components of the Data Analysis window.

## Window Layout

The window contains these main areas:

- **Variable selector pane** (left, top): choose Category / Distribution / Sum variables.
- **Chart area** (right, top): displays analysis chart.
- **Chart data grid** (right, bottom): tabular summary of chart data.
- **Data filter pane** (left): filter source rows before analysis.
- **Raw data grid** (bottom): rows that match the selected chart/data point.
- **Toolbar** (top) and **Status bar** (bottom).

Panels can be shown/hidden from the **View** menu or by splitter controls.

## Menus

### File

| Menu item | Description |
| --- | --- |
| Export chart data | Export chart data. Supports `.xlsx` and `.csv`. |
| Export raw data | Export current raw data. Supports `.xlsx` and `.csv`. |
| Close | Close the window. |

### Edit

| Menu item | Description |
| --- | --- |
| Copy chart | Copy graph chart to clipboard. |
| Copy chart data | Copy chart data to clipboard. |
| Copy raw data selections | Copy selected raw grid data to clipboard. |

### Analysis

| Menu item | Description |
| --- | --- |
| Category count | Change analysis type to category count. |
| Category sum | Change analysis type to category sum. |
| Category percentile and average | Change analysis type to category percentile/average. |
| Category distribution count | Change analysis type to category distribution count. |
| Category distribution count % | Change analysis type to category distribution count percentage. |
| Category distribution sum | Change analysis type to category distribution sum. |
| Category distribution sum % | Change analysis type to category distribution sum percentage. |
| Scatter plot of count | Change analysis type to scatter count. |
| Scatter plot of sum | Change analysis type to scatter sum. |

### View

| Menu item | Description |
| --- | --- |
| Data filter | Show or hide data filter panel. |
| Chart data | Show or hide chart data panel. |
| Raw data list | Show or hide raw data grid panel. |
| Toolbar | Show or hide toolbar. |
| Status bar | Show or hide status bar. |
| Show all data | List all loaded source rows in the raw data grid. |

### Tools

| Menu item | Description |
| --- | --- |
| Options | Show CSV options dialog. |
| Percentiles | Set percentile values used by category percentile analysis. |

## Toolbar

| Item | Description |
| --- | --- |
| Close | Close the window. |
| Analysis type buttons | Switch between analysis types (same as **Analysis** menu). |
| Exclude/Include blanks | Toggle whether blank categories are excluded. |
| Sort | Sort single-value result sets (for example count/sum). |
| Sort drop-down | Choose sort column for multi-column result sets (for example distribution/percentile). |
| Search for | Text box to search categories. |
| Search results | Current selection index and match count. |
| Next | Move to next match. |
| Previous | Move to previous match. |

## Context Menus

### Chart data grid

- **Copy**
- **Export chart data**

### Raw data grid

- **Copy**
- **Export raw data**

## Status Bar

| Item | Description |
| --- | --- |
| Message | Current operation status/progress. |
| Object name | Selected table/view name. |
| Rows | Number of source rows. |
| Load time | Time used to read source data. |
| Analysis time | Time used to parse/build analysis source. |
| Calculate time | Time used to calculate current chart/grid result. |
| Categories | Number of displayed categories. |
| Rn | Currently selected result row number. |

## Notes

- `NULL` and blank values can be calculated separately if that option is set before starting analysis.
- Search controls appear only when search is available for the current result.

[Back to Windows and Elements](windows-and-elements.md)

## Screenshots

![Data analysis window screenshot](images/Octofy_Data_analysis.png)

