# Table: [dbo].[Contacts]

**Data Source:** Auto-generated  
**Schema:** dbo  
**Type:** Table  

## Description

# **Table:** `[dbo].[Contacts]`
> The table stores detailed contact information for individuals or organizations.
---
### **Columns:**
| Ord | Name | Data Type | Description |
|:---:|:---:|:---:|:---|
| 1 | `ContactID` | INTEGER | Primary key, Unique identifier for each contact record |
| 2 | `ContactType` | NVARCHAR(50) | Type of contact (e.g., Sales, Support, etc.) |
| 3 | `CompanyName` | NVARCHAR(40) | Name of the company associated with the contact |
| 4 | `ContactName` | NVARCHAR(30) | Full name of the contact person |
| 5 | `ContactTitle` | NVARCHAR(30) | Title or job title of the contact (e.g., Manager, Sales Representative) |
| 6 | `Address` | NVARCHAR(60) | Full address of the contact's location |
| 7 | `City` | NVARCHAR(15) | City where the contact is located |
| 8 | `Region` | NVARCHAR(15) | Region or state where the contact is located |
| 9 | `PostalCode` | NVARCHAR(10) | Postal or zip code for the contact |
| 10 | `Country` | NVARCHAR(15) | Country where the contact is located |
| 11 | `Phone` | NVARCHAR(24) | Primary phone number of the contact |
| 12 | `Extension` | NVARCHAR(4) | Extension number for the phone |
| 13 | `Fax` | NVARCHAR(24) | Fax number for the contact |
| 14 | `HomePage` | NTEXT | Website URL or homepage of the contact |
| 15 | `PhotoPath` | NVARCHAR(255) | File path to the contact's photo |
| 16 | `Photo` | IMAGE | Binary data or image of the contact's photo |
---
