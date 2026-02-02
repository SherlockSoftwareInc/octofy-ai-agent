# Skills Manager UI Guide

> Visual walkthrough of the Skills Manager interface with view/edit modes

---

## Interface Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Admin Panel → Skills Manager                                           │
├────────────────────────┬────────────────────────────────────────────────┤
│                        │                                                │
│   📁 Skills Folder     │         📄 dbo.Customers.md                   │
│   ├─ 📋 _index.md      │                                                │
│   └─ 📁 Northwind      │         [View] [Raw]                  [Edit]   │
│      ├─ 📄 _data-sou…  │  ┌──────────────────────────────────────────┐  │
│      ├─ 📁 data-groups │  │                                          │  │
│      │  ├─ 📄 _custom… │  │  # Table: [dbo].[Customers]              │  │
│      │  ├─ 📄 _orders… │  │                                          │  │
│      │  └─ 📄 _produc… │  │  **Schema:** dbo                         │  │
│      └─ 📁 schemas     │  │  **Type:** Table                         │  │
│         └─ 📁 dbo      │  │                                          │  │
│            ├─ 📄 dbo.C… │  │  ## Description                          │  │
│            ├─ 📄 dbo.O… │  │                                          │  │
│            └─ 📄 dbo.P… │  │  Stores detailed information...          │  │
│                        │  │                                          │  │
│   File Info            │  └──────────────────────────────────────────┘  │
│   ├─ Path: skills/...  │                                                │
│   ├─ Lines: 45         │  ℹ️  Viewing rendered markdown - toggle to    │
│   └─ Size: 1.2k chars  │     Raw to see source                         │
│                        │                                                │
└────────────────────────┴────────────────────────────────────────────────┘
```

---

## View Modes

### 1. View Mode (Default) - Rendered HTML

**What you see:**
- ✨ Beautiful formatted content
- 🎨 Styled headings and text
- 📊 Pretty tables
- 💻 Syntax-highlighted code
- 🔗 Clickable links

```
┌─────────────────────────────────────────────────────┐
│  📄 _data-source.md          [View] [Raw]    [Edit] │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Northwind                                          │
│  ════════════════════════════════════════════       │
│                                                     │
│  Type: SQL Server                                   │
│  Status: Active                                     │
│                                                     │
│  Description                                        │
│  ────────────────────────────────────────           │
│                                                     │
│  Database schema: dbo. Contains 39 tables for       │
│  the Northwind sample database.                     │
│                                                     │
│  Data Groups                                        │
│  ────────────────────────────────────────           │
│                                                     │
│  • data-groups/_customers-group.md                  │
│  • data-groups/_orders-group.md                     │
│  • data-groups/_products-group.md                   │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Features:**
- Headings styled with larger fonts and borders
- Lists with proper bullets/numbers
- Tables with hover effects
- Code blocks with syntax colors
- Links in blue/indigo color

---

### 2. Raw Mode - Source Code

**What you see:**
- 📝 Raw markdown text
- 🔤 Monospace font
- ⬜ Plain formatting
- 📋 Copy-friendly

```
┌─────────────────────────────────────────────────────┐
│  📄 _data-source.md          [View] [Raw]    [Edit] │
├─────────────────────────────────────────────────────┤
│                                                     │
│  # Northwind                                        │
│                                                     │
│  **Type:** SQL Server                               │
│  **Status:** Active                                 │
│                                                     │
│  ## Description                                     │
│                                                     │
│  Database schema: dbo. Contains 39 tables for       │
│  the Northwind sample database.                     │
│                                                     │
│  ## Data Groups                                     │
│                                                     │
│  - [data-groups/_customers-group.md](...)           │
│  - [data-groups/_orders-group.md](...)              │
│  - [data-groups/_products-group.md](...)            │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Features:**
- See exact markdown syntax
- Identify formatting issues
- Copy markdown source
- Learn markdown structure

---

### 3. Edit Mode - Active Editing

**What you see:**
- ✏️ Editable text area
- 💾 Save and Cancel buttons
- 🔄 Loading indicator when saving
- ⚠️ Helper text at bottom

```
┌─────────────────────────────────────────────────────┐
│  📄 _data-source.md          [Cancel] [💾 Save]     │
├─────────────────────────────────────────────────────┤
│  # Northwind█                                       │
│                                                     │
│  **Type:** SQL Server                               │
│  **Status:** Active                                 │
│                                                     │
│  ## Description                                     │
│                                                     │
│  Database schema: dbo. Contains 39 tables for       │
│  the Northwind sample database.                     │
│                                                     │
│  ## Data Groups                                     │
│                                                     │
│  - [data-groups/_customers-group.md](...)           │
│  - [data-groups/_orders-group.md](...)              │
│  - [data-groups/_products-group.md](...)            │
│                                                     │
├─────────────────────────────────────────────────────┤
│  ℹ️  Editing mode - make your changes and click     │
│     Save                                            │
└─────────────────────────────────────────────────────┘
```

**Actions:**
- **Cancel**: Discard changes, reload original
- **Save**: Persist changes to disk
- **During Save**: Button shows spinner and "Saving..."
- **After Save**: Toast notification confirms success

---

## Markdown Rendering Examples

### Headings

**Markdown:**
```markdown
# Heading 1
## Heading 2
### Heading 3
```

**Rendered (View Mode):**
```
Heading 1
═════════════════════════════════════════

Heading 2
─────────────────────────────────────────

Heading 3
```

---

### Tables

**Markdown:**
```markdown
| Column | Type | Description |
|--------|------|-------------|
| ID     | INT  | Primary key |
| Name   | VARCHAR | Customer name |
```

**Rendered (View Mode):**
```
┌────────┬─────────┬────────────────┐
│ Column │ Type    │ Description    │
├────────┼─────────┼────────────────┤
│ ID     │ INT     │ Primary key    │
│ Name   │ VARCHAR │ Customer name  │
└────────┴─────────┴────────────────┘
```

---

### Code Blocks

**Markdown:**
````markdown
```sql
SELECT * FROM Customers
WHERE Country = 'USA'
```
````

**Rendered (View Mode):**
```sql
SELECT * FROM Customers
WHERE Country = 'USA'
```
*With purple keywords, green strings, and proper syntax highlighting*

---

### Lists

**Markdown:**
```markdown
- Item 1
- Item 2
  - Nested item
- Item 3
```

**Rendered (View Mode):**
```
• Item 1
• Item 2
  ◦ Nested item
• Item 3
```

---

### Blockquotes

**Markdown:**
```markdown
> Important note here
> that spans multiple lines
```

**Rendered (View Mode):**
```
┃ Important note here
┃ that spans multiple lines
```
*With blue left border and gray background*

---

## Navigation Flow

### Opening a File

```
1. Browse Tree               2. Click File              3. View Content
┌─────────────┐            ┌─────────────┐            ┌─────────────┐
│ 📁 Northwind│            │ 📁 Northwind│            │ 📄 File.md  │
│ ├─ 📄 _data…│  ──────>   │ ├─ 📄 _data…│  ──────>   │ [View][Raw] │
│ ├─ 📁 data- │            │ ├─ 📁 data- │            │             │
│ └─ 📁 schem…│            │ └─ 📁 schem…│            │ Content...  │
└─────────────┘            └─────────────┘            └─────────────┘
```

### Editing a File

```
1. View Mode                2. Click Edit              3. Make Changes
┌─────────────┐            ┌─────────────┐            ┌─────────────┐
│ 📄 File.md  │            │ 📄 File.md  │            │ 📄 File.md  │
│ [View][Raw] │            │ [View][Raw] │            │[Cancel][Save│
│    [Edit]   │  ──────>   │    [Edit]   │  ──────>   │             │
│             │            │             │            │ # Edit...█  │
│ Content...  │            │ Content...  │            └─────────────┘
└─────────────┘            └─────────────┘                  │
                                                            │
4. Save                    5. Success Toast                 │
┌─────────────┐            ┌─────────────┐                 │
│ 📄 File.md  │            │ ┌─────────┐ │  <──────────────┘
│ [View][Raw] │            │ │✅ Saved!│ │
│    [Edit]   │  <───────  │ └─────────┘ │
│             │            │             │
│ Content...  │            │ Content...  │
└─────────────┘            └─────────────┘
```

---

## Toast Notifications

### Success Toast (Green)
```
┌────────────────────────────┐
│ ✅ File saved successfully │
│                          × │
└────────────────────────────┘
```

### Error Toast (Red)
```
┌────────────────────────────┐
│ ❌ Failed to save file     │
│                          × │
└────────────────────────────┘
```

*Auto-dismisses after 3 seconds or click × to close*

---

## File Tree Icons

| Icon | Type | Description |
|------|------|-------------|
| 📁 | Folder (Collapsed) | Clickable to expand |
| 📂 | Folder (Expanded) | Clickable to collapse |
| 📄 | Markdown File | Clickable to open |
| 📋 | Index File | Special markdown file |
| ▶️ | Expand Arrow | Click to expand folder |
| ▼ | Collapse Arrow | Click to collapse folder |

---

## Keyboard Navigation

| Key | Action |
|-----|--------|
| `Click` file | Open file |
| `Click` folder | Expand/collapse |
| `Arrow` on expand button | Expand/collapse without selecting |
| `Tab` | Navigate between elements |
| `Enter` | Activate button |

---

## Best Practices

### ✅ Do's

1. **Toggle to View first** when opening a file
2. **Use Raw mode** to check syntax
3. **Click Cancel** if you make a mistake
4. **Save frequently** when editing
5. **Check File Info** panel for size/lines

### ❌ Don'ts

1. **Don't refresh** while editing (you'll lose changes)
2. **Don't edit multiple files** at once (save first)
3. **Don't forget to Save** before closing
4. **Don't use browser Back** button while editing

---

## Responsive Design

The Skills Manager adapts to different screen sizes:

### Desktop (1920px+)
```
┌─────────────────────────────────────────┐
│ Tree (30%)    │    Content (70%)        │
│               │                         │
└─────────────────────────────────────────┘
```

### Laptop (1366px)
```
┌──────────────────────────────┐
│ Tree (33%) │  Content (67%)  │
│            │                 │
└──────────────────────────────┘
```

### Tablet/Small (768px+)
```
┌────────────┐
│ Tree       │
│ (Full)     │
├────────────┤
│ Content    │
│ (Full)     │
└────────────┘
```

---

## Color Scheme

### View Mode
- **Headings**: White (`#f1f5f9`)
- **Text**: Light gray (`#cbd5e1`)
- **Code**: Amber background (`#1e293b`)
- **Links**: Indigo (`#818cf8`)
- **Tables**: Gray borders (`#334155`)

### Raw Mode
- **Text**: Light gray (`#e2e8f0`)
- **Background**: Dark slate (`#0f172a`)
- **Border**: Slate (`#334155`)

### Edit Mode
- **Text**: Light gray (`#e2e8f0`)
- **Background**: Very dark slate (`#020617`)
- **Border**: Slate (`#334155`)
- **Focus Ring**: Indigo (`#6366f1`)

---

## Summary

The Skills Manager provides:

✅ **Three viewing modes**: View (HTML), Raw (source), Edit (modify)
✅ **Rich markdown rendering**: Headings, tables, code, lists, quotes
✅ **Syntax highlighting**: Language-specific code coloring
✅ **File tree navigation**: Expandable/collapsible folders
✅ **Live editing**: Make changes and save directly
✅ **Visual feedback**: Toasts for success/error messages
✅ **Responsive design**: Works on all screen sizes
✅ **Dark theme**: Easy on the eyes

**Perfect for:**
- 📖 Reading documentation
- ✏️ Editing metadata
- 🔍 Exploring Skills tree structure
- 📝 Managing data sources, groups, and tables
