# Schema Index-Based Search Feature

## Overview

This document describes the **skills-folder JSON indexes** (`.schema-index.json` / `.object-index.json`) used for admin listing, keyword object search, and markdown hydration. Generate-time retrieval uses the vector collection `schemas` (parent + column entities). See [VECTOR_SCHEMA.md](VECTOR_SCHEMA.md) and [DISCOVERY_STRATEGY_IMPLEMENTATION.md](DISCOVERY_STRATEGY_IMPLEMENTATION.md).

Schema discovery uses prebuilt index files so searches do not scan the filesystem. The indexes are loaded once, cached in memory, and reused for search, listing, lookups, and statistics.

## How It Works (End-to-End)

### 1) Index generation (offline step)

A script scans schema markdown files and creates two JSON index files:

- `.schema-index.json` in each data source folder
- `.object-index.json` in each schema folder

Metadata extraction rules:

- **Schema-level (per schema folder):** If `_schema.md` exists in the schema folder, the script reads it for purpose/domain and keywords. Use a `## Purpose` or `## Domain` section for the schema's functional area (e.g. "HR and Payroll", "Sales and orders"). Use a `## Keywords` section or a `**Keywords:**` line with comma-separated terms. If `_schema.md` is absent, the schema `description` defaults to "Contains N tables and M views" and `keywords` to `[]`.
- **Object-level (per table/view .md):** Schema name from **Schema:**, object type from **Type:** (Table, View, or Function), object name from the title line (fallback: filename), description from the first blockquote under the title, keywords derived from description and object name. For Functions, a `usage_example` field is also extracted from the `### Usage:` section.

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

### 4) Two-stage discovery and scoring

**Stage 1 – Schema relevance:** The query is normalized (lowercase, tokenize, remove stop words, drop length ≤ 2). Each schema in the cached indices is scored by schema name (+2.0), description (+1.0), and schema keywords (+1.5) per matching term. Schemas with score ≥ 1.0 are ranked and the **top 5** form the relevant set **S**. If the optional `domain` parameter is set, only schemas whose description or keywords match the domain terms are considered. If **S** is empty (no schema passes the threshold), the search falls back to all schemas.

**Stage 2 – Object search:** Object scoring runs only within the schemas in **S** (or all schemas when falling back). Each object is scored as before:

- Object name contains term: +3.0
- Keyword contains term: +2.0
- Description contains term: +1.0

If the object's schema is in **S**, its score is multiplied by a **schema match bonus** (default 1.5) so that objects in functionally relevant schemas outrank similar matches in other schemas.

Filters applied before/during search:

- `data_source` (optional)
- `object_type` (optional: Table, View, or Function)
- `domain` (optional: restrict to schemas matching this functional area)

Results are sorted by score (descending) and truncated to `top_k`.

### 5) Listing, lookup, and stats

- `list_all_objects`: reads objects from the cached object indexes, with optional filters.
- `get_object_by_name`: searches for an exact `object_name` match within schema and data source filters.
- `get_schema_statistics`:
  - When `data_source` is provided: returns that data source and its schema list.
  - When omitted: returns aggregated totals across all data sources.
  - When `query` is provided: also returns `recommended_schemas` (top 10 schemas by relevance to the query, with score).

## Index Files Structure

### 1) Schema Index (.schema-index.json)

Located in each data source folder. Schema-level `description` and `keywords` come from `_schema.md` in each schema folder when present.

```json
{
  "data_source": "Northwind",
  "total_schemas": 1,
  "schemas": [
    {
      "schema_name": "dbo",
      "description": "Sales, orders, product catalog, and customer data for the Northwind sample database.",
      "keywords": ["sales", "orders", "products", "customers", "employees", "suppliers", "shipping", "inventory", "categories"],
      "object_index_file": "schemas/dbo/.object-index.json",
      "total_objects": 38,
      "tables": 22,
      "views": 16,
      "functions": 5
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
  "functions": 5,
  "objects": [
    {
      "object_type": "Table",
      "schema_name": "dbo",
      "object_name": "Categories",
      "description": "Stores information about product categories...",
      "keywords": ["stores", "information", "product", "categories"],
      "file_name": "dbo.Categories.md"
    },
    {
      "object_type": "Function",
      "schema_name": "dbo",
      "object_name": "fn_CalculateTax",
      "description": "Calculates sales tax based on state code and amount.",
      "keywords": ["tax", "calculation", "finance"],
      "file_name": "dbo.fn.fn_CalculateTax.md",
      "usage_example": "SELECT [dbo].[fn_CalculateTax](@StateCode = 'NY', @Amount = 100.00)"
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
- `object_type` (optional: Table/View/Function)
- `top_k` (optional, default 10)
- `domain` (optional): restrict to schemas whose description or keywords match this functional area (e.g. "Sales", "HR")

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
GET /api/v1/admin/skills/statistics?query=sales
```

Query parameters:

- `data_source` (optional): filter by data source name
- `query` (optional): when provided, the response includes `recommended_schemas` (top 10 schemas by relevance to the query)

Response (when `data_source` is provided):

```json
{
  "data_source": "Northwind",
  "total_schemas": 1,
  "schemas": [
    {
      "schema_name": "dbo",
      "description": "Sales, orders, product catalog, and customer data...",
      "keywords": ["sales", "orders", "products", "customers", ...],
      "object_index_file": "schemas/dbo/.object-index.json",
      "total_objects": 38,
      "tables": 22,
      "views": 16,
      "functions": 5
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
  "total_functions": 5,
  "data_sources": [...]
}
```

Response (when `query` is provided; additional field):

```json
{
  ...,
  "recommended_schemas": [
    {
      "data_source": "Northwind",
      "schema_name": "dbo",
      "description": "Sales, orders, product catalog...",
      "keywords": ["sales", "orders", ...],
      "score": 2.5
    }
  ]
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
- Index loading and object indices are cached in memory after first use. The first call to `load_schema_indices()` builds the cache; clearing the cache (e.g. after regenerate-indices) resets it. Stage 1 iterates only schema entries from the cache (no object iteration).
- Schema purpose/domain and keywords are read from **`_schema.md`** in each schema folder when running `generate_schema_indices.py`. Regenerating indices is the source of truth for schema descriptions and keywords; a DB schema scan that writes `.schema-index.json` uses generic descriptions unless indices are regenerated afterward.

## Testing

```powershell
python scripts\test_index_search.py
```

Covers loading, scoring, listing, lookup, stats, schema-first prioritization (e.g. "sales" preferring Northwind dbo), recommended_schemas when statistics are called with a query, and fallback to global search when no schema passes the threshold.

## Best Practices for `_schema.md`

When authoring `_schema.md` files, explicitly mention available utility functions in the `## Purpose` or `## Domain` section. This helps the LLM discover functions during schema-level scoring.

Example:
> This schema contains HR data, including employee records, department assignments, and payroll history. It also provides utility functions for calculating employee tenure and retirement eligibility.

## Scoring Notes

- **Function boost**: Objects with `object_type: "Function"` receive a 1.2x scoring multiplier to improve discoverability, since users often search for actions (e.g., "calculate", "convert", "format").
- **Stop words**: Common verbs like "get" are preserved during query normalization (not stripped as stop words) to support matching function names like `fn_GetEmployeeSeniority`.

## Future Enhancements

1. Auto-regeneration on file changes
2. Full-text search
3. Faceted filtering
4. Fuzzy matching
5. Search analytics
