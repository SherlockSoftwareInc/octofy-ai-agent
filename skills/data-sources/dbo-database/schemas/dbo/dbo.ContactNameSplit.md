# Table: [dbo].[ContactNameSplit]

**Data Source:** Auto-generated  
**Schema:** dbo  
**Type:** Table  
**Era:** Unknown  
**Record Count:** Unknown  
**Update Frequency:** Unknown

## Description

# **Table:** `[dbo].[ContactNameSplit]`
> Stores parsed contact information, including separated name, title, fax number, and contact type for individuals associated with the business.
---
### **Columns:**
| Ord | Name | Data Type | Description |
|:---:|:---:|:---:|:---|
| 1 | `ID` | INTEGER | Primary key, Unique identifier for each contact record. |
| 2 | `Name` | NVARCHAR(30) | The full or parsed name of the contact person. |
| 3 | `Title` | NVARCHAR(30) | The job title or position of the contact person. |
| 4 | `Fax` | NVARCHAR(24) | Fax number associated with the contact person. |
| 5 | `ContactType` | NVARCHAR(50) | Specifies the type or role of the contact, such as customer, supplier, or employee. |
---


## Columns

## Common Queries

(Requires manual documentation)

## Related Tables

(Requires manual documentation)

## Data Quality Notes

(Requires manual documentation)
