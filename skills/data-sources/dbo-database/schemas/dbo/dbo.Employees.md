# Table: [dbo].[Employees]

**Data Source:** Auto-generated  
**Schema:** dbo  
**Type:** Table  
**Era:** Unknown  
**Record Count:** Unknown  
**Update Frequency:** Unknown

## Description

# **Table:** `[dbo].[Employees]`
> This table is used to store employee details for human resources, payroll, HR management, or organizational development purposes.
---
### **Columns:**
| Ord | Name | Data Type | Description |
|:---:|:---:|:---:|:---|
| 1 | `EmployeeID` | INTEGER | Primary key, Unique identifier for each employee record |
| 2 | `LastName` | NVARCHAR(20) | Last name of the employee |
| 3 | `FirstName` | NVARCHAR(10) | First name of the employee |
| 4 | `Title` | NVARCHAR(30) | Job title or role of the employee (e.g., Manager, Engineer, Sales Rep) |
| 5 | `TitleOfCourtesy` | NVARCHAR(25) | Formal title or honorific used before the employee's name (e.g., Mr., Ms., Dr.) |
| 6 | `BirthDate` | DATETIME | Date of birth of the employee |
| 7 | `HireDate` | DATETIME | Date when the employee started working |
| 8 | `Address` | NVARCHAR(60) | Full address of the employee's residence or office |
| 9 | `City` | NVARCHAR(15) | City where the employee is located |
| 10 | `Region` | NVARCHAR(15) | Region or state where the employee is located |
| 11 | `PostalCode` | NVARCHAR(10) | Postal or zip code for the employee |
| 12 | `Country` | NVARCHAR(15) | Country where the employee is located |
| 13 | `HomePhone` | NVARCHAR(24) | Primary home phone number of the employee |
| 14 | `Extension` | NVARCHAR(4) | Extension number for the home phone |
| 15 | `Photo` | IMAGE | Binary data or image of the employee's photo |
| 16 | `Notes` | NTEXT | Additional notes or information about the employee |
| 17 | `ReportsTo` | INTEGER | ID of the employee who reports to this employee (e.g., manager), Reference: [dbo].[Employees].[EmployeeID] |
| 18 | `PhotoPath` | NVARCHAR(255) | File path to the employee's photo |
---


## Columns

## Common Queries

(Requires manual documentation)

## Related Tables

(Requires manual documentation)

## Data Quality Notes

(Requires manual documentation)
