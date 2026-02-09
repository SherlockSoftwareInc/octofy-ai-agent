# Table: [dbo].[Suppliers]

**Data Source:** Northwind
**Schema:** dbo
**Type:** Table

## Description

# **Table:** `[dbo].[Suppliers]`
> Contains detailed information about companies that supply products, including company details, contact information, and address data.
---
### **Columns:**
| Ord | Name | Data Type | Description |
|:---:|:---:|:---:|:---|
| 1 | `SupplierID` | INTEGER | Primary key, Unique identifier for each supplier. Serves as the primary key for the table. |
| 2 | `CompanyName` | NVARCHAR(40) | Name of the supplier company. |
| 3 | `ContactName` | NVARCHAR(30) | Full name of the primary contact person at the supplier. |
| 4 | `ContactTitle` | NVARCHAR(30) | Job title or position of the primary contact person at the supplier. |
| 5 | `Address` | NVARCHAR(60) | Street address of the supplier's main office or location. |
| 6 | `City` | NVARCHAR(15) | City where the supplier's office or facility is located. |
| 7 | `Region` | NVARCHAR(15) | Region, state, or province where the supplier is located. |
| 8 | `PostalCode` | NVARCHAR(10) | Postal or ZIP code for the supplier's address. |
| 9 | `Country` | NVARCHAR(15) | Country where the supplier is based. |
| 10 | `Phone` | NVARCHAR(24) | Primary phone number for contacting the supplier. |
| 11 | `Fax` | NVARCHAR(24) | Fax number for the supplier. |
| 12 | `HomePage` | NTEXT | Web page URL or additional descriptive information about the supplier. |
---

