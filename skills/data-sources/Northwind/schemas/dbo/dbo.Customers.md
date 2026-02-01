# Table: [dbo].[Customers]

**Data Source:** Auto-generated  
**Schema:** dbo  
**Type:** Table  

## Description

# **Table:** `[dbo].[Customers]`
> Stores detailed information about customers, including company details, contact information, and address data.
---
### **Columns:**
| Ord | Name | Data Type | Description |
|:---:|:---:|:---:|:---|
| 1 | `CustomerID` | NCHAR(5) | Primary key, Unique identifier for each customer record. |
| 2 | `CompanyName` | NVARCHAR(40) | Name of the company associated with the customer. |
| 3 | `ContactName` | NVARCHAR(30) | Full name of the primary contact person for the customer. |
| 4 | `ContactTitle` | NVARCHAR(30) | Job title or position of the customer's primary contact. |
| 5 | `Address` | NVARCHAR(60) | Street address of the customer's location. |
| 6 | `City` | NVARCHAR(15) | City where the customer is located. |
| 7 | `Region` | NVARCHAR(15) | Region, state, or province where the customer is located. |
| 8 | `PostalCode` | NVARCHAR(10) | Postal or ZIP code for the customer's address. |
| 9 | `Country` | NVARCHAR(15) | Country where the customer is located. |
| 10 | `Phone` | NVARCHAR(24) | Primary phone number for the customer. |
| 11 | `Fax` | NVARCHAR(24) | Fax number for the customer. |
---
