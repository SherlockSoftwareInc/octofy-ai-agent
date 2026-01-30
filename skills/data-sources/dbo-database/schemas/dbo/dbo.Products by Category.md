# Table: [dbo].[Products by Category]

**Data Source:** Auto-generated  
**Schema:** dbo  
**Type:** View  
**Era:** Unknown  
**Record Count:** Unknown  
**Update Frequency:** Unknown

## Description

# **View:** `[dbo].[Products by Category]`
> Categorized product listing showing inventory status and availability. This view organizes products by their category for reporting and inventory management purposes.
---
### **Columns:**
| Ord | Name | Data Type | Description |
|:---:|:---:|:---:|:---|
| 1 | `CategoryName` | NVARCHAR(15) | Name of the product category. |
| 2 | `ProductName` | NVARCHAR(40) | Name of the product. |
| 3 | `QuantityPerUnit` | NVARCHAR(20) | Packaging description indicating quantity contained per unit. |
| 4 | `UnitsInStock` | SMALLINT | Current number of units available in inventory. |
| 5 | `Discontinued` | BIT | Flag indicating whether the product has been discontinued (1 = discontinued, 0 = active). |
---


## Columns

## Common Queries

(Requires manual documentation)

## Related Tables

(Requires manual documentation)

## Data Quality Notes

(Requires manual documentation)
