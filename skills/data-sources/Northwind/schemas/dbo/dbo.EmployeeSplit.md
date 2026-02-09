# Table: [dbo].[EmployeeSplit]

**Data Source:** Northwind
**Schema:** dbo
**Type:** Table

## Description

# **Table:** `[dbo].[EmployeeSplit]`
> Stores supplementary employee information, such as phone extension and photo path, to extend the core employee records.
---
### **Columns:**
| Ord | Name | Data Type | Description |
|:---:|:---:|:---:|:---|
| 1 | `ID` | INTEGER | Primary key, Unique identifier for the employee. Reference: Employee.ID |
| 2 | `Extension` | NVARCHAR(4) | Employee's internal phone extension number. |
| 3 | `PhotoPath` | NVARCHAR(255) | File path or URL to the employee's photo. |
---

