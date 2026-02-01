# Table: [dbo].[CustomerCustomerDemo]

**Data Source:** Auto-generated  
**Schema:** dbo  
**Type:** Table  

## Description

# **Table:** `[dbo].[CustomerCustomerDemo]`
> Associative table linking customers to their customer demographic types.
---
### **Columns:**
| Ord | Name | Data Type | Description |
|:---:|:---:|:---:|:---|
| 1 | `CustomerID` | NCHAR(5) | Primary key, Unique identifier of the customer. Reference: Customers.CustomerID |
| 2 | `CustomerTypeID` | NCHAR(10) | Primary key, Identifier for the customer demographic type. Reference: CustomerDemographics.CustomerTypeID |
---
