# Table: [dbo].[Order Details]

**Data Source:** Northwind
**Schema:** dbo
**Type:** Table

## Description

# **Table:** `[dbo].[Order Details]`
> This table serves as a line-item registry for every product included in a customer order.
---
### **Columns:**
| Ord | Name | Data Type | Description |
|:---:|:---:|:---:|:---|
| 1 | `OrderID` | INTEGER | Primary key, Unique identifier for the parent order. Part of the composite primary key. Reference: [dbo].[Orders].[OrderID] |
| 2 | `ProductID` | INTEGER | Primary key, Unique identifier for the product being purchased. Part of the composite primary key. Reference [dbo].[Products].[ProductID], Reference: [dbo].[Products].[ProductID] |
| 3 | `UnitPrice` | MONEY | The cost per unit of the product at the time of the transaction. |
| 4 | `Quantity` | SMALLINT | The total number of units of the product associated with this order line item. |
| 5 | `Discount` | REAL | The percentage or fixed reduction applied to the unit price (usually expressed as a decimal, e.g., 0.15 for 15%). |
---

