# Table: [dbo].[Products]

**Data Source:** Northwind
**Schema:** dbo
**Type:** Table

## Description

# **Table:** `[dbo].[Products]`
> Stores information about all specialty food products available for sale, including product details, supplier, category, pricing, and inventory status.
---
### **Columns:**
| Ord | Name | Data Type | Description |
|:---:|:---:|:---:|:---|
| 1 | `ProductID` | INTEGER | Primary key, Unique identifier for each product. |
| 2 | `ProductName` | NVARCHAR(40) | Name of the product. |
| 3 | `SupplierID` | INTEGER | Identifier of the supplier providing the product. Reference: Suppliers.SupplierID |
| 4 | `CategoryID` | INTEGER | Identifier of the product category. Reference: Categories.CategoryID |
| 5 | `QuantityPerUnit` | NVARCHAR(20) | Description of the quantity of product per unit (e.g., '24 - 12 oz bottles'). |
| 6 | `UnitPrice` | MONEY | Price of a single unit of the product. |
| 7 | `UnitsInStock` | SMALLINT | Current quantity of the product available in inventory. |
| 8 | `UnitsOnOrder` | SMALLINT | Quantity of the product that has been ordered but not yet received. |
| 9 | `ReorderLevel` | SMALLINT | Inventory level at which new stock should be ordered. |
| 10 | `Discontinued` | BIT | Indicates whether the product is discontinued (1 = discontinued, 0 = active). |
---

