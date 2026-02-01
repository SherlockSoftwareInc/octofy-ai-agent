# Table: [dbo].[Order Subtotals]

**Data Source:** Auto-generated  
**Schema:** dbo  
**Type:** View  

## Description

# **View:** `[dbo].[Order Subtotals]`
> Stores calculated subtotal amounts for each order, typically used for reporting, analysis, or as a derived view of order line items.
---
### **Columns:**
| Ord | Name | Data Type | Description |
|:---:|:---:|:---:|:---|
| 1 | `OrderID` | INTEGER | Unique identifier for the order. Reference: Orders.OrderID |
| 2 | `Subtotal` | MONEY | Calculated total amount for the order before taxes, discounts, or shipping charges, derived from the sum of order details. |
---
