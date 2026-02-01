# Table: [dbo].[Categories]

**Data Source:** Auto-generated  
**Schema:** dbo  
**Type:** Table  

## Description

# **Table:** `[dbo].[Categories]`
> Stores information about product categories, allowing for the classification and organization of products within the sales database.
---
### **Columns:**
| Ord | Name | Data Type | Description |
|:---:|:---:|:---:|:---|
| 1 | `CategoryID` | INTEGER | Primary key, Unique identifier for each category. Serves as the primary key. |
| 2 | `CategoryName` | NVARCHAR(15) | Name of the product category. |
| 3 | `Description` | NTEXT | Detailed description or notes about the category. |
| 4 | `Picture` | IMAGE | Optional image representing the category. |
---
