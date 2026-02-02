# Excel Upload Feature - Quick Reference

## What's New

Added **Excel file upload** to two admin pages:
- **Schema Management**: Bulk import table descriptions
- **Few-Shot Examples**: Bulk import Q&A training data

## How to Use

### Schema Management Upload

1. Go to **Admin** → **Schema Management**
2. Create Excel file with 3 columns:
   ```
   schema_name  | table_name  | description
   dbo          | Customers   | Customer contact and order information
   dbo          | Orders      | Sales orders and transaction details
   dbo          | Products    | Product catalog and inventory
   ```
3. Choose **Append** or **Replace** mode
4. Upload the file
5. Watch progress bar fill
6. See success message with row count

### Few-Shot Examples Upload

1. Go to **Admin** → **Few-Shot Examples**
2. Create Excel file with 2 columns:
   ```
   question                         | sql_query
   Show customers from USA          | SELECT * FROM dbo.Customers WHERE Country='USA'
   Top 5 best-selling products      | SELECT TOP 5 ProductName FROM dbo.Products ORDER BY Sales DESC
   Count orders by customer         | SELECT CustomerID, COUNT(*) FROM dbo.Orders GROUP BY CustomerID
   ```
3. Choose **Append** or **Replace** mode
4. Upload the file
5. Watch progress bar fill
6. See success message with row count

## Key Features

✅ **Excel Only** - No CSV files (unlike Value Index)  
✅ **Progress Tracking** - Real-time percentage display  
✅ **Two Modes** - Append new data or replace everything  
✅ **Auto-Cleaning** - Removes duplicates and trims whitespace  
✅ **Error Messages** - Clear feedback on what went wrong  
✅ **Format Guide** - Built-in help showing required columns  

## Validation Rules

### Schemas
- All 3 columns required: `schema_name`, `table_name`, `description`
- No empty cells allowed
- Case-insensitive column matching
- Duplicates removed automatically

### Few-Shots  
- Both columns required: `question`, `sql_query`
- No empty cells allowed
- Case-insensitive column matching
- Duplicates removed automatically (by question)

## Upload Modes

| Mode | Behavior |
|------|----------|
| **Append** | Adds new rows without removing existing data |
| **Replace** | Clears everything first, then loads new data |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "File must be Excel format" | Ensure .xlsx or .xls extension |
| "File must contain columns..." | Check column names match exactly |
| Upload doesn't start | Try refreshing page |
| Data doesn't appear | Refresh page after upload completes |
| Accidentally replaced data | You can re-upload with backup file |

## File Size Limits

- No hard limits enforced
- Tested with typical admin workloads (< 1000 rows)
- Very large files (10000+ rows) may take time to process

## Related Features

- **Value Index**: Upload values for database lookups (supports Excel + CSV)
- **Schema Sync**: Auto-discover tables from database
- **Manual Entry**: Add examples one-at-a-time via UI

## API Endpoints

**Upload Schemas:**
```
POST /api/v1/admin/ingest-schemas
Content-Type: multipart/form-data
Parameters: file, mode
```

**Upload Few-Shots:**
```
POST /api/v1/admin/ingest-fewshots
Content-Type: multipart/form-data
Parameters: file, mode
```

**Progress Tracking:**
```
GET /api/v1/admin/ingest-progress (Server-Sent Events)
```

## Implementation Files

Backend:
- `app/services/admin_service.py` - Parse & validate Excel files
- `app/api/endpoints/admin.py` - API endpoints

Frontend:
- `frontend/src/api/client.ts` - API client methods
- `frontend/src/pages/Admin/SchemaManager.tsx` - Upload UI
- `frontend/src/pages/Admin/FewShotManager.tsx` - Upload UI
