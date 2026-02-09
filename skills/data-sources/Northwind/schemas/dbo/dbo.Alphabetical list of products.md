# View: [dbo].[Alphabetical list of products]

**Data Source:** Northwind
**Schema:** dbo
**Type:** View

## Description

# **View:** `[dbo].[Alphabetical list of products]`
> View providing an alphabetical listing of products with related supplier and category information, including inventory and pricing details.
---
### **Columns:**
| Ord | Name | Data Type | Description |
|:---:|:---:|:---:|:---|
| 1 | `ProductID` | INTEGER | Unique identifier for each product. Reference: Products.ProductID |
| 2 | `ProductName` | NVARCHAR(40) | Name of the product. |
| 3 | `SupplierID` | INTEGER | Identifier for the supplier providing the product. Reference: Suppliers.SupplierID |
| 4 | `CategoryID` | INTEGER | Identifier for the category to which the product belongs. Reference: Categories.CategoryID |
| 5 | `QuantityPerUnit` | NVARCHAR(20) | Description of the quantity of the product per unit (e.g., '24 - 12 oz bottles'). |
| 6 | `UnitPrice` | MONEY | Price of a single unit of the product. |
| 7 | `UnitsInStock` | SMALLINT | Number of units of the product currently in stock. |
| 8 | `UnitsOnOrder` | SMALLINT | Number of units of the product that have been ordered but not yet received. |
| 9 | `ReorderLevel` | SMALLINT | Minimum number of units in stock before a reorder is suggested. |
| 10 | `Discontinued` | BIT | Indicates whether the product is discontinued (1 = discontinued, 0 = active). |
| 11 | `CategoryName` | NVARCHAR(15) | Name of the category to which the product belongs. |
---

