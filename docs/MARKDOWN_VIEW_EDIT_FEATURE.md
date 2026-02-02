# Markdown View/Edit Feature

> Dual-mode viewer and editor for all markdown files in the Skills tree

---

## Overview

The Skills Manager now supports **two viewing modes** for all markdown files:

1. **View Mode** - Renders markdown as beautifully formatted HTML
2. **Raw Mode** - Shows the raw markdown source code

Plus a dedicated **Edit Mode** for making changes to the files.

---

## Features

### 📖 View Mode (Default)

- **Rendered HTML**: Converts markdown to styled HTML in real-time
- **Syntax Highlighting**: Code blocks are highlighted with language-specific colors
- **GFM Support**: GitHub Flavored Markdown (tables, task lists, strikethrough)
- **Custom Styling**: Dark theme optimized for readability
- **Responsive Tables**: Horizontal scrolling for wide tables
- **Clickable Links**: External links open in new tabs

### 📝 Raw Mode

- **Source View**: See the raw markdown exactly as stored in the file
- **Monospace Font**: Easy to read markdown syntax
- **Line Wrapping**: Long lines wrap naturally
- **Copy-Friendly**: Easy to copy markdown source

### ✏️ Edit Mode

- **Live Editing**: Type directly in the markdown source
- **Syntax-Aware**: Monospace editor for markdown editing
- **Auto-Save**: Save button updates the file on disk
- **Cancel Support**: Discard changes and reload original content
- **Cache Clearing**: Automatically refreshes Skills cache after saving

---

## User Interface

### Mode Toggle

```
┌─────────────────────────────────────────┐
│  📄 filename.md               [View][Raw] │
│                                    [Edit] │
├─────────────────────────────────────────┤
│                                          │
│  Markdown content displays here...       │
│                                          │
└─────────────────────────────────────────┘
```

### Edit Mode

```
┌─────────────────────────────────────────┐
│  📄 filename.md        [Cancel] [Save]   │
├─────────────────────────────────────────┤
│ # Markdown Source                        │
│                                          │
│ Edit directly here...                    │
│                                          │
└─────────────────────────────────────────┘
```

---

## Supported Markdown Features

### Headings
```markdown
# H1 - Largest heading
## H2 - Section heading
### H3 - Subsection
#### H4 - Minor heading
```

### Text Formatting
```markdown
**Bold text**
*Italic text*
~~Strikethrough~~
`inline code`
```

### Lists
```markdown
- Unordered list item
- Another item
  - Nested item

1. Ordered list item
2. Second item
```

### Links and Images
```markdown
[Link text](https://example.com)
![Image alt text](image-url.png)
```

### Code Blocks
````markdown
```python
def hello():
    print("Hello, World!")
```
````

### Tables
```markdown
| Column 1 | Column 2 | Column 3 |
|----------|----------|----------|
| Data 1   | Data 2   | Data 3   |
| Data 4   | Data 5   | Data 6   |
```

### Blockquotes
```markdown
> This is a blockquote
> It can span multiple lines
```

### Horizontal Rules
```markdown
---
```

---

## Technical Implementation

### Frontend Components

#### MarkdownViewer Component
**File:** `frontend/src/components/MarkdownViewer.tsx`

**Features:**
- Uses `react-markdown` for parsing
- `remark-gfm` plugin for GitHub Flavored Markdown
- `react-syntax-highlighter` for code blocks
- Custom styled components for all markdown elements
- Dark theme with Tailwind CSS classes

**Props:**
```typescript
interface MarkdownViewerProps {
    content: string;      // Markdown source
    className?: string;   // Additional CSS classes
}
```

**Example Usage:**
```tsx
<MarkdownViewer 
    content={markdownContent}
    className="flex-1"
/>
```

---

#### MarkdownEditor Component
**File:** `frontend/src/components/MarkdownEditor.tsx`

**Features:**
- Simple textarea with monospace font
- Syntax-aware styling
- Focus ring for accessibility
- Resize disabled for consistent layout

**Props:**
```typescript
interface MarkdownEditorProps {
    content: string;           // Current markdown
    onChange: (content: string) => void;  // Update handler
    className?: string;        // Additional CSS classes
    placeholder?: string;      // Placeholder text
}
```

**Example Usage:**
```tsx
<MarkdownEditor
    content={markdownContent}
    onChange={setMarkdownContent}
    className="flex-1"
    placeholder="Enter markdown..."
/>
```

---

### Backend Endpoints

All existing endpoints in `/api/v1/admin/skills/` support markdown operations:

#### Get Markdown Content
```
GET /admin/skills/raw-markdown?file_path={path}&api_key={key}
```

**Response:**
```json
{
  "content": "# Markdown content...",
  "file_path": "skills/data-sources/..."
}
```

#### Save Markdown Content
```
PUT /admin/skills/raw-markdown?api_key={key}
```

**Request Body:**
```json
{
  "file_path": "skills/data-sources/...",
  "content": "# Updated markdown..."
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Markdown file saved",
  "file_path": "skills/data-sources/..."
}
```

---

### Styling

**File:** `frontend/src/index.css`

Custom CSS classes for markdown rendering:

```css
.markdown-viewer {
  line-height: 1.7;
}

.markdown-viewer h1,
.markdown-viewer h2,
.markdown-viewer h3 {
  font-weight: 600;
  line-height: 1.3;
}

.markdown-viewer code {
  font-family: 'Courier New', Courier, monospace;
  font-size: 0.9em;
}

.markdown-viewer pre {
  border-radius: 0.5rem;
  overflow-x: auto;
}
```

---

## Usage Examples

### Viewing a Data Source File

1. Navigate to **Admin → Skills Manager**
2. Expand the data source folder (e.g., `Northwind/`)
3. Click on `_data-source.md`
4. **Default View**: See beautifully rendered HTML with:
   - Formatted headings
   - Syntax-highlighted code blocks
   - Styled tables
   - Clickable links

### Switching to Raw Mode

1. With a file open, click the **[Raw]** button in the top toolbar
2. See the markdown source code in monospace font
3. Toggle back to **[View]** to see rendered HTML

### Editing a File

1. Open any markdown file
2. Click **[Edit]** button
3. Make changes in the editor
4. Click **[Save]** to persist changes
5. Click **[Cancel]** to discard changes

---

## File Types Supported

The view/edit feature works with all markdown files in the Skills tree:

| File Type | Location | Description |
|-----------|----------|-------------|
| **Index** | `_index.md` | Data sources catalog |
| **Data Source** | `{source}/_data-source.md` | Source metadata |
| **Data Group** | `data-groups/_*-group.md` | Logical groupings |
| **Table Schema** | `schemas/{schema}/{table}.md` | Table definitions |

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl/Cmd + S` | Save (when editing) |
| `Esc` | Cancel edit mode |

> Note: Keyboard shortcuts are browser-dependent

---

## Best Practices

### When to Use View Mode
- ✅ Reading documentation
- ✅ Understanding table schemas
- ✅ Reviewing formatted content
- ✅ Checking rendered output

### When to Use Raw Mode
- ✅ Checking markdown syntax
- ✅ Debugging formatting issues
- ✅ Copying markdown source
- ✅ Learning markdown structure

### When to Use Edit Mode
- ✅ Fixing typos
- ✅ Adding documentation
- ✅ Updating keywords
- ✅ Modifying descriptions

---

## Limitations

1. **No Preview While Editing**: Must save to see rendered output
   - *Solution*: Toggle between View and Edit modes to preview
   
2. **No Undo History**: Browser undo only (`Ctrl+Z`)
   - *Solution*: Use Cancel to discard all changes
   
3. **No Multi-File Editing**: One file at a time
   - *Solution*: Save current file before opening another

4. **No Collaborative Editing**: Last save wins
   - *Solution*: Coordinate with team when editing

---

## Dependencies

### Frontend
```json
{
  "react-markdown": "^9.1.0",
  "react-syntax-highlighter": "^16.1.0",
  "remark-gfm": "^4.0.1"
}
```

### Backend
```
markdown==3.10.1
```

---

## Future Enhancements

Potential improvements for future releases:

- [ ] **Live Preview**: Split-screen editor with real-time preview
- [ ] **Version History**: Track changes over time
- [ ] **Search in File**: Find and replace within markdown
- [ ] **Markdown Toolbar**: Quick insert buttons for formatting
- [ ] **Image Upload**: Drag-and-drop image support
- [ ] **Export Options**: Download as PDF or HTML
- [ ] **Collaborative Editing**: Real-time multi-user editing
- [ ] **Diff View**: Show changes before saving

---

## Troubleshooting

### Markdown Not Rendering
**Issue**: View mode shows raw markdown instead of HTML

**Solution**: Check that `react-markdown` is installed:
```bash
cd frontend
npm install react-markdown remark-gfm react-syntax-highlighter
```

### Save Not Working
**Issue**: Changes don't persist after clicking Save

**Solution**: 
1. Check file permissions on the `skills/` directory
2. Verify API key is valid
3. Check browser console for errors

### Code Blocks Not Highlighted
**Issue**: Code blocks show as plain text

**Solution**: Ensure language is specified in markdown:
````markdown
```python
code here
```
````

---

## Related Documentation

- [SKILLS_CRUD_API.md](SKILLS_CRUD_API.md) - Complete CRUD API reference
- [SKILLS_QUICK_REFERENCE.md](SKILLS_QUICK_REFERENCE.md) - Quick command guide
- [CONTEXT.md](CONTEXT.md) - Project overview
