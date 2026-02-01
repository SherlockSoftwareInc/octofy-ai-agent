# Skills Tree CRUD API Documentation

This document provides complete API reference for managing the Skills tree structure: Data Sources, Data Groups, and Data Objects (Tables).

---

## Base URL

```
http://localhost:8000/api/v1/admin/skills
```

## Authentication

All endpoints require API key authentication via query parameter:

```
?api_key=your_api_key_here
```

---

## 📋 Data Sources

### List All Data Sources

**Endpoint:** `GET /admin/skills/data-sources`

**Description:** Retrieves all data sources from the `_index.md` file.

**Response:**
```json
[
  {
    "name": "Northwind",
    "type": "SQL Server",
    "description": "Database schema: dbo. Contains 39 tables...",
    "keywords": ["dbo", "database", "sql"],
    "status": "Active",
    "file_path": "skills/data-sources/Northwind/_data-source.md"
  }
]
```

---

### Create Data Source

**Endpoint:** `POST /admin/skills/data-sources`

**Description:** Creates a new data source with directory structure.

**Request Body:**
```json
{
  "name": "AdventureWorks",
  "type": "SQL Server",
  "description": "Adventure Works database with sales, HR, and production data",
  "keywords": ["sales", "products", "employees", "customers"],
  "status": "Active"
}
```

**What It Creates:**
```
skills/data-sources/
└── adventureworks/
    ├── _data-source.md       # Data source metadata
    ├── data-groups/          # Empty directory for groups
    └── schemas/              # Empty directory for table schemas
```

**Response:**
```json
{
  "status": "success",
  "message": "Created data source: AdventureWorks",
  "data": {
    "name": "AdventureWorks",
    "type": "SQL Server",
    "status": "Active",
    "description": "Adventure Works database with sales, HR, and production data",
    "keywords": ["sales", "products", "employees", "customers"],
    "file_path": "skills/data-sources/adventureworks/_data-source.md"
  }
}
```

---

### Update Data Source

**Endpoint:** `PUT /admin/skills/data-sources/{data_source_name}`

**Description:** Updates an existing data source's metadata.

**Example:** `PUT /admin/skills/data-sources/Northwind`

**Request Body:** (all fields optional)
```json
{
  "name": "Northwind Updated",
  "type": "SQL Server",
  "description": "Updated description",
  "keywords": ["updated", "keywords"],
  "status": "Active"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Updated data source: Northwind",
  "data": {
    "name": "Northwind Updated",
    "file_path": "skills/data-sources/northwind/_data-source.md"
  }
}
```

---

### Delete Data Source

**Endpoint:** `DELETE /admin/skills/data-sources/{data_source_name}`

**Description:** Deletes a data source and all its contents (data groups, schemas).

**Example:** `DELETE /admin/skills/data-sources/Northwind`

**⚠️ Warning:** This is a destructive operation that removes:
- `_data-source.md`
- All data groups in `data-groups/`
- All table schemas in `schemas/`
- The entire data source directory

**Response:**
```json
{
  "status": "success",
  "message": "Deleted data source: Northwind"
}
```

---

## 📦 Data Groups

### List Data Groups

**Endpoint:** `GET /admin/skills/data-groups`

**Query Parameters:**
- `data_source` (optional): Filter by data source name

**Examples:**
```
GET /admin/skills/data-groups
GET /admin/skills/data-groups?data_source=Northwind
```

**Response:**
```json
[
  {
    "name": "Customers",
    "data_source": "Dbo Database",
    "description": "This data group was auto-generated from Milvus schema_index.",
    "keywords": ["customers", "address", "city", "country"],
    "tables": ["../schemas/dbo/dbo.Customers.md"],
    "category": "Auto-generated",
    "file_path": "skills/data-sources/Northwind/data-groups/_customers-group.md"
  }
]
```

---

### Create Data Group

**Endpoint:** `POST /admin/skills/data-groups`

**Description:** Creates a new data group file.

**Request Body:**
```json
{
  "name": "Sales Analytics",
  "data_source": "Northwind",
  "description": "Tables related to sales analysis and reporting",
  "keywords": ["sales", "revenue", "orders", "analytics"],
  "category": "User-defined",
  "tables": [
    "skills/data-sources/Northwind/schemas/dbo/dbo.Orders.md",
    "skills/data-sources/Northwind/schemas/dbo/dbo.OrderDetails.md"
  ]
}
```

**What It Creates:**
```
skills/data-sources/Northwind/data-groups/_sales-analytics-group.md
```

**Response:**
```json
{
  "status": "success",
  "message": "Created data group: Sales Analytics",
  "data": {
    "name": "Sales Analytics",
    "data_source": "Northwind",
    "description": "Tables related to sales analysis and reporting",
    "keywords": ["sales", "revenue", "orders", "analytics"],
    "category": "User-defined",
    "tables": [...],
    "file_path": "skills/data-sources/Northwind/data-groups/_sales-analytics-group.md"
  }
}
```

---

### Update Data Group

**Endpoint:** `PUT /admin/skills/data-groups`

**Description:** Updates an existing data group.

**Request Body:** (must include `file_path`, other fields optional)
```json
{
  "file_path": "skills/data-sources/Northwind/data-groups/_customers-group.md",
  "name": "Customer Management",
  "description": "Updated description",
  "keywords": ["customers", "crm", "contacts"],
  "category": "Core Business",
  "tables": [
    "skills/data-sources/Northwind/schemas/dbo/dbo.Customers.md",
    "skills/data-sources/Northwind/schemas/dbo/dbo.CustomerDemographics.md"
  ]
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Updated data group: Customer Management",
  "data": {
    "file_path": "skills/data-sources/Northwind/data-groups/_customers-group.md",
    "updated": true
  }
}
```

---

### Delete Data Group

**Endpoint:** `DELETE /admin/skills/data-groups`

**Query Parameters:**
- `file_path` (required): Path to the data group file

**Example:**
```
DELETE /admin/skills/data-groups?file_path=skills/data-sources/Northwind/data-groups/_customers-group.md
```

**Response:**
```json
{
  "status": "success",
  "message": "Deleted data group"
}
```

---

## 📊 Data Objects (Tables)

### List Tables

**Endpoint:** `GET /admin/skills/tables`

**Query Parameters:**
- `data_source` (optional): Filter by data source name
- `data_group` (optional): Filter by data group name

**Examples:**
```
GET /admin/skills/tables
GET /admin/skills/tables?data_source=Northwind
GET /admin/skills/tables?data_source=Northwind&data_group=Customers
```

**Response:**
```json
[
  {
    "table_name": "Customers",
    "schema_name": "dbo",
    "data_source": "Auto-generated",
    "description": "# **Table:** `[dbo].[Customers]`...",
    "columns": [...],
    "file_path": "skills/data-sources/Northwind/schemas/dbo/dbo.Customers.md"
  }
]
```

---

### Get Table By Path

**Endpoint:** `GET /admin/skills/tables/by-path`

**Query Parameters:**
- `file_path` (required): Path to the table schema file

**Example:**
```
GET /admin/skills/tables/by-path?file_path=skills/data-sources/Northwind/schemas/dbo/dbo.Customers.md
```

**Response:**
```json
{
  "table_name": "Customers",
  "schema_name": "dbo",
  "data_source": "Auto-generated",
  "description": "# **Table:** `[dbo].[Customers]`...",
  "columns": [...]
}
```

---

### Create Table (Data Object)

**Endpoint:** `POST /admin/skills/tables`

**Description:** Creates a new table schema file.

**Request Body:**
```json
{
  "data_source": "Northwind",
  "schema_name": "dbo",
  "table_name": "Promotions",
  "description": "Marketing promotions and campaigns",
  "table_type": "Table",
  "record_count": "Unknown",
  "columns": [
    {
      "name": "PromotionID",
      "type": "INT",
      "description": "Primary key, unique promotion identifier"
    },
    {
      "name": "PromotionName",
      "type": "NVARCHAR(100)",
      "description": "Name of the promotion"
    },
    {
      "name": "StartDate",
      "type": "DATETIME",
      "description": "Promotion start date"
    },
    {
      "name": "EndDate",
      "type": "DATETIME",
      "description": "Promotion end date"
    }
  ]
}
```

**What It Creates:**
```
skills/data-sources/Northwind/schemas/dbo/dbo.Promotions.md
```

**Response:**
```json
{
  "status": "success",
  "message": "Created table: dbo.Promotions",
  "data": {
    "data_source": "Northwind",
    "schema_name": "dbo",
    "table_name": "Promotions",
    "description": "Marketing promotions and campaigns",
    "file_path": "skills/data-sources/Northwind/schemas/dbo/dbo.Promotions.md"
  }
}
```

---

### Update Table

**Endpoint:** `PUT /admin/skills/tables`

**Description:** Updates an existing table schema's description.

**Request Body:** (must include `file_path`)
```json
{
  "file_path": "skills/data-sources/Northwind/schemas/dbo/dbo.Customers.md",
  "description": "Updated table description with more details..."
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Updated table: Customers",
  "data": {
    "file_path": "skills/data-sources/Northwind/schemas/dbo/dbo.Customers.md",
    "updated": true
  }
}
```

---

### Delete Table

**Endpoint:** `DELETE /admin/skills/tables`

**Query Parameters:**
- `file_path` (required): Path to the table schema file

**Example:**
```
DELETE /admin/skills/tables?file_path=skills/data-sources/Northwind/schemas/dbo/dbo.Promotions.md
```

**⚠️ Warning:** This removes the table schema file but does NOT:
- Remove references from data groups
- Delete the physical database table
- Update the `_data-source.md` file

**Response:**
```json
{
  "status": "success",
  "message": "Deleted table schema"
}
```

---

## 📁 File Structure After Creation

After using all CRUD operations, your Skills tree will look like:

```
skills/data-sources/
├── _index.md                                   # Updated automatically
├── Northwind/
│   ├── _data-source.md                         # Created via POST /data-sources
│   ├── data-groups/
│   │   ├── _customers-group.md                 # Created via POST /data-groups
│   │   ├── _sales-analytics-group.md           # Created via POST /data-groups
│   │   └── ...
│   └── schemas/
│       └── dbo/
│           ├── dbo.Customers.md                # Created via POST /tables
│           ├── dbo.Orders.md                   # Created via POST /tables
│           ├── dbo.Promotions.md               # Created via POST /tables
│           └── ...
└── AdventureWorks/
    ├── _data-source.md                         # Created via POST /data-sources
    ├── data-groups/
    └── schemas/
```

---

## 🔄 Typical Workflow

### 1. Create a New Data Source

```bash
curl -X POST "http://localhost:8000/api/v1/admin/skills/data-sources?api_key=YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "AdventureWorks",
    "type": "SQL Server",
    "description": "Sales and HR database",
    "keywords": ["sales", "employees"],
    "status": "Active"
  }'
```

### 2. Add Table Schemas

```bash
curl -X POST "http://localhost:8000/api/v1/admin/skills/tables?api_key=YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "data_source": "AdventureWorks",
    "schema_name": "Sales",
    "table_name": "SalesOrders",
    "description": "Sales order transactions",
    "columns": [
      {"name": "OrderID", "type": "INT", "description": "Primary key"},
      {"name": "CustomerID", "type": "INT", "description": "Foreign key to Customers"}
    ]
  }'
```

### 3. Create Data Groups

```bash
curl -X POST "http://localhost:8000/api/v1/admin/skills/data-groups?api_key=YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Sales Data",
    "data_source": "AdventureWorks",
    "description": "Sales-related tables",
    "keywords": ["sales", "orders", "revenue"],
    "category": "Core Business",
    "tables": ["skills/data-sources/AdventureWorks/schemas/Sales/Sales.SalesOrders.md"]
  }'
```

### 4. Update Metadata as Needed

```bash
curl -X PUT "http://localhost:8000/api/v1/admin/skills/data-groups?api_key=YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "skills/data-sources/AdventureWorks/data-groups/_sales-data-group.md",
    "keywords": ["sales", "orders", "revenue", "customers", "products"]
  }'
```

---

## 🛠️ Error Handling

All endpoints return consistent error responses:

**Success Response:**
```json
{
  "status": "success",
  "message": "Operation completed",
  "data": {...}
}
```

**Error Response:**
```json
{
  "detail": "Error message describing what went wrong"
}
```

**Common HTTP Status Codes:**
- `200` - Success
- `404` - Resource not found
- `500` - Server error (validation failed, file not found, etc.)

---

## 📝 Notes

1. **Slugification**: Names are converted to filesystem-safe slugs (lowercase, hyphens instead of spaces).
   - "Sales Analytics" → `_sales-analytics-group.md`
   - "AdventureWorks" → `adventureworks/`

2. **File Paths**: Always use absolute paths from project root when updating/deleting:
   - ✅ `skills/data-sources/Northwind/schemas/dbo/dbo.Customers.md`
   - ❌ `../schemas/dbo/dbo.Customers.md`

3. **Index Management**: The `_index.md` file is automatically updated when creating/updating/deleting data sources.

4. **Relative Links**: Data groups use relative paths to reference tables:
   - From: `data-groups/_customers-group.md`
   - To: `../schemas/dbo/dbo.Customers.md`

5. **Cache Clearing**: GET endpoints automatically clear caches to ensure fresh data.

---

## 🧪 Testing Endpoints

You can test all endpoints using the provided curl commands or tools like:
- Postman
- Insomnia
- HTTPie
- Browser (for GET requests)

**Example using Python:**

```python
import requests

BASE_URL = "http://localhost:8000/api/v1/admin/skills"
API_KEY = "your_api_key_here"

# Create data source
response = requests.post(
    f"{BASE_URL}/data-sources",
    params={"api_key": API_KEY},
    json={
        "name": "TestDB",
        "type": "SQL Server",
        "description": "Test database",
        "keywords": ["test"],
        "status": "Active"
    }
)
print(response.json())
```

---

## 📚 Related Documentation

- [CONTEXT.md](CONTEXT.md) - Project overview
- [BACKEND_API.md](BACKEND_API.md) - Complete backend API reference
- [Skills Migration Script](scripts/migrate_milvus_to_skills.py) - Auto-generation tool
