# Excel Upload Feature for Admin Pages

## Overview
Added Excel file upload functionality to the **Schema Management** and **Few-Shot Examples** admin pages, allowing users to bulk-import data from Excel files (.xlsx, .xls). This mirrors the existing Value Index upload feature but is restricted to Excel format only (no CSV support).

## Features Added

### 1. Schema Management (SchemaManager.tsx)
- **Upload Section**: New upload panel at the top of the page
- **File Format**: Excel only (.xlsx, .xls)
- **Upload Modes**:
  - **Append**: Add new schemas without removing existing ones
  - **Replace**: Clear all schemas and reload with new data
- **Progress Tracking**: Real-time progress bar with percentage
- **Success/Error Messages**: Visual feedback with detailed information
- **Format Guide**: Built-in info box showing required Excel columns

#### Excel Format for Schemas
```
Column 1: schema_name     (e.g., 'dbo')
Column 2: table_name      (e.g., 'Customers')
Column 3: description     (e.g., 'Customer contact and order data')
```

### 2. Few-Shot Examples (FewShotManager.tsx)
- **Upload Section**: New upload panel above the examples list
- **File Format**: Excel only (.xlsx, .xls)
- **Upload Modes**:
  - **Append**: Add new examples without removing existing ones
  - **Replace**: Clear all examples and reload with new data
- **Progress Tracking**: Real-time progress bar with percentage
- **Success/Error Messages**: Visual feedback with detailed information
- **Format Guide**: Built-in info box showing required Excel columns

#### Excel Format for Few-Shots
```
Column 1: question       (e.g., 'Show all customers from USA')
Column 2: sql_query      (e.g., 'SELECT * FROM dbo.Customers WHERE Country = 'USA'')
```

## Implementation Details

### Backend Changes

#### 1. admin_service.py
Added two new functions:

**`ingest_schemas_from_excel()`**
- Parses Excel files with schema metadata
- Validates required columns (schema_name, table_name, description)
- Supports append/replace modes
- Handles deduplication and data cleaning
- Includes progress callback for real-time updates

**`ingest_fewshots_from_excel()`**
- Parses Excel files with Q&A examples
- Validates required columns (question, sql_query)
- Supports append/replace modes
- Handles deduplication and data cleaning
- Includes progress callback for real-time updates

#### 2. admin.py (endpoints)
Added two new API endpoints:

**`POST /api/v1/admin/ingest-schemas`**
```
Parameters:
  - file: Excel file (.xlsx/.xls)
  - mode: "append" or "replace" (default: "append")

Response:
{
  "status": "success",
  "message": "Successfully ingested X schemas",
  "rows_processed": 5,
  "total_rows": 5
}
```

**`POST /api/v1/admin/ingest-fewshots`**
```
Parameters:
  - file: Excel file (.xlsx/.xls)
  - mode: "append" or "replace" (default: "append")

Response:
{
  "status": "success",
  "message": "Successfully ingested X few-shot examples",
  "rows_processed": 10,
  "total_rows": 10
}
```

Both endpoints:
- Use SSE (Server-Sent Events) for real-time progress tracking
- Share the existing `/admin/ingest-progress` endpoint
- Support the same global progress state
- Return structured error messages on failure

### Frontend Changes

#### 1. client.ts (API Client)
Added two new admin methods:

**`api.admin.ingestSchemas(file, mode, onProgress)`**
- Accepts Excel file and upload mode
- Tracks progress via SSE
- Returns ingestion results

**`api.admin.ingestFewShots(file, mode, onProgress)`**
- Accepts Excel file and upload mode
- Tracks progress via SSE
- Returns ingestion results

#### 2. SchemaManager.tsx
- Added `UploadStatus` state interface
- Added upload mode selection (append/replace)
- Added file upload input with Excel-only validation
- Added progress bar component
- Added success/error message components
- Added format guide info section
- Updated imports to include Upload, Loader2 icons

#### 3. FewShotManager.tsx
- Added `UploadStatus` state interface
- Added upload mode selection (append/replace)
- Added file upload input with Excel-only validation
- Added progress bar component
- Added success/error message components
- Added format guide info section
- Updated imports to include Upload, Loader2, CheckCircle, AlertCircle icons

## File Changes Summary

### Modified Files
1. **app/services/admin_service.py** (+182 lines)
   - Added `ingest_schemas_from_excel()`
   - Added `ingest_fewshots_from_excel()`

2. **app/api/endpoints/admin.py** (+91 lines)
   - Added imports for new functions
   - Added POST `/admin/ingest-schemas`
   - Added POST `/admin/ingest-fewshots`

3. **frontend/src/api/client.ts** (+96 lines)
   - Added `api.admin.ingestSchemas()`
   - Added `api.admin.ingestFewShots()`

4. **frontend/src/pages/Admin/SchemaManager.tsx** (restructured)
   - Added upload UI section
   - Added file upload handler
   - Added upload state management
   - Added format guide

5. **frontend/src/pages/Admin/FewShotManager.tsx** (restructured)
   - Added upload UI section
   - Added file upload handler
   - Added upload state management
   - Added format guide

## Usage Guide

### Uploading Schemas

1. **Navigate to Admin Panel** → **Schema Management**
2. **Prepare Excel File** with columns:
   - `schema_name`: Database schema (e.g., 'dbo')
   - `table_name`: Table name (e.g., 'Products')
   - `description`: Table description for semantic search
3. **Select Upload Mode**:
   - "Append" to add without removing existing
   - "Replace" to clear and reload all
4. **Upload File**: Click upload area or drag/drop
5. **Monitor Progress**: Real-time progress bar shows upload status
6. **Verify**: Check success message for row counts

### Uploading Few-Shot Examples

1. **Navigate to Admin Panel** → **Few-Shot Examples**
2. **Prepare Excel File** with columns:
   - `question`: Natural language question (e.g., "Show top 5 customers")
   - `sql_query`: Correct T-SQL query
3. **Select Upload Mode**:
   - "Append" to add without removing existing
   - "Replace" to clear and reload all
4. **Upload File**: Click upload area or drag/drop
5. **Monitor Progress**: Real-time progress bar shows upload status
6. **Verify**: Check success message for row counts

## Technical Details

### Error Handling
- File type validation (Excel only)
- Column validation with helpful error messages
- Data cleaning (strip whitespace, remove empty rows)
- Deduplication to prevent duplicate entries
- Progress callback error handling (non-blocking)
- Structured API error responses

### Data Validation

**Schemas:**
- Required: schema_name, table_name, description
- All fields must be non-empty strings
- Duplicates removed (by schema_name + table_name)

**Few-Shots:**
- Required: question, sql_query
- All fields must be non-empty strings
- Duplicates removed (by question only)

### Progress Tracking
- Uses Server-Sent Events (SSE) for real-time updates
- Shared `/admin/ingest-progress` endpoint
- Global `_upload_progress` state
- Updates at 0.5-second intervals
- Automatically closes on completion or error
- 5-second timeout safety net

## Comparison with Value Index Upload

| Feature | Schemas | Few-Shots | Values |
|---------|---------|-----------|--------|
| File Format | Excel only | Excel only | Excel + CSV |
| Upload Modes | Append/Replace | Append/Replace | Append/Replace |
| Progress Tracking | SSE | SSE | SSE |
| Download Template | No | No | Yes |
| Max File Size | No limit | No limit | No limit |
| Required Columns | 3 | 2 | 5 |
| Deduplication | Yes | Yes | Yes |
| Data Cleaning | Yes | Yes | Yes |

## Future Enhancements

1. **Download Templates**: Add ability to download Excel templates for schemas and few-shots
2. **Batch Operations**: Allow selecting multiple files for upload
3. **Import History**: Track what was uploaded and when
4. **Validation Preview**: Show preview of data before import
5. **CSV Support**: Extend to support CSV format if needed
6. **Column Mapping**: Allow custom column mapping for flexibility

## Dependencies

### Python (Backend)
- pandas (already required for Excel/CSV parsing)
- openpyxl (already included in pandas dependencies)

### TypeScript/React (Frontend)
- axios (already used)
- lucide-react (already used for icons)

## Testing Recommendations

1. **Basic Upload**: Test with valid Excel file with all required columns
2. **Append Mode**: Upload, then upload again with different data
3. **Replace Mode**: Upload once, then replace with new data
4. **Error Cases**:
   - Missing columns
   - Empty file
   - Invalid file format (test with PDF, etc.)
   - Duplicate entries (verify deduplication)
5. **Progress**: Monitor progress bar during upload
6. **UI**: Test on different screen sizes

## Troubleshooting

### "File must be Excel format"
- Ensure file ends with .xlsx or .xls
- Check file isn't actually CSV despite extension

### "File must contain columns: ..."
- Verify column names match exactly (case-insensitive matching)
- Check for extra spaces in column headers
- Ensure all required columns are present

### Upload stops at 0%
- Check file size (should be reasonable)
- Verify network connection
- Check browser console for errors
- Try refreshing and uploading again

### Success message but data not appearing
- Wait a moment (data may still be processing)
- Click "Refresh Status" button (for schemas)
- Refresh the page to reload data
- Check if mode was "replace" - verify old data cleared first

## Notes

- The feature reuses the existing SSE progress endpoint (`/admin/ingest-progress`)
- Both endpoints validate file type on the frontend AND backend
- Data is deduplicated and cleaned before insertion
- Progress callbacks are non-blocking and won't fail if event source closes early
- The implementation follows the same pattern as Value Index upload for consistency
