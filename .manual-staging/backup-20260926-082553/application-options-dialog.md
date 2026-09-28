# Application Options Dialog

# Options Dialog

The **Options** dialog allows you to configure application-wide settings. Open it from the **Options** menu item.

---

## Calculation Exclusions

These settings control which columns are included or excluded when performing analysis.

| Setting | Description | Valid Range | Default |
| --- | --- | --- | --- |
| Maximum categories on y-axis | Columns whose distinct value count exceeds this number are excluded from y-axis analysis. | 256 – 82,595,522 | 524,288 |
| Maximum categories on x-axis | Columns whose distinct value count exceeds this number are excluded from x-axis analysis. | 16 – 128 | 64 |
| Maximum category name length | Category names longer than this character limit are truncated during analysis. | 16 – 32,768 | 1,024 |
| Merge NULL and Blank Values | When checked, NULL and empty-string values are treated as a single category during analysis. | — | Enabled |

---

## Loading Data

Controls the database connection behaviour when loading data.

| Setting | Description | Default |
| --- | --- | --- |
| Connection timeout | Maximum number of seconds to wait for a database query to complete before a connection timeout error is raised. | 30 seconds |

---

[Back to Windows and Elements](windows-and-elements.md)

## Screenshots

![Options window screenshot](images/Octofy_Options.png)

