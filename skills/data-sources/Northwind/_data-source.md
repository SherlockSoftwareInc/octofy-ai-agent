# Northwind Database

**Type:** SQL Server  
**Server:** localhost
**Database:** northwind

**Friendly Name:** Northwind Database  
**Keywords:** sales, customers, orders, products, employees, shipping

## Description

Sales database for imported and exported specialty foods. This database contains comprehensive information about customer orders, product inventory, employee management, and international shipping operations.

## Data Coverage

- **Time Range:** Unknown (requires manual update)
- **Update Frequency:** Unknown (requires manual update)

## Schema Notes

- Specific time ranges
- Update frequency
- Cross-schema references
- Access restrictions

## Connection Method

```python
# SQL Server connection via pyodbc
# See app settings for connection string
```

## Physical Schemas

All table schemas are stored in the `schemas/` directory, organized by database schema:

- **schemas/dbo/** - Dbo schema tables
