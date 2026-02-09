# Table: [dbo].[Orders]

**Data Source:** Northwind
**Schema:** dbo
**Type:** Table

## Description

# **Table:** `[dbo].[Orders]`
> Stores information about customer orders, including order details, customer and employee associations, shipping information, and key dates.
---
### **Columns:**
| Ord | Name | Data Type | Description |
|:---:|:---:|:---:|:---|
| 1 | `OrderID` | INTEGER | Primary key, Primary key identifier for the order. |
| 2 | `CustomerID` | NCHAR(5) | Identifier of the customer who placed the order. Reference: Customers.CustomerID |
| 3 | `EmployeeID` | INTEGER | Identifier of the employee responsible for the order. Reference: Employees.EmployeeID |
| 4 | `OrderDate` | DATETIME | Date and time when the order was placed. |
| 5 | `RequiredDate` | DATETIME | Date by which the customer requires the order to be delivered. |
| 6 | `ShippedDate` | DATETIME | Date and time when the order was shipped. |
| 7 | `ShipVia` | INTEGER | Identifier of the shipping company used for the order. Reference: Shippers.ShipperID |
| 8 | `Freight` | MONEY | Shipping cost charged for the order. |
| 9 | `ShipName` | NVARCHAR(40) | Name of the recipient or entity to which the order is shipped. |
| 10 | `ShipAddress` | NVARCHAR(60) | Street address where the order is to be shipped. |
| 11 | `ShipCity` | NVARCHAR(15) | City of the shipping address. |
| 12 | `ShipRegion` | NVARCHAR(15) | Region or state of the shipping address. |
| 13 | `ShipPostalCode` | NVARCHAR(10) | Postal code of the shipping address. |
| 14 | `ShipCountry` | NVARCHAR(15) | Country of the shipping address. |
---

