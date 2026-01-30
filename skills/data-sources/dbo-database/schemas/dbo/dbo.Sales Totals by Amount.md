# Table: [dbo].[Sales Totals by Amount]

**Data Source:** Auto-generated  
**Schema:** dbo  
**Type:** View  
**Era:** Unknown  
**Record Count:** Unknown  
**Update Frequency:** Unknown

## Description

# **View:** `[dbo].[Sales Totals by Amount]`
> Aggregates sales data showing total order amounts with associated customer and shipping information for analysis of high-value transactions.
---
### **Columns:**
| Ord | Name | Data Type | Description |
|:---:|:---:|:---:|:---|
| 1 | `SaleAmount` | MONEY | Total monetary value of the order, calculated from order details. |
| 2 | `OrderID` | INTEGER | Unique identifier for the order. Reference:Orders.OrderID |
| 3 | `CompanyName` | NVARCHAR(40) | Name of the customer company that placed the order. |
| 4 | `ShippedDate` | DATETIME | Date and time when the order was shipped to the customer. |
---


## Columns

## Common Queries

(Requires manual documentation)

## Related Tables

(Requires manual documentation)

## Data Quality Notes

(Requires manual documentation)
