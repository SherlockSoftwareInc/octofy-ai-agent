# Table: [dbo].[Territories]

**Data Source:** Auto-generated  
**Schema:** dbo  
**Type:** Table  
**Era:** Unknown  
**Record Count:** Unknown  
**Update Frequency:** Unknown

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


## Columns

## Common Queries

(Requires manual documentation)

## Related Tables

(Requires manual documentation)

## Data Quality Notes

(Requires manual documentation)
