# Skills Markdown Editor Feature

## Overview

Added a **Raw Markdown Editor** mode to the Skills Manager that allows direct editing of skill `.md` files as plain text.

---

## Features

### 1. View Mode Toggle
- **Form View**: Structured form editing (existing functionality)
- **Raw MD View**: Direct markdown file editing (new!)

### 2. Markdown Editor
- **Read-only preview** when not editing
- **Full-text editor** when in edit mode
- **Line/character count** display
- **Monospace font** with syntax-friendly styling
- **Warning indicator** about careful editing

### 3. Smart Loading
- Markdown content loaded on-demand when switching to Raw MD view
- Cached until you switch back to Form view
- No performance impact on tree navigation

---

## Backend API Endpoints

### GET `/admin/skills/raw-markdown`
Get raw markdown content of a skill file.

**Query Parameters:**
- `file_path` (string): Path to the skill `.md` file

**Response:**
```json
{
  "content": "# Data Source\n\n**Type:** SQL Server...",
  "file_path": "skills/data-sources/dbo-database/_data-source.md"
}
```

### PUT `/admin/skills/raw-markdown`
Save raw markdown content to a skill file.

**Request Body:**
```json
{
  "file_path": "skills/data-sources/dbo-database/_data-source.md",
  "content": "# Updated Data Source\n\n..."
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Markdown file saved",
  "file_path": "skills/data-sources/dbo-database/_data-source.md"
}
```

**Features:**
- Validates file exists before writing
- Clears skills service cache to reload data
- UTF-8 encoding support

---

## Frontend Changes

### `SkillsManager.tsx` Updates

**1. DetailPanel Component:**
- Added `viewMode` state: `'form' | 'markdown'`
- Added `markdownContent` state for raw content
- Added `loadMarkdown()` function to fetch content
- Updated `handleSave()` to handle both form and markdown modes

**2. View Mode Toggle:**
```tsx
<div className="flex bg-slate-800 rounded-lg p-1">
  <button onClick={() => setViewMode('form')}>Form</button>
  <button onClick={() => loadMarkdown()}>Raw MD</button>
</div>
```

**3. MarkdownEditor Component:**
- New component for markdown editing
- Textarea in edit mode, `<pre>` in read-only mode
- Line/character counter
- Warning message about careful editing

### `client.ts` Updates

Added API methods:
- `api.admin.getRawMarkdown(filePath): Promise<string>`
- `api.admin.saveRawMarkdown(filePath, content): Promise<void>`

---

## User Workflow

### Editing a Skill File as Markdown

1. **Navigate**: Select any data source, data group, or table in the tree
2. **Switch Mode**: Click "Raw MD" button in the detail panel
3. **Edit**: Click "Edit" button to enable editing
4. **Modify**: Edit the markdown content directly in the textarea
5. **Save**: Click "Save" to write changes back to the file
6. **Refresh**: Tree automatically reloads to reflect changes

### Best Practices

✅ **Use Raw MD mode for:**
- Complex formatting changes
- Bulk text editing
- Adding custom markdown sections
- Copy/paste from other files

✅ **Use Form mode for:**
- Simple field updates (name, keywords, etc.)
- Quick edits
- Safer, validated changes

---

## Technical Details

### Cache Management
When saving raw markdown, the backend automatically clears the skills service cache:
```python
skills_service = get_skills_service()
skills_service._data_sources_cache = None
skills_service._data_groups_cache = None
```

### File Validation
- Checks file exists before reading/writing
- Returns 404 if file not found
- UTF-8 encoding enforced

### UI State Management
- Markdown content loaded lazily (on first view)
- Edit mode disabled when switching between Form/MD views
- Loading spinner while fetching content

---

## Files Modified

### Backend
- `app/api/endpoints/admin.py` - Added 2 new endpoints (+47 lines)

### Frontend  
- `frontend/src/api/client.ts` - Added 2 API methods (+14 lines)
- `frontend/src/pages/Admin/SkillsManager.tsx` - Added markdown editor (+134 lines)

---

## Example Use Cases

### 1. Add Custom Documentation Section
```markdown
# Customer Data Group

**Data Source:** Northwind
**Keywords:** customers, orders, contact

## Description
Customer-related tables including contact information and order history.

## Custom Notes
**Migration Status:** Complete
**Last Reviewed:** 2026-01-31
**Owner:** Data Team
```

### 2. Bulk Edit Keywords
Switch to Raw MD view and edit keywords across multiple sections:
```markdown
**Keywords:** customers, crm, contacts, sales, marketing
```

### 3. Fix Formatting Issues
Directly fix markdown syntax errors or inconsistencies:
```markdown
- **[dbo.Customers](../schemas/dbo/dbo.Customers.md)** - Customer master table
- **[dbo.Orders](../schemas/dbo/dbo.Orders.md)** - Order transactions
```

---

## Safety Features

1. **Read-only preview** when not editing prevents accidental changes
2. **Warning message** reminds users to be careful with formatting
3. **File validation** prevents writing to non-existent files
4. **Automatic cache refresh** ensures UI stays in sync
5. **UTF-8 encoding** preserves special characters

---

## Future Enhancements (Optional)

- [ ] Markdown syntax highlighting
- [ ] Split-pane view (edit + preview side-by-side)
- [ ] Markdown validation/linting
- [ ] Diff view for changes
- [ ] Undo/redo functionality
- [ ] Search/replace within markdown

---

## Summary

The Raw Markdown Editor gives you **full control** over skill files while maintaining the convenience of the form-based editor. Switch between modes based on your editing needs - use forms for simple updates, markdown for advanced editing.

**Result:** More flexible, powerful skills management with direct file access when you need it! 🎉
