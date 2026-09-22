# Value Index Feature - Complete Implementation Guide

## Overview

The Value Index feature enables the AI Agent to accurately map user-provided natural language terms (e.g., "North America") to exact database values (e.g., "NA") and their corresponding locations (schema.table.column) using a pre-indexed Excel manifest.

This feature improves SQL generation accuracy by providing the LLM with verified, ground-truth data mappings during the query generation phase. Collection fields and `data_source_id` partitioning are defined in [VECTOR_SCHEMA.md](VECTOR_SCHEMA.md). Discovery uses a case-insensitive substring match on `plain_value`, then seeds parent tables into RRF (see [DISCOVERY_STRATEGY_IMPLEMENTATION.md](DISCOVERY_STRATEGY_IMPLEMENTATION.md)).

## Architecture

### Components

1. **Backend Services**
   - `admin_service.py` - Excel parsing, validation, and embedding
   - `vector_store.py` - Milvus operations for value ingestion and retrieval
   - `generation_service.py` - Integration of values into LLM prompts

2. **API Endpoints**
   - `POST /api/v1/admin/ingest-values` - Upload and process Excel files
   - `GET /api/v1/admin/values` - Retrieve all indexed values
   - `DELETE /api/v1/admin/values/{id}` - Delete specific values
   - `POST /api/v1/admin/values/clear` - Clear all values
   - `GET /api/v1/admin/values/template` - Download Excel template

3. **Frontend Components**
   - `ValueManager.tsx` - Admin UI for value management
   - `AdminLayout.tsx` - Navigation integration

### Data Flow

```
User Uploads Excel
    ↓
Backend Parses File (pandas)
    ↓
Values Embedded (OpenAI text-embedding-3-small)
    ↓
Stored in the `value_index` collection (partitioned by `data_source_id`)
    ↓
Query Received by Agent
    ↓
Value Lookup (case-insensitive substring on `plain_value`)
    ↓
Parent tables seeded into discovery + mappings injected into the prompt
    ↓
LLM Generates Better SQL
```

## Implementation Details

### 1. Backend Value Ingestion (`admin_service.py`)

#### `ingest_values_from_excel(file_content, mode)`

```python
def ingest_values_from_excel(file_content: bytes, mode: str = "append") -> Dict[str, Any]:
    """
    Parse Excel file and ingest values into the value index.
    
    Excel format required:
    - Column 1: value (the actual database value)
    - Column 2: schema_name (e.g., 'dbo')
    - Column 3: table_name (e.g., 'Customers')
    - Column 4: column_name (e.g., 'Country')
    - Column 5: metadata (optional, JSON-formatted)
    """
```

**Features:**
- Validates Excel structure
- Deduplicates rows
- Cleans whitespace from values
- Embeds values using OpenAI's text-embedding-3-small (1536 dimensions)
- Supports append or replace modes
- Returns detailed ingestion report

### 2. Vector Store Operations (`vector_store.py`)

New methods added to `MilvusVectorStore`:

#### `insert_value_item(value, schema_name, table_name, column_name, metadata)`
Inserts a single value with embedding into the Milvus value_index collection.

#### `search_values(query, top_k=5)`
Performs semantic similarity search to find relevant database values.

#### `get_all_values()`
Retrieves all indexed values with metadata.

#### `delete_value_item(item_id)`
Deletes a specific value by ID.

#### `clear_values_collection()`
Clears all values from the collection.

### 3. LLM Integration (`generation_service.py`)

#### `lookup_values_for_query(query, threshold=0.7)`

Performs semantic search on the value index to find relevant values for a query:

```python
def lookup_values_for_query(query: str, threshold: float = 0.7) -> Dict[str, List[str]]:
    """
    Look up relevant values in the value index based on the user query.
    
    Returns dictionary mapping schema.table.column to list of values
    """
```

#### Value Injection into Prompt

Values are injected into the LLM system prompt as verified data mappings:

```
### VERIFIED DATA MAPPINGS
The following values have been pre-verified as valid in the database:
- dbo.Territories.RegionDescription: 'Eastern', 'Western', 'Northern'
- dbo.Products.Category: 'Beverages', 'Condiments', 'Seafood'
```

This prevents the LLM from inventing values and ensures generated SQL uses exact database values.

### 4. API Endpoints (`app/api/endpoints/admin.py`)

#### Upload Values
```http
POST /api/v1/admin/ingest-values
Content-Type: multipart/form-data

Parameters:
- file: Excel file (.xlsx, .xls, .csv)
- mode: "append" or "replace" (default: "append")

Response:
{
  "status": "success",
  "message": "Successfully ingested 42 values",
  "rows_processed": 42,
  "total_rows": 50
}
```

#### Get All Values
```http
GET /api/v1/admin/values

Response:
[
  {
    "id": 1,
    "value": "North America",
    "schema_name": "dbo",
    "table_name": "Territories",
    "column_name": "RegionDescription"
  },
  ...
]
```

#### Delete Value
```http
DELETE /api/v1/admin/values/{id}
```

#### Clear All Values
```http
POST /api/v1/admin/values/clear
```

#### Download Template
```http
GET /api/v1/admin/values/template

Returns: Excel file with template structure
```

### 5. Frontend Value Manager (`ValueManager.tsx`)

The admin interface provides:

- **File Upload**: Drag-and-drop or click-to-upload Excel files
- **Upload Modes**: Append new values or replace all existing values
- **Progress Tracking**: Real-time upload progress indicator
- **Template Download**: Get a pre-formatted Excel template
- **Value Management**: View, search, and delete individual values
- **Batch Operations**: Clear all values at once
- **Status Feedback**: Success/error messages with details

## Usage Guide

### Step 1: Download Excel Template

1. Navigate to Admin Panel → Value Index
2. Click "Download Template" button
3. Template contains 5 columns:
   - `value`: Actual database value
   - `schema_name`: Database schema (e.g., 'dbo')
   - `table_name`: Table name (e.g., 'Customers')
   - `column_name`: Column name (e.g., 'Country')
   - `metadata`: Optional JSON (leave as '{}')

### Step 2: Populate Excel File

Example:
```
value                  | schema_name | table_name | column_name        | metadata
North America          | dbo         | Territories| RegionDescription  | {}
Eastern                | dbo         | Territories| RegionDescription  | {}
Beverages              | dbo         | Products   | Category           | {}
Condiments             | dbo         | Products   | Category           | {}
Enterprise             | dbo         | Accounts   | TierLevel          | {}
```

### Step 3: Upload File

1. Select "Append to existing values" or "Replace all values"
2. Click upload area or drag file
3. Wait for progress indicator to complete
4. View confirmation message

### Step 4: Verify Values

- Uploaded values appear in the table below
- Search by value name, table, or column
- Delete individual values if needed

## Example: Impact on SQL Generation

### Without Value Index
**User Query:** "Show me sales in North America"

LLM might generate:
```sql
SELECT * FROM dbo.Orders o
WHERE o.Territory = 'North America'  -- ERROR: Value doesn't exist!
```

### With Value Index
**LLM receives in prompt:**
```
### VERIFIED DATA MAPPINGS
- dbo.Territories.RegionDescription: 'NA', 'Eastern', 'Western'
```

LLM now generates:
```sql
SELECT o.OrderID, o.OrderDate
FROM dbo.Orders o
WHERE o.Territory IN ('NA')  -- Correct value!
```

## Configuration

### Milvus Collection Schema

The value_index collection stores:
- `id` (INT64, primary key, auto-increment)
- `embedding` (FLOAT_VECTOR, 1536 dimensions)
- `value` (VARCHAR, up to 256 chars)
- `schema_name` (VARCHAR, up to 128 chars)
- `table_name` (VARCHAR, up to 128 chars)
- `column_name` (VARCHAR, up to 128 chars)

### Similarity Threshold

Default threshold: 0.7 (on normalized scale)

Values with semantic similarity below this threshold are filtered out to prevent false matches.

## Performance Considerations

### Indexing Speed
- ~100-200 values per second (includes embedding generation)
- Batch upload of 1000 values: ~5-10 seconds

### Search Performance
- Semantic search: ~10-50ms per query
- Milvus L2 distance with IVF_FLAT index
- Top-k results: Usually 3-5 values per query

### Storage
- ~4KB per value in vector store
- 1000 values ≈ 4MB in Milvus

## Troubleshooting

### Issue: "File must be Excel (.xlsx/.xls) or CSV format"
**Solution:** Ensure file extension matches format (save as .xlsx in Excel)

### Issue: Excel file not recognized
**Solution:** Verify file has required 4-5 columns in correct order (value, schema_name, table_name, column_name, metadata)

### Issue: No values returned in search
**Solution:** 
- Check if values were successfully ingested (view in table)
- Verify semantic similarity of search terms
- Try uploading additional related values

### Issue: Values not appearing in LLM prompts
**Solution:**
- Ensure search similarity threshold is appropriate
- Check if query terms match indexed values semantically
- Try different phrasing in user query

## Future Enhancements

1. **Batch Value Operations**
   - Multi-file upload
   - Scheduled ingestion from database tables

2. **Value Statistics**
   - Frequency analysis
   - Unused value detection

3. **Semantic Grouping**
   - Automatically group similar values
   - Category-based filtering

4. **Smart Suggestions**
   - Auto-suggest values during query entry
   - Confidence scoring for suggestions

## API Integration Examples

### Python Client Example

```python
import requests

# Upload Excel file
with open('values.xlsx', 'rb') as f:
    files = {'file': f}
    data = {'mode': 'append'}
    response = requests.post(
        'http://localhost:8100/api/v1/admin/ingest-values',
        files=files,
        data=data
    )
    print(response.json())

# Get all values
response = requests.get('http://localhost:8100/api/v1/admin/values')
values = response.json()
print(f"Total values: {len(values)}")

# Delete specific value
requests.delete('http://localhost:8100/api/v1/admin/values/1')

# Clear all values
requests.post('http://localhost:8100/api/v1/admin/values/clear')
```

### JavaScript/TypeScript Example

```typescript
// Upload file
const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('mode', 'append');

const response = await fetch('/api/v1/admin/ingest-values', {
  method: 'POST',
  body: formData
});

const result = await response.json();
console.log(`Ingested ${result.rows_processed} values`);

// Get all values
const valuesResponse = await fetch('/api/v1/admin/values');
const values = await valuesResponse.json();

// Delete value
await fetch(`/api/v1/admin/values/${valueId}`, {
  method: 'DELETE'
});
```

## Testing

### Unit Tests

Test files to create:
- `test_value_ingestion.py` - Excel parsing and embedding
- `test_value_search.py` - Semantic search functionality
- `test_value_integration.py` - LLM prompt injection

### Integration Test

```python
def test_value_index_e2e():
    # 1. Upload values
    # 2. Verify ingestion
    # 3. Search for values
    # 4. Check LLM prompt inclusion
    # 5. Validate SQL generation uses correct values
```

## Database Compatibility

- ✅ Microsoft SQL Server
- ✅ PostgreSQL (with adjustments)
- ✅ MySQL (with adjustments)
- ✅ SQLite (with adjustments)

## Limitations

1. **Value Size**: Individual values limited to 256 characters
2. **Batch Size**: Excel files limited by available memory (typically 50,000+ rows)
3. **Semantic Accuracy**: Depends on embedding model quality
4. **Language Support**: Optimized for English (works with other languages)

## Dependencies

```
pandas==2.1.4
openpyxl==3.1.0
pymilvus==2.3.7
openai==1.61.0
```
