# Table: [dbo].[Department]

**Data Source:** Auto-generated  
**Schema:** dbo  
**Type:** Table  

## Description

# **Table:** `[dbo].[Department]`
> The Department table stores information about departmental structure within an organization. It includes details such as department IDs, names, manager information, parent department relationships, and system timestamps for tracking and logging.
---
### **Columns:**
| Ord | Name | Data Type | Description |
|:---:|:---:|:---:|:---|
| 1 | `DeptID` | INTEGER | Primary key, Unique identifier for each department |
| 2 | `DeptName` | VARCHAR(50) | Name of the department |
| 3 | `ManagerID` | INTEGER | Employee ID of the department manager |
| 4 | `ParentDeptID` | INTEGER | ID of the parent department (if applicable) |
| 5 | `SysStartTime` | DATETIME2 | Timestamp when the department was created or last updated in the system |
| 6 | `SysEndTime` | DATETIME2 | Timestamp when the department was last updated or ended in the system |
---
