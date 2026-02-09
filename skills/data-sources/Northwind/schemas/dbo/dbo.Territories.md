# Table: [dbo].[Territories]

**Data Source:** Northwind
**Schema:** dbo
**Type:** Table

## Description

# **Table:** `[dbo].[Territories]`
> Stores information about sales territories, including their unique identifiers, descriptions, and associated regions.
---
### **Columns:**
| Ord | Name | Data Type | Description |
|:---:|:---:|:---:|:---|
| 1 | `TerritoryID` | NVARCHAR(20) | Primary key, Unique identifier for the territory. |
| 2 | `TerritoryDescription` | NCHAR(50) | Descriptive name or details of the territory. |
| 3 | `RegionID` | INTEGER | Identifier of the region to which the territory belongs. Reference: Regions.RegionID |
---

