# Skills Tree CRUD - Quick Reference

> Quick command reference for managing Data Sources, Data Groups, and Data Objects

---

## 🚀 Quick Start

### Base URL
```
http://localhost:8000/api/v1/admin/skills
```

### Authentication
Add `?api_key=YOUR_KEY` to all requests

---

## 📋 Data Sources

| Action | Method | Endpoint |
|--------|--------|----------|
| **List all** | GET | `/data-sources` |
| **Create** | POST | `/data-sources` |
| **Update** | PUT | `/data-sources/{name}` |
| **Delete** | DELETE | `/data-sources/{name}` |

### Create Example
```json
POST /data-sources
{
  "name": "AdventureWorks",
  "type": "SQL Server",
  "description": "Sales and HR database",
  "keywords": ["sales", "employees"],
  "status": "Active"
}
```

---

## 📦 Data Groups

| Action | Method | Endpoint |
|--------|--------|----------|
| **List all** | GET | `/data-groups` |
| **List filtered** | GET | `/data-groups?data_source=Northwind` |
| **Create** | POST | `/data-groups` |
| **Update** | PUT | `/data-groups` |
| **Delete** | DELETE | `/data-groups?file_path=...` |

### Create Example
```json
POST /data-groups
{
  "name": "Sales Analytics",
  "data_source": "Northwind",
  "description": "Sales analysis tables",
  "keywords": ["sales", "revenue", "orders"],
  "category": "Core Business",
  "tables": [
    "skills/data-sources/Northwind/schemas/dbo/dbo.Orders.md"
  ]
}
```

---

## 📊 Data Objects (Tables)

| Action | Method | Endpoint |
|--------|--------|----------|
| **List all** | GET | `/tables` |
| **List filtered** | GET | `/tables?data_source=Northwind` |
| **Get by path** | GET | `/tables/by-path?file_path=...` |
| **Create** | POST | `/tables` |
| **Update** | PUT | `/tables` |
| **Delete** | DELETE | `/tables?file_path=...` |

### Create Example
```json
POST /tables
{
  "data_source": "Northwind",
  "schema_name": "dbo",
  "table_name": "Promotions",
  "description": "Marketing promotions",
  "table_type": "Table",
  "record_count": "Unknown",
  "columns": [
    {
      "name": "PromotionID",
      "type": "INT",
      "description": "Primary key"
    },
    {
      "name": "PromotionName",
      "type": "NVARCHAR(100)",
      "description": "Promotion name"
    }
  ]
}
```

---

## 🔄 Typical Workflow

```bash
# 1. Create Data Source
curl -X POST "http://localhost:8000/api/v1/admin/skills/data-sources?api_key=YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "MyDB", "type": "SQL Server", "description": "My database", "keywords": ["db"], "status": "Active"}'

# 2. Create Tables
curl -X POST "http://localhost:8000/api/v1/admin/skills/tables?api_key=YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"data_source": "MyDB", "schema_name": "dbo", "table_name": "Users", "description": "User accounts"}'

# 3. Create Data Group
curl -X POST "http://localhost:8000/api/v1/admin/skills/data-groups?api_key=YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "User Management", "data_source": "MyDB", "description": "User tables", "keywords": ["users"], "tables": ["skills/data-sources/mydb/schemas/dbo/dbo.Users.md"]}'
```

---

## 📁 File Structure Created

```
skills/data-sources/
├── _index.md                          # Auto-updated
└── MyDB/
    ├── _data-source.md                # POST /data-sources
    ├── data-groups/
    │   └── _user-management-group.md  # POST /data-groups
    └── schemas/
        └── dbo/
            └── dbo.Users.md           # POST /tables
```

---

## 🛠️ Python Example

```python
import requests

BASE = "http://localhost:8000/api/v1/admin/skills"
KEY = "your_api_key"

# Create data source
requests.post(f"{BASE}/data-sources", params={"api_key": KEY}, json={
    "name": "TestDB",
    "type": "SQL Server",
    "description": "Test",
    "keywords": ["test"],
    "status": "Active"
})

# Create table
requests.post(f"{BASE}/tables", params={"api_key": KEY}, json={
    "data_source": "TestDB",
    "schema_name": "dbo",
    "table_name": "Products",
    "description": "Product catalog"
})

# Create group
requests.post(f"{BASE}/data-groups", params={"api_key": KEY}, json={
    "name": "Catalog",
    "data_source": "TestDB",
    "description": "Product catalog tables",
    "keywords": ["products", "catalog"],
    "tables": ["skills/data-sources/testdb/schemas/dbo/dbo.Products.md"]
})
```

---

## 📝 Key Notes

1. **Names are slugified**: "My Database" → `my-database/`
2. **Use absolute paths** for file_path parameters
3. **Keywords are important** - used for semantic search
4. **Create order**: Data Source → Tables → Data Groups
5. **Deletion is destructive** - no undo!

---

## 📚 Full Documentation

See [SKILLS_CRUD_API.md](SKILLS_CRUD_API.md) for complete API reference.
