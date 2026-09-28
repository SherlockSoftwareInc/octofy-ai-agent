# Column Values Frequency Window

The Column Values Frequency window displays the distribution of values in a selected column as both a bar chart and a data grid. It shows each distinct value (category), its occurrence count, and its percentage of the total. The window is opened from the data explorer by selecting a column on a table or view.

## Toolbar

| Item | Description |
| --- | --- |
| Close | Close the window. |
| Graph view | Switch to the bar chart view. |
| Data view | Switch to the data grid view. The grid shows three columns: the category value, its count, and its percentage of the total. |
| Sort | Toggle sorting by count from large to small (tooltip: `Sort by counts of category from large to small`). When active, results are sorted by the Count column; when inactive, results are sorted by the category value. |
| Blanks | Toggle whether blank and null values are included in the chart and grid. The button is labelled **Blanks** and its tooltip switches between `Exclude blanks` and `Include blanks`. The button is only enabled when the column contains blank or null values. When blanks are excluded, the status bar shows the number of excluded blanks. |
| Group by: *(date columns only)* | Drop-down list to group date column values by a time period. Available options are: Day, Week, Month, Quarter, and Year. **Day** means no grouping. This control is only visible when the selected column is a date or date/time column, and the last used value is restored the next time a date column is opened. |
| Search for: | Text box to search for a category value. Type text and press **Enter** to find the first match. Press **Enter** again or click **Next** to cycle through further matches. Press **Escape** to clear the search. The search box is only visible when the number of categories exceeds 10 or when category names are truncated. |
| Search results | Shows the current match position and total number of matches (e.g., `2/5`). Visible only when a search returns more than one result. |
| Next | Navigate to the next matching category. Visible only when a search has multiple results. |
| Previous | Navigate to the previous matching category. Visible only when a search has multiple results. |

## Data Grid Columns

| Column | Description |
| --- | --- |
| *(Column name)* | The distinct category value from the selected column. Blank values are shown as **(Blanks)** and null values as **(Null)**. |
| Count | The number of rows containing this category value. |
| Percent | The percentage this category represents of the total non-blank row count, formatted to two decimal places with a `%` suffix. This column cannot be sorted by clicking its header. |

## Status Bar

| Item | Description |
| --- | --- |
| Message | Displays progress messages such as `Calculating...` or `Populating the chart...`, and shows the number of blanks excluded when the blanks are excluded (for example `3 blanks excluded`). |
| Object name | The fully qualified name of the database table or view. |
| Column name | The name of the selected column. |
| Categories | The number of distinct category values currently displayed, shown as `Categories: 42`. |
| Rn | The row number of the currently selected category, shown as `Rn: 7`. |

## Keyboard Shortcuts

| Key | Action |
| --- | --- |
| **F3** | Navigate to the next search match (when the search box is visible and a search term is active). |
| **Escape** | Clear the search text box and reset the current search. |

## Notes

- Selecting a row in the data grid highlights the corresponding bar in the chart, and clicking a bar in the chart selects the corresponding row in the grid.
- Category names that exceed the maximum configured length are truncated. A warning is shown in the status bar when this occurs.
- The chart is not shown when the number of categories exceeds 50,000; a notice is displayed in the chart area instead.
- The value frequency itself is computed by the database with a grouped count query, so the numbers are the server-side counts of the selected column.
- Form size, position, and window state are saved and restored between sessions.
- For date columns, the last-used date grouping is also saved and restored.

[Back to Windows and Elements](windows-and-elements.md)

## Screenshots

![Column values frequency window screenshot](images/Octofy_Column_value_frequency.png)
