# View: [dbo].[Quarterly Orders]

**Data Source:** Northwind
**Schema:** dbo
**Type:** View

## Description

# **View:** `[dbo].[Quarterly Orders]`
> View aggregating customer order information by quarter, providing a summary of customer locations and company details for quarterly reporting and analysis.
---
### **Columns:**
| Ord | Name | Data Type | Description |
|:---:|:---:|:---:|:---|
| 1 | `CustomerID` | NCHAR(5) | Unique identifier for the customer. Reference:Customers.CustomerID |
| 2 | `CompanyName` | NVARCHAR(40) | Legal name of the customer company or organization. |
| 3 | `City` | NVARCHAR(15) | City where the customer is located. |
| 4 | `Country` | NVARCHAR(15) | Country where the customer is located. |
---

