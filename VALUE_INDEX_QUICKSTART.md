# Value Index Feature - Quick Start Guide

## What is the Value Index?

The Value Index maps user-provided terms (e.g., "North America") to exact database values (e.g., "NA") and their locations (schema.table.column). This prevents the AI from generating SQL with invalid values.

## Quick Start (5 minutes)

### 1. Download Excel Template

```
1. Open the app and go to Admin Panel (top-right button)
2. Click "Value Index" tab
3. Click "Download Template" button
```

### 2. Fill in Your Values

Open the downloaded `value_index_template.xlsx` and add your data:

| value       | schema_name | table_name | column_name        |
|-------------|-------------|------------|-------------------|
| NA          | dbo         | Territories| RegionDescription |
| Eastern     | dbo         | Territories| RegionDescription |
| Beverages   | dbo         | Products   | Category          |
| Seafood     | dbo         | Products   | Category          |

**Column Meanings:**
- **value**: The actual value in the database
- **schema_name**: Database schema (usually 'dbo' for SQL Server)
- **table_name**: Table containing this value
- **column_name**: Column containing this value
- **metadata**: Leave as {} (optional JSON)

### 3. Upload the File

```
1. Go back to Value Index admin page
2. Keep "Append to existing values" selected (or "Replace" to clear first)
3. Click the upload area and select your Excel file
4. Wait for the success message
```

### 4. Verify It Worked

Your uploaded values should appear in the table below the upload area.

### 5. Test with a Query

Go back to the chat and try a query using your values:

```
"Show me orders for Beverages category"
```

The LLM will now have access to verified data mappings and generate better SQL!

## How It Works Under the Hood

```
1. User uploads Excel with values
   ↓
2. Backend parses file and validates format
   ↓
3. Each value is embedded using OpenAI's text-embedding-3-small
   ↓
4. Embeddings + metadata stored in Milvus vector database
   ↓
5. When user queries the AI:
   - System performs semantic search for relevant values
   - Injects verified values into the LLM prompt
   - LLM generates SQL using correct values (no hallucination!)
```

## Common Tasks

### Upload More Values

1. Go to Value Index
2. Select "Append to existing values"
3. Upload new Excel file with additional rows
4. New values are added without removing existing ones

### Replace All Values

1. Go to Value Index
2. Select "Replace all values (clear first)"
3. Upload Excel file
4. All previous values deleted, new values uploaded

### Delete Specific Value

1. Find the value in the table
2. Click the trash icon on the right
3. Value is removed from index

### Clear Everything

1. Click "Clear All Values" button
2. Confirm deletion
3. All values removed (can re-upload anytime)

### Search Values

1. Use the search box above the values table
2. Search by:
   - Value name (e.g., "Beverages")
   - Table name (e.g., "Products")
   - Column name (e.g., "Category")

## Excel Format Rules

✅ **DO:**
- Use exactly 4 or 5 columns
- Column order: value, schema_name, table_name, column_name, metadata
- Fill in all 4 required columns
- Use real database schema/table/column names
- Save as .xlsx or .csv format

❌ **DON'T:**
- Add extra columns
- Change column order
- Leave required columns blank
- Use incorrect schema/table names
- Save as .xls (old format)

## Supported Value Types

- Text: "North America", "Beverages", "Active"
- Numbers: "1", "100", "2024"
- Dates: "2024-01-15" (any format)
- Codes: "NA", "BEV", "ACT"

## Performance

- **Upload Speed:** ~100-200 values per second
- **Search Speed:** <50ms per query
- **Max File Size:** Limited by RAM (typically 50,000+ rows)

## Troubleshooting

**Q: "File must be Excel format"**
- A: Save your file as .xlsx (not .xls or .xlt)

**Q: Upload fails with validation error**
- A: Check that your Excel has exactly 4-5 columns in this order:
  value, schema_name, table_name, column_name, metadata

**Q: Values uploaded but not used in SQL**
- A: Values only help if they match the semantic meaning of your query
  - Try queries that mention the actual value names
  - Example: Upload "Beverages" for category, then query "show beverages"

**Q: How many values can I upload?**
- A: Limited by available memory (~50,000 values easily, more possible)

**Q: Can I edit values after uploading?**
- A: Delete and re-upload, or use "Replace all values" mode

## Real-World Example

### Setup
Upload these values:
```
North America  | dbo | Territories | RegionDescription
South America  | dbo | Territories | RegionDescription
Europe         | dbo | Territories | RegionDescription
```

### Query
User: "How many orders came from North America?"

### Without Value Index
LLM might try:
```sql
WHERE region = 'North America'  -- ❌ Won't match!
```

### With Value Index
LLM sees:
```
### VERIFIED DATA MAPPINGS
- dbo.Territories.RegionDescription: 'North America', 'South America'
```

And generates:
```sql
WHERE territory_desc = 'North America'  -- ✅ Correct!
```

## Next Steps

1. **Identify your data**
   - What lookup tables exist in your database?
   - What are common filter values?
   
2. **Create an Excel file** with your values
   - Use the template as a starting point
   - One row per value

3. **Upload to Value Index**
   - Follow the "Quick Start" steps above

4. **Test with your real data**
   - Make queries using your domain terminology
   - Verify SQL uses correct values

## Tips for Best Results

1. **Use natural language values**
   - Good: "North America", "Executive"
   - Less good: "NA", "exec"

2. **Include related values together**
   - Upload all region names
   - Upload all category names
   - Upload all status values

3. **Keep values unique**
   - Don't upload duplicates
   - System automatically deduplicates

4. **Update regularly**
   - Add new values as business changes
   - Remove obsolete values

## Need Help?

See full documentation:
- `VALUE_INDEX_FEATURE.md` - Complete feature guide
- `VALUE_INDEX_IMPLEMENTATION.md` - Technical details

---

**Ready to improve your SQL generation? Upload your first values now! 🚀**
