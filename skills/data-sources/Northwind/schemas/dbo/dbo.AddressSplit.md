# Table: [dbo].[AddressSplit]

**Data Source:** Auto-generated  
**Schema:** dbo  
**Type:** Table  

## Description

# **Table:** `[dbo].[AddressSplit]`
> Contains normalized address information with separate fields for address line, city, region, postal code, country, and contact type for entities such as customers, employees, or suppliers.
---
### **Columns:**
| Ord | Name | Data Type | Description |
|:---:|:---:|:---:|:---|
| 1 | `ID` | INTEGER | Primary key, Primary key identifier for the address record. |
| 2 | `Address` | NVARCHAR(60) | Street address or address line component of the location. |
| 3 | `City` | NVARCHAR(15) | City where the address is located. |
| 4 | `Region` | NVARCHAR(15) | Region, state, or province associated with the address. |
| 5 | `PostalCode` | NVARCHAR(50) | Postal or ZIP code for the address. |
| 6 | `Country` | NVARCHAR(15) | Country where the address is located. |
| 7 | `ContactType` | NVARCHAR(50) | Type of contact associated with the address, such as billing, shipping, or home. |
---
