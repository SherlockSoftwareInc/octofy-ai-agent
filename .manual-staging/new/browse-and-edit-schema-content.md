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

A table or view node also has **value-index column** children. They are read from the data source's `vector-index.db` the first time you expand the node: the placeholder child shows **Loading...** and is then replaced by one child per indexed column (tooltip `schema.table.column - n value(s)`). An object with no indexed columns stays a leaf and the status bar reports **No value index columns for ...**.

The panel has a search box above the tree. A search replaces the whole tree with matching data source → schema → object nodes; those result nodes carry no file path, so a search result selection shows an empty content area.

## Selecting nodes drives the content area

| Selection | Content area |
| --- | --- |
| **schemas** folder | Grid preview of the schema index (`schema_name` + `description`). |
| Schema node | Grid preview of that schema's object index (`object_name` + `object_type` + `description`). |
| **data-groups** folder | Grid preview of the data-group index (`group_name` + `description`). |
| **tools** folder | Grid preview of the tool function definitions (`tool_name` + `protocol` + `description`). |
| **semantic-model** folder | Grid preview of every model in `vector-index.db` (`model_name` + `model_id` + `status`). |
| Semantic model node | Embedded [semantic model editor](semantic-models.md) on that specific model. |
| Object file node | Embedded **database object editor**. |
| Value-index column node | Read-only grid preview of the values indexed for that column. |
| Data-group file node | Embedded **data group editor**. |
| Tool function file node | Embedded [tool function editor](tool-functions.md). |
| `_data-source.md` | Text editor — the only markdown file that is editable as text. |
| JSON index file | Text editor with JSON syntax highlighting. |
| Markdown file with no dedicated editor | Read blocked — an empty text surface with the status bar message **Read blocked for markdown: ...**. |
| Root node / no file | Empty text surface. |

## Text editor

The text editor is a Scintilla-based code editor with:

- Syntax highlighting by file type — **JSON** for `.json` index files, **Markdown** for `_data-source.md`, and plain text otherwise.
- Line numbers, word wrap, indentation guides, and a 2-space tab width.
- **Cut / Copy / Paste** from the **Edit** menu or the toolbar; commands target whichever control has focus. The editor's own `Ctrl+X` / `Ctrl+C` / `Ctrl+V` shortcuts work in the same way.

Markdown files that belong to a dedicated editor (object, data group, or tool function markdown) are **read blocked** in the text editor — edit them through their editor instead. Saving a read-blocked file is refused.

## Grid previews and row editing

The schema, object, and data-group index views are shown as read-only grids. **Double-click a row** (or right-click and choose **Edit Item**) to edit the row's metadata:

- **Schema rows** — a dialog edits the schema description and keywords; `.schema-index.json` is updated.
- **Data-group rows** — a dialog edits description, keywords, members, and business rules; the group's markdown file and `.data-group-index.json` are regenerated. See [Data Groups and Precomputed Q&As](data-groups-and-precomputed-qas.md).
- **Object rows** — a dialog edits description, usage example, keywords, and columns; the object's markdown file and `.object-index.json` are updated, and a background vector-index update is scheduled.

The **tools** and **semantic-model** folder previews are lists: **double-clicking a row** (or choosing **Edit Item**) opens that entity's embedded editor panel, exactly as selecting its tree node does. The value-index values preview is read-only.

## Embedded editors

- **Database object editor** — edit a table/view/function's description, keywords, usage example, columns (with per-column descriptions), and business rules. **Schemas > Add Column Reference** adds a reference to a column of the object (enabled only in this editor). Changes are saved to the object index and markdown on navigation or close.
- **Data group editor** — edit the group's description, category, keywords, members, and business rules. The **Data Groups** menu commands (**Add Objects**, **Remove**, **Generate Keywords**) operate on this editor.
- **Tool function editor** — edit the tool definition (name, description, protocol, parameters, prompts, model, and temperature). It is opened from a tool node, a tool row in the list preview, or the tree's **Edit Function Call Definition** / **Add** commands (the latter two open the same editor in a separate window).
- **Semantic model editor** — edit the model's measures, dimensions, joins, and governance predicates; there is no separate save command, the model auto-saves.

## Context menu (tree)

Right-clicking a tree node offers context commands: **Open**, **Copy Name**, **Add** (on the `data-groups` and `tools` folder nodes), **Manage Anticipated Questions** (data groups), **Edit Function Call Definition** and **Add Semantic Model** (see [Tool Functions](tool-functions.md) and [Semantic Models](semantic-models.md)), **Remove**, **Sync**, and **Rebuild**. Removing the root node or the top-level `schemas` / `data-groups` nodes is blocked.

## Save behavior

- Text edits are auto-saved when you switch selection or close the form; read-blocked markdown cannot be saved.
- Editor changes are saved to the corresponding index files and markdown files; changed object files trigger a background vector-index update.
- Semantic model edits are saved asynchronously with coalescing (see [Semantic Models](semantic-models.md)).

## Related topics

- [Schema Library Form](schema-library-form.md)
- [Add Database Objects](add-database-objects.md)
- [Data Groups and Precomputed Q&As](data-groups-and-precomputed-qas.md)
- [Tool Functions](tool-functions.md)

[Back to Create Build-in AI Agent](create-build-in-ai-agent.md)
