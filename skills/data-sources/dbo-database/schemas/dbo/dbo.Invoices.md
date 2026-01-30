# Table: [dbo].[Invoices]

**Data Source:** Auto-generated  
**Schema:** dbo  
**Type:** View  
**Era:** Unknown  
**Record Count:** Unknown  
**Update Frequency:** Unknown

## Description

# **View:** `[dbo].[Invoices]`
> Stores detailed invoice information for customer orders, including shipping details, customer information, order specifics, and line item details with pricing.
---
### **Columns:**
| Ord | Name | Data Type | Description |
|:---:|:---:|:---:|:---|
| 1 | `ShipName` | NVARCHAR(40) | Name of the recipient or company at the shipping address. |
| 2 | `ShipAddress` | NVARCHAR(60) | Street address for shipping delivery. |
| 3 | `ShipCity` | NVARCHAR(15) | City for shipping delivery. |
| 4 | `ShipRegion` | NVARCHAR(15) | Region or state for shipping delivery. |
| 5 | `ShipPostalCode` | NVARCHAR(10) | Postal or ZIP code for shipping delivery. |
| 6 | `ShipCountry` | NVARCHAR(15) | Country for shipping delivery. |
| 7 | `CustomerID` | NCHAR(5) | Unique identifier for the customer. Reference: Customers.CustomerID |
| 8 | `CustomerName` | NVARCHAR(40) | Name of the customer or company placing the order. |
| 9 | `Address` | NVARCHAR(60) | Customer's primary street address. |
| 10 | `City` | NVARCHAR(15) | Customer's primary city. |
| 11 | `Region` | NVARCHAR(15) | Customer's primary region or state. |
| 12 | `PostalCode` | NVARCHAR(10) | Customer's primary postal or ZIP code. |
| 13 | `Country` | NVARCHAR(15) | Customer's primary country. |
| 14 | `Salesperson` | NVARCHAR(31) | Name of the employee responsible for the sale. Reference: Employees.EmployeeID |
| 15 | `OrderID` | INTEGER | Unique identifier for the order. Reference: Orders.OrderID |
| 16 | `OrderDate` | DATETIME | Date and time when the order was placed. |
| 17 | `RequiredDate` | DATETIME | Date by which the order is required to be delivered. |
| 18 | `ShippedDate` | DATETIME | Date when the order was shipped (nullable if not yet shipped). |
| 19 | `ShipperName` | NVARCHAR(40) | Name of the shipping company used for delivery. Reference: Shippers.ShipperID |
| 20 | `ProductID` | INTEGER | Unique identifier for the product. Reference: Products.ProductID |
| 21 | `ProductName` | NVARCHAR(40) | Name of the product ordered. |
| 22 | `UnitPrice` | MONEY | Price per unit of the product at the time of order. |
| 23 | `Quantity` | SMALLINT | Number of units ordered for this product. |
| 24 | `Discount` | REAL | Discount percentage applied to this line item (typically 0-1). |
| 25 | `ExtendedPrice` | MONEY | Calculated line item total: (UnitPrice * Quantity) * (1 - Discount). |
| 26 | `Freight` | MONEY | Shipping cost charged for the entire order. |
---


## Columns

## Common Queries

(Requires manual documentation)

## Related Tables

(Requires manual documentation)

## Data Quality Notes

(Requires manual documentation)
