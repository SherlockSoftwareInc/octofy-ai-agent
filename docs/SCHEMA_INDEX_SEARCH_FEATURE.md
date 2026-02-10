# Schema Index-Based Search Feature

## Overview

Schema discovery uses prebuilt index files so searches do not scan the filesystem. The indexes are loaded once, cached in memory, and reused for search, listing, lookups, and statistics.

## How It Works (End-to-End)

### 1) Index generation (offline step)

A script scans schema markdown files and creates two JSON index files:

- `.schema-index.json` in each data source folder
- `.object-index.json` in each schema folder

Metadata extraction rules:

- Schema name is read from the **Schema:** line in the markdown.
- Object type is read from the **Type:** line (Table or View).
- Object name is read from the title line (fallback: filename).
- Description is the first blockquote line under the title.
- Keywords are derived from the description plus object name parts, filtered and capped.

These indexes are written to disk and are the only inputs the search uses.

### 2) Index loading (runtime)

SkillsService loads all `.schema-index.json` files using a recursive search and caches them.
For a specific data source, it loads all `.object-index.json` files under that data source and caches them too.

### 3) Query normalization (search input)

The search query is normalized before scoring:

- Lowercased
- Split into terms with a word regex
- Stop words removed (e.g., "the", "and", "show", "list")
- Very short terms (length <= 2) removed

Only the remaining terms are used for scoring.

### 4) Scoring and filtering

Each indexed object is scored against the query terms:

- Object name contains term: +3.0
- Keyword contains term: +2.0
- Description contains term: +1.0

Filters are applied before scoring:

- `data_source` (optional)
- `object_type` (optional: Table or View)

Results are sorted by score (descending) and truncated to `top_k`.

### 5) Listing, lookup, and stats

- `list_all_objects`: reads objects from the cached object indexes, with optional filters.
- `get_object_by_name`: searches for an exact `object_name` match within schema and data source filters.
- `get_schema_statistics`:
  - When `data_source` is provided: returns that data source and its schema list.
  - When omitted: returns aggregated totals across all data sources.

## Index Files Structure

### 1) Schema Index (.schema-index.json)

Located in each data source folder:

```json
{
  "data_source": "Northwind",
  "total_schemas": 1,
  "schemas": [
    {
      "schema_name": "dbo",
      "description": "Contains 22 tables and 16 views",
      "object_index_file": "schemas/dbo/.object-index.json",
      "total_objects": 38,
      "tables": 22,
      "views": 16
    }
  ]
}
```

### 2) Object Index (.object-index.json)

Located in each schema folder:

```json
{
  "schema": "dbo",
  "total_objects": 38,
  "tables": 22,
  "views": 16,
  "objects": [
    {
      "object_type": "Table",
      "schema_name": "dbo",
      "object_name": "Categories",
      "description": "Stores information about product categories...",
      "keywords": ["stores", "information", "product", "categories"],
      "file_name": "dbo.Categories.md"
    }
  ]
}
```

## API Endpoints

All endpoints require `X-API-Key` and admin access.

### Search Objects

```http
GET /api/v1/admin/skills/search?query=customer&top_k=10
```

Query parameters:

- `query` (required)
- `data_source` (optional)
- `object_type` (optional: Table/View)
- `top_k` (optional, default 10)

Response:

```json
{
  "query": "customer",
  "total_results": 5,
  "results": [
    {
      "data_source": "Northwind",
      "schema_name": "dbo",
      "object_name": "Customers",
      "object_type": "Table",
      "description": "Stores detailed customer information...",
      "keywords": ["stores", "detailed", "customers"],
      "file_name": "dbo.Customers.md",
      "score": 8.0
    }
  ]
}
```

### List All Objects

```http
GET /api/v1/admin/skills/objects?data_source=Northwind&schema_name=dbo
```

Response:

```json
{
  "total_objects": 38,
  "objects": [...]
}
```

### Get Object by Name

```http
GET /api/v1/admin/skills/objects/by-name?object_name=Categories&schema_name=dbo
```

Response:

```json
{
  "data_source": "Northwind",
  "schema_name": "dbo",
  "object_name": "Categories",
  "object_type": "Table",
  "description": "...",
  "keywords": [...],
  "file_name": "dbo.Categories.md"
}
```

### Get Statistics

```http
GET /api/v1/admin/skills/statistics?data_source=Northwind
```

Response (when `data_source` is provided):

```json
{
  "data_source": "Northwind",
  "total_schemas": 1,
  "schemas": [
    {
      "schema_name": "dbo",
      "description": "Contains 22 tables and 16 views",
      "object_index_file": "schemas/dbo/.object-index.json",
      "total_objects": 38,
      "tables": 22,
      "views": 16
    }
  ]
}
```

Response (when `data_source` is omitted):

```json
{
  "total_data_sources": 1,
  "total_schemas": 1,
  "total_objects": 38,
  "total_tables": 22,
  "total_views": 16,
  "data_sources": [...]
}
```

### Regenerate Indices

```http
POST /api/v1/admin/skills/regenerate-indices
```

Regenerates all index files and clears the in-memory cache.

## Maintenance

### Regenerate index files

```powershell
python scripts\generate_schema_indices.py
```

Or via API:

```bash
curl -X POST http://localhost:8000/api/v1/admin/skills/regenerate-indices \
  -H "X-API-Key: your-api-key"
```

## Performance Benefits

| Operation | Without Index | With Index |
|-----------|---------------|------------|
| Search for "customer" | ~200ms (scan files) | ~5ms (read JSON) |
| List all objects | ~150ms (scan files) | ~3ms (read JSON) |
| Get object by name | ~50ms (scan files) | ~2ms (direct lookup) |
| Get statistics | ~100ms (scan/count) | ~1ms (pre-calculated) |

## Integration Notes

- The index-based methods are additive; existing SkillsService methods still work.
- Index loading and object indices are cached in memory after first use.

## Testing

```powershell
python scripts\test_index_search.py
```

Covers loading, scoring, listing, lookup, and stats.

## Future Enhancements

1. Auto-regeneration on file changes
2. Full-text search
3. Faceted filtering
4. Fuzzy matching
5. Search analytics
