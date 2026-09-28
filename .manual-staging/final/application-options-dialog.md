# Application Options Dialog

The **Options** dialog allows you to configure application-wide settings. Open it from **Tools > Options**.

The dialog has no tabs. It groups the settings into **Calculation exclusions** and **Loading data**, and closes with **OK** (save) or **Cancel** (discard).

---

## Calculation Exclusions

These settings control which columns are included or excluded when performing analysis.

| Setting | Description | Valid Range | Default |
| --- | --- | --- | --- |
| Maximum categories on y-axis | Columns whose distinct value count exceeds this number are excluded from y-axis analysis. | 256 – 82,595,524 | 524,288 |
| Maximum categories on x-axis | Columns whose distinct value count exceeds this number are excluded from x-axis analysis. | 16 – 128 | 64 |
| Maximum category name length | Category names longer than this character limit are truncated during analysis. | 16 – 32,768 | 1,024 |
| Merge NULL and Blank Values | When checked, NULL and empty-string values are treated as a single category during analysis. | — | Enabled |

Each of the three numeric settings accepts digits only; a non-numeric entry is rejected with **Invalid input** and "Please enter numeric only.", and a value outside its range is rejected with "Please enter a number between 256 and 82,595,524.", "Please enter a number between 16 and 128.", or "Please enter a number between 16 and 32768." respectively.

---

## Loading Data

Controls the database connection behaviour when loading data.

| Setting | Description | Default |
| --- | --- | --- |
| Connection timeout | Maximum number of seconds to wait for a database query to complete before a connection timeout error is raised. | 120 seconds |

The value must be numeric; the dialog accepts any number and does not enforce a range.

---

[Back to Windows and Elements](windows-and-elements.md)

## Screenshots

![Options window screenshot](images/Octofy_Options.png)
