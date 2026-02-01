# Table: [dbo].[Summary of Sales by Quarter]

**Data Source:** Auto-generated  
**Schema:** dbo  
**Type:** View  

## Description

# **View:** `[dbo].[Summary of Sales by Quarter]`
> Aggregated view showing sales subtotals grouped by quarterly shipping periods. Provides a high-level overview of revenue trends across quarters.
---
### **Columns:**
| Ord | Name | Data Type | Description |
|:---:|:---:|:---:|:---|
| 1 | `ShippedDate` | DATETIME | The date when the order was shipped, used to determine the quarter for sales aggregation. |
| 2 | `OrderID` | INTEGER | Unique identifier for the order. Reference: Orders.OrderID |
| 3 | `Subtotal` | MONEY | Total sales amount for the order before taxes and shipping, expressed in monetary value. |
---
