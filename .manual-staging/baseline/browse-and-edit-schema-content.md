# Browse and Edit Schema Content

The [Schema Library Form](schema-library-form.md) lets you browse the schema library tree and edit its content in dedicated editors. This topic describes the tree, the content surfaces, and the editing commands.

## The schema library tree

The left panel shows the library folder for the current data source with the following branches:

| Node | Contents |
| --- | --- |
| **schemas** | One node per schema; each schema node lists its tables, views, and functions. |
| **data-groups** | One node per data group (business grouping of objects). |
| **tools** | One node per tool function definition file. |
| **semantic-model** | One node per semantic model (newest first; inactive models labeled **(inactive)**). |

## Selecting nodes drives the content area

| Selection | Content area |
| --- | --- |
| **schemas** folder | Grid preview of the schema index (schema name + description). |
| Schema node | Grid preview of that schema's object index (object name + type + description). |
| **data-groups** folder | Grid preview of the data-group index (group name + description). |
| **semantic-model** folder | Embedded [semantic model editor](semantic-models.md) (latest active model, or a fresh model when none exists). |
| Semantic model node | Embedded semantic model editor on that specific model. |
| Object file node | Embedded **database object editor**. |
| Data-group file node | Embedded **data group editor**. |
| Tool function file node | Embedded [tool function editor](tool-functions.md). |
| `_data-source.md` | Text editor — the only markdown file that is editable as text. |
| JSON index file | Text editor with JSON syntax highlighting. |
| Root node / no file | Empty text surface. |

## Text editor

The text editor is a Scintilla-based code editor with:

- Syntax highlighting by file type — **JSON** for `.json` index files, **Markdown** for `_data-source.md`, and plain text otherwise.
- Line numbers, word wrap, indentation guides, and a 2-space tab width.
- **Undo / Redo**, **Cut / Copy / Paste**, and **Select All** from the **Edit** menu or the toolbar; commands target whichever control has focus.

## Grid previews and row editing

The schema, object, and data-group index views are shown as read-only grids. **Double-click a row** (or right-click and choose **Edit item**) to edit the row's metadata:

- **Schema rows** — a dialog edits the schema description and keywords; `.schema-index.json` is updated.
- **Data-group rows** — a dialog edits description, keywords, members, and business rules; the group's markdown file and `.data-group-index.json` are regenerated. See [Data Groups and Precomputed Q&As](data-groups-and-precomputed-qas.md).
- **Object rows** — a dialog edits description, usage example, keywords, and columns; the object's markdown file and `.object-index.json` are updated, and a background vector-index update is scheduled.

## Embedded editors

- **Database object editor** — edit a table/view/function's description, keywords, usage example, columns (with per-column descriptions), and business rules. **Column > Add Column Reference** adds a reference to a column of the object (enabled only in this editor). Changes are saved to the object index and markdown on navigation or close.
- **Data group editor** — edit the group's description, category, keywords, members, and business rules. The **Data Group** menu commands (**Add objects**, **Remove**, **Generate keywords**) operate on this editor.

## Context menu (tree)

Right-clicking a tree node offers context commands: **Open**, **Copy Name**, **Add**, **Manage Anticipated Questions** (data groups), **Edit Function Call Definition** / **Add Semantic Model** (see [Tool Functions](tool-functions.md) and [Semantic Models](semantic-models.md)), **Remove**, **Sync**, and **Rebuild**. Removing the root node or the top-level `schemas` / `data-groups` nodes is blocked.

## Save behavior

- Text edits are auto-saved when you switch selection or close the form.
- Editor changes are saved to the corresponding index files and markdown files; changed object files trigger a background vector-index update.
- Semantic model edits are saved asynchronously with coalescing (see [Semantic Models](semantic-models.md)).

## Related topics

- [Schema Library Form](schema-library-form.md)
- [Add Database Objects](add-database-objects.md)
- [Data Groups and Precomputed Q&As](data-groups-and-precomputed-qas.md)
- [Tool Functions](tool-functions.md)

[Back to Create Build-in AI Agent](create-build-in-ai-agent.md)
