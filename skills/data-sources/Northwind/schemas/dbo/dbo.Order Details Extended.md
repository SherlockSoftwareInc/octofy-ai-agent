# Table: [dbo].[Order Details Extended]

**Data Source:** Auto-generated  
**Schema:** dbo  
**Type:** View  

## Description

# **View:** `[dbo].[Order Details Extended]`
> Provides detailed information for each order line item, including product details, unit price, quantity, discount, and the calculated extended price per item.
---
### **Columns:**
| Ord | Name | Data Type | Description |
|:---:|:---:|:---:|:---|
| 1 | `OrderID` | INTEGER | Identifier of the order associated with this line item. Reference: Orders.OrderID |
| 2 | `ProductID` | INTEGER | Identifier of the product associated with this line item. Reference: Products.ProductID |
| 3 | `ProductName` | NVARCHAR(40) | Name of the product for this order line item. |
| 4 | `UnitPrice` | MONEY | Unit price of the product at the time of the order. |
| 5 | `Quantity` | SMALLINT | Number of product units ordered in this line item. |
| 6 | `Discount` | REAL | Discount rate applied to this order line item. |
| 7 | `ExtendedPrice` | MONEY | Total price for the line item after applying the discount to the ordered quantity. |
---
