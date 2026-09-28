# Data Analysis Window

This page describes the UI components of the Data Analysis window (`Data table analysis`).

## Window Layout

The window contains these main areas:

- **Variable selector pane** (left, top): choose Category / Distribution / Sum variables.
- **Chart area** (right, top): displays the analysis chart.
- **Chart data grid** (right, bottom): tabular summary of chart data.
- **Data filter pane** (left): filter source rows before analysis.
- **Raw data grid** (bottom): rows that match the selected chart/data point.
- **Toolbar** (top) and **Status bar** (bottom).
- **AI Assistant panel** (right side, collapsible).

Panels can be shown/hidden from the **View** menu or by splitter controls.

## Menus

### File

| Menu item | Description |
| --- | --- |
| Save Chart Data as... | Export chart data. Supports `.xlsx` and `.csv`. |
| Save Raw Data as... | Export raw data. Supports `.xlsx` and `.csv`. |
| Close | Close the window. |

### Edit

| Menu item | Description |
| --- | --- |
| Copy Chart | Copy the chart image to the clipboard. |
| Copy Chart Data | Copy chart data to the clipboard. |
| Copy Raw Data Selections | Copy selected raw grid data to the clipboard. |

### Analysis

| Menu item | Description |
| --- | --- |
| Category count | Change analysis type to category count. |
| Category sum | Change analysis type to category sum. |
| Category percentile values | Change analysis type to category percentile values. |
| Category distribution count | Change analysis type to category distribution count. |
| Category distribution count % | Change analysis type to category distribution count percentage. |
| Category distribution sum | Change analysis type to category distribution sum. |
| Category distribution sum % | Change analysis type to category distribution sum percentage. |
| Count scatter | Change analysis type to count scatter. |
| Sum scatter | Change analysis type to sum scatter. |

### View

| Menu item | Description |
| --- | --- |
| Data filter | Show or hide the data filter panel. |
| Chart data | Show or hide the chart data panel. |
| Raw data list | Show or hide the raw data grid panel. |
| Toolbar | Show or hide the toolbar. |
| Status bar | Show or hide the status bar. |
| Show all raw data | List all loaded source rows in the raw data grid. |
| AI Assistant | Show or hide the AI Assistant chat panel (same action as the toolbar button). |

### Tools

| Menu item | Description |
| --- | --- |
| Options | Show the CSV options dialog (delimiter and quote behavior). |
| Percentils | Set the percentile values used by the category percentile analysis. Enabled only for **Category percentile values**. |

## Toolbar

| Item | Description |
| --- | --- |
| Close | Close the window. |
| Analysis type: | Label in front of the analysis type buttons. |
| Category count | Switch to the category count chart. |
| Category sum | Switch to the category sum chart. |
| Category percentile | Switch to the category percentile values chart. |
| Category distribution count | Switch to the category distribution count chart. |
| Category distribution count % | Switch to the category distribution count percentage chart. |
| Category distribution sum | Switch to the category distribution sum chart. |
| Category distribution sum % | Switch to the category distribution sum percentage chart. |
| X Y scatter | Switch to the count scatter chart. |
| X Y scatter sum | Switch to the sum scatter chart. |
| Exclude blanks of Y-axis | Toggle whether the blank category is excluded. |
| Sort (drop-down) | Choose the sort column for multi-column result sets. Tooltip: `Choose the sort order`. |
| Large to small | Toggle sorting the single-value result set from large to small. Tooltip: `Sort from large to small`. |
| Search for: | Text box to search categories. Tooltip: `Search categories`. |
| 0/0 | Current match position and number of matches. |
| ↓ | Move to the next match. Tooltip: `Next`. |
| ↑ | Move to the previous match. Tooltip: `Previous`. |
| AI Assistant | Show or hide the AI Assistant chat panel. Tooltip: `Toggle AI chat panel`. While the panel is shown the button reads **Hide AI Chat**. |

## AI Assistant

The **AI Assistant** toolbar button and the **View > AI Assistant** menu item show the chat panel on the right side of the window. The panel opens only after an LLM provider is configured and after you agree to the AI data-analysis consent prompt. The panel is always closed when the window opens.

The panel runs in the analysis mode of the chat control:

- There is no mode picker. The panel shows the two context toggles **Include chart data** and **Include raw data**, which decide whether the chart data and the raw rows are sent to the provider together with the description of the analysed data set.
- The input box placeholder is `Ask for chart updates, filtering, sorting, and analysis refinements…`.
- Ask in plain language to change the chart type, choose the category / distribution / sum column, group a date column, filter rows, clear the filter, exclude blanks, sort the result, or to explain what the current result shows.
- The assistant answers in markdown and applies the requested change to the window itself. Each applied change is reported in the conversation as a short result message.
- Type a question in the input box and press **Enter** to send it with the **Send** button (hold **Shift** and press **Enter** to insert a line break). While a reply is streaming, **Send** is replaced by **Stop**; click it to cancel the reply.
- Answers stream in as they are generated. Each assistant reply has a **Copy** button that copies the raw markdown of that answer.

## Context Menus

### Chart data grid

- **Copy chart data**
- **Save Chart Data as...**

### Raw data grid

- **Copy raw data selections**
- **Save Raw Data as...**

## Status Bar

| Item | Description |
| --- | --- |
| Message | Current operation status/progress, for example `Loading data...`, `Please wait while calculating {0}%...`, `Build data for the chart...`, and the number of excluded blanks. |
| Table/View name | Selected table/view name. |
| Raw data rows | Number of source rows, shown as `Raw data rows: {0}`. |
| Load data | Time used to read source data, shown as `Load data: {0}s`. |
| Data set analysis | Time used to parse/build the analysis source, shown as `Data set analysis: {0}s`. |
| Build chart data | Time used to calculate the current chart/grid result, shown as `Build chart data: {0}s`. |
| Categories | Number of displayed categories, shown as `Categories: {0}`. |
| Rn | Currently selected result row, shown as `Rn: {0}`. |

## Notes

- `NULL` and blank values can be calculated separately if that option is set before starting analysis. They are displayed as **(Null)** and **(Blanks)**.
- Search controls appear only when search is available for the current result: the chart data grid has more than 10 rows and the analysis type is not a scatter chart.
- Sort controls depend on the analysis type: the single **Large to small** toggle is shown by the count/sum analyses and the sort drop-down by the multi-column analyses.
- The category percentile values chart is drawn as a box plot, and its percentile values come from **Tools > Percentils**.

[Back to Windows and Elements](windows-and-elements.md)

## Screenshots

![Data analysis window screenshot](images/Octofy_Data_analysis.png)
