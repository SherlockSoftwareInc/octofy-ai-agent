# Table: [dbo].[EmployeeTerritories]

**Data Source:** Auto-generated  
**Schema:** dbo  
**Type:** Table  

## Description

# **Table:** `[dbo].[EmployeeTerritories]`
> Stores the associations between employees and the territories to which they are assigned.
---
### **Columns:**
| Ord | Name | Data Type | Description |
|:---:|:---:|:---:|:---|
| 1 | `EmployeeID` | INTEGER | Primary key, Unique identifier of the employee assigned to the territory. Reference: Employees.EmployeeID |
| 2 | `TerritoryID` | NVARCHAR(20) | Primary key, Unique identifier of the territory assigned to the employee. Reference: Territories.TerritoryID |
---
