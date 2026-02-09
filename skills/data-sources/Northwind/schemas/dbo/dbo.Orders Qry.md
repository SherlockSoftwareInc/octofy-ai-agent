# View: [dbo].[Orders Qry]

**Data Source:** Northwind
**Schema:** dbo
**Type:** View

## Description

# **View:** `[dbo].[Orders Qry]`
> A query view that combines order information with customer details, providing a comprehensive view of sales transactions including shipping and customer location data.
---
### **Columns:**
| Ord | Name | Data Type | Description |
|:---:|:---:|:---:|:---|
| 1 | `OrderID` | INTEGER | Unique identifier for each order. Primary key for order records. |
| 2 | `CustomerID` | NCHAR(5) | Identifier of the customer who placed the order. Reference:Customers.CustomerID |
| 3 | `EmployeeID` | INTEGER | Identifier of the employee who processed the order. Reference:Employees.EmployeeID |
| 4 | `OrderDate` | DATETIME | Date and time when the order was placed by the customer. |
| 5 | `RequiredDate` | DATETIME | Date by which the order must be shipped to meet customer requirements. |
| 6 | `ShippedDate` | DATETIME | Date when the order was actually shipped to the customer. Null if not yet shipped. |
| 7 | `ShipVia` | INTEGER | Identifier of the shipping company used for delivery. Reference:Shippers.ShipperID |
| 8 | `Freight` | MONEY | Shipping cost charged to the customer for order delivery. |
| 9 | `ShipName` | NVARCHAR(40) | Name of the recipient for shipping purposes, which may differ from customer name. |
| 10 | `ShipAddress` | NVARCHAR(60) | Street address for order delivery. |
| 11 | `ShipCity` | NVARCHAR(15) | City for order delivery. |
| 12 | `ShipRegion` | NVARCHAR(15) | Region or state for order delivery. |
| 13 | `ShipPostalCode` | NVARCHAR(10) | Postal or ZIP code for order delivery. |
| 14 | `ShipCountry` | NVARCHAR(15) | Country for order delivery. |
| 15 | `CompanyName` | NVARCHAR(40) | Official business name of the customer who placed the order. |
| 16 | `Address` | NVARCHAR(60) | Primary business address of the customer. |
| 17 | `City` | NVARCHAR(15) | City of the customer's primary business location. |
| 18 | `Region` | NVARCHAR(15) | Region or state of the customer's primary business location. |
| 19 | `PostalCode` | NVARCHAR(10) | Postal or ZIP code of the customer's primary business location. |
| 20 | `Country` | NVARCHAR(15) | Country of the customer's primary business location. |
---

