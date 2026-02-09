# Table: [dbo].[BaseContactSplit]

**Data Source:** Northwind
**Schema:** dbo
**Type:** Table

## Description

# **Table:** `[dbo].[BaseContactSplit]`
> Stores contact information for companies, including contact names, phone numbers, and contact types.
---
### **Columns:**
| Ord | Name | Data Type | Description |
|:---:|:---:|:---:|:---|
| 1 | `ID` | INTEGER | Primary key, Unique identifier for each contact record. |
| 2 | `CompanyName` | NVARCHAR(40) | Name of the company associated with the contact. |
| 3 | `ContactName` | NVARCHAR(30) | Full name of the contact person. |
| 4 | `Phone` | NVARCHAR(24) | Phone number for the contact. |
| 5 | `ContactType` | NVARCHAR(50) | Type or role of the contact (e.g., primary, billing, shipping). |
---

