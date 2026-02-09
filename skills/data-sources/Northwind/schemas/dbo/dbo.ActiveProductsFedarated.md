# Table: [dbo].[ActiveProductsFedarated]

**Data Source:** Northwind
**Schema:** dbo
**Type:** Table

## Description

# **Table:** `[dbo].[ActiveProductsFedarated]`
> Stores details of products that are currently active and federated across multiple systems or sources within the organization.
---
### **Columns:**
| Ord | Name | Data Type | Description |
|:---:|:---:|:---:|:---|
| 1 | `ProductID` | INTEGER | Primary key, Unique identifier for the product. Reference: Products.ProductID |
| 2 | `ProductName` | NVARCHAR(40) | Name of the active federated product. |
---

