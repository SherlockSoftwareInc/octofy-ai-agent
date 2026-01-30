# Table: [dbo].[Summary of Sales by Year]

**Data Source:** Auto-generated  
**Schema:** dbo  
**Type:** View  
**Era:** Unknown  
**Record Count:** Unknown  
**Update Frequency:** Unknown

## Description

# **View:** `[dbo].[Summary of Sales by Year]`
> Aggregated view showing annual sales totals for completed orders, providing a high-level overview of revenue by year.
---
### **Columns:**
| Ord | Name | Data Type | Description |
|:---:|:---:|:---:|:---|
| 1 | `ShippedDate` | DATETIME | Date when the order was shipped to the customer. Used to group sales by calendar year. |
| 2 | `OrderID` | INTEGER | Unique identifier for the order. Reference:Orders.OrderID |
| 3 | `Subtotal` | MONEY | Total monetary value of the order before taxes and shipping, aggregated for reporting. |
---


## Columns

## Common Queries

(Requires manual documentation)

## Related Tables

(Requires manual documentation)

## Data Quality Notes

(Requires manual documentation)
