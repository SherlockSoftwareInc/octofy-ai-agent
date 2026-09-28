# Schema Library Form

The **Schema Library** form is the maintenance window for the local, searchable schema library that a built-in AI agent uses to discover database objects. It lets you view, edit, and maintain:

- **Schema and object metadata** — descriptions, keywords, column documentation, usage examples, and business rules for tables, views, and functions.
- **Data groups** — business-focused groupings of database objects with anticipated questions and precomputed queries.
- **Tool functions** — AI-callable function definitions stored in the library's `tools` folder.
- **Semantic models** — the semantic layer used by the built-in SQL generator, edited inline in the form.

The form also synchronizes and rebuilds the library from the live database, maintains the vector index used for semantic search, and offers AI-assisted description generation.

## Open the Schema Library Form

From **AI Agent Manager**:

1. Select **Build-in Agent**.
2. Click **Manage Schema Library**.

The form opens for the current database connection.

## Layout

The form has three main areas:

- **Menu bar** — **File**, **View**, **Edit**, **Column**, **Data Group**, and **AI Assistant** menus.
- **Toolbar** — quick access to creating data groups, editing (Cut/Copy/Paste), and AI description of the selected object.
- **Left panel** — the schema library tree for the current data source.
- **Right panel** — the content area. Depending on the tree selection it shows one of:
  - a text editor (Scintilla) for JSON index files and the data-source markdown file;
  - a grid preview of schema, data-group, or object index contents;
  - an embedded **database object editor** (tables/views/functions);
  - an embedded **data group editor**;
  - an embedded **tool function editor**; or
  - an embedded **semantic model editor**.
- **Status bar** — current file path, operation status, and messages from the embedded editors. A marquee progress bar appears while rebuilds, syncs, or batch operations run.

## Schema library tree

The left panel shows the library folder for the current connection (the folder name is the agent's `SchemaDataDirectory`, or `{database}_{server}` for SQL Server connections, or `{DSN}_ODBC` for ODBC connections) with the following branches:

| Node | Contents |
| --- | --- |
| **schemas** | One node per schema, each listing the schema's tables, views, and functions as file-backed nodes. |
| **data-groups** | One node per data group (a business grouping of objects with its own markdown file). |
| **tools** | One node per tool function definition file (`.md` under `tools/`). |
| **semantic-model** | One node per semantic model in the data source's vector database, newest first. Inactive models are labeled with **(inactive)**. |

## File menu

| Command | Description |
| --- | --- |
| **Open Schema Library Folder** | Opens the current schema library folder in File Explorer. Enabled when a library is loaded. |
| **Open Vector Database** | Opens a viewer for the data source's `vector-index.db` file. |
| **Add Database Objects** | Opens the **Database Objects Selector**; the selected objects (deduplicated by type + schema.name) are added to the library by rebuilding for just those objects. Objects already in the library are skipped unless they are functions. |
| **Sync** | Incrementally synchronizes the library with the database. Scope follows the current selection: selected object → sync that object; selected schema → sync that schema; otherwise full sync. |
| **Rebuild** | Rebuilds library content from the database. Scope follows the current selection (object / schema / full). A confirmation prompt warns that the rebuild can take a while, and progress is shown in the status bar. A review checklist of items needing attention is shown after a full rebuild. |
| **Rebuild vector index** | Rebuilds the vector index (`vector-index.db`) from the markdown files on disk. Confirmation is required; it is disabled while a rebuild is already running. |
| **Learn from Past Projects** | Opens the **Import Legacy Scripts** dialog to ingest legacy SQL scripts into the knowledge base. |
| **Add to Knowledge Base** | Opens the **Add to Knowledge Base** dialog for adding SQL questions to the library. For built-in agents with a configured vector database, checking **"Build a semantic model from this query"** extracts a semantic model from the query (LLM-first with SQL-parse fallback) and opens the **Edit Semantic Model** dialog pre-seeded for review. |
| **Save Semantic Model** | Saves the semantic model currently being edited. Only enabled while the semantic model editor is active. |
| **Exit** | Closes the form. |

## View menu

| Command | Description |
| --- | --- |
| **Review Checklist…** (`Ctrl+R`) | Opens the review items collected from the last build/sync operations (or re-collected from disk). Enabled when a library is loaded. |

## Edit menu

| Command | Description |
| --- | --- |
| **Undo** (`Ctrl+Z`) / **Redo** (`Ctrl+Y`) | Undo/redo in the active text editor. |
| **Cut** (`Ctrl+X`) / **Copy** (`Ctrl+C`) / **Paste** (`Ctrl+V`) | Clipboard operations. They target whichever control has focus: the tree panel, the text editor, the database object editor, or a text box. |
| **Select All** (`Ctrl+A`) | Selects all content in the active editor. |

## Column menu

| Command | Description |
| --- | --- |
| **Add Column Reference** | Adds a column reference to the currently edited database object. Enabled only while the database object editor is active. |

## Data Group menu

| Command | Description |
| --- | --- |
| **New data group** | Creates a new data group. Prompts for a name (letters, digits, spaces, `_`, `-`; must not already exist), then opens the **Database Objects Selector** to pick member objects. The description and keywords are generated automatically from the group name and members, and — when an LLM provider is configured — initial precomputed question/answer pairs are generated and stored with the group. |
| **Add objects** | Adds more objects to the currently edited data group. Enabled only while the data group editor is active. |
| **Remove** | Removes the selected object from the data group. Enabled only while the data group editor is active. |
| **Generate keywords** | Regenerates keywords for the data group from its name and members. Enabled only while the data group editor is active. |
| **Manage Anticipated Questions** | Opens the **Anticipated Questions** dialog for the selected data group. |
| **Sync Vectors** | Foreground reconcile of every data group and its coupled precomputed queries into the vector tables (no-op when embedding settings are not configured). |

## AI Assistant menu

These commands use the configured LLM provider to write or complete descriptions of database objects. They require a valid LLM provider (see [AI Settings](ai-settings.md)); otherwise a warning is shown.

| Command | Description |
| --- | --- |
| **Describe** | Describes the currently selected table or view (regenerates its description). |
| **Describe with…** | Describes the selected table or view using additional context you supply. |
| **Describe missing** | Fills in descriptions only where they are missing for the selected object. |
| **Batch Describe** | Describes every object in the library sequentially. You may optionally provide additional context. Progress is shown in the status bar and progress bar; failures on individual objects are reported but do not stop the batch. |

## Toolbar

| Button | Description |
| --- | --- |
| **New** | Create a new data group from selected objects (same as **Data Group > New data group**). |
| **Cut / Copy / Paste** | Clipboard operations for the active editor. |
| **Describe Missing** | Use AI to describe the selected table or view when its description is missing (same as **AI Assistant > Describe missing**). |

## Tree and content behavior

Selecting nodes in the left tree drives the content area:

| Selection | Content area |
| --- | --- |
| **schemas** folder | Grid preview of the schema index (schema name + description), sorted by name. |
| Schema node | Grid preview of that schema's object index (object name + type + description). |
| **data-groups** folder | Grid preview of the data-group index (group name + description). |
| **semantic-model** folder | Embedded semantic model editor on the latest active model (or a fresh model when none exists). |
| Semantic model node | Embedded semantic model editor on that specific model. Inactive models can still be opened and edited. |
| Object file node (table/view/function) | Embedded database object editor. |
| Data-group file node | Embedded data group editor. |
| Tool function file node | Embedded tool function editor. |
| `_data-source.md` | Text editor (the only markdown file that is editable as text; other `.md` files open in their dedicated editors). |
| JSON index file | Text editor with JSON syntax highlighting. |
| Root node / no file | Empty text surface. |

### Grid preview editing

In any grid preview, **double-click a row** (or right-click and choose **Edit item**) to edit the row's metadata:

- **Schema rows** — a dialog edits the schema description and keywords; `.schema-index.json` is updated.
- **Data-group rows** — a dialog edits description, keywords, members, and business rules; the group's markdown file and `.data-group-index.json` are regenerated.
- **Object rows** — a dialog edits description, usage example, keywords, and columns; the object's markdown file and `.object-index.json` are updated, and a background vector-index update is scheduled.

## Context menu (tree)

Right-clicking tree nodes offers context commands (in addition to the menu bar): **Open**, **Copy Name**, **Add** (data groups), **Manage Anticipated Questions** (data groups), **Edit Function Call Definition** / **Add Semantic Model** (on the semantic-model node — starts a brand-new model in the embedded editor), **Remove**, **Sync**, and **Rebuild**. Removing the root node or the top-level `schemas` / `data-groups` nodes is blocked.

## Save behavior

- **Text edits** are auto-saved when you switch selection or close the form.
- **Database object editor** changes are saved to the object index and the object's markdown file; a background vector-index update is scheduled for changed object files.
- **Data group editor** changes are saved to `.data-group-index.json` and the group's markdown file.
- **Tool function editor** changes are saved to the tool function definition.
- **Semantic model** edits are saved asynchronously (saving may call the embedding endpoint). While a save is in flight, further changes are coalesced into one follow-up save so the latest state always wins; when the form closes with unsaved model changes, the final state is saved before the form closes.

## First-time setup

When no schema library folder exists for the connection:

1. The form creates the data source folder structure (`_data-source.md`, `.schema-index.json`, `schemas/`, `data-groups/`) and registers it in the catalog `_index.md`.
2. A basic library is built from the live database, then a full rebuild runs automatically with progress shown in the status bar.
3. After the build, the review checklist is shown if any items need attention.

If the library folder already exists but the data source metadata is outdated, the form repairs it automatically (for example, injecting the missing `source_id` front matter or converting an old inline `**Description:**` field into a `## Description` section).

## Related topics

- [Create a Build-in AI Agent](create-build-in-ai-agent.md) — the wizard that creates an agent and its initial schema library.
- [AI Agent Manager Window](ai-agent-manager-window.md) — where the Schema Library form is opened from, and per-agent configuration.
- [AI Settings](ai-settings.md) — the LLM and embedding provider settings used by the AI Assistant commands, vector index, and semantic model saving.
- [Add Data Source](add-data-source.md) — creating the database connection this form operates on.
- [Application Options Dialog](application-options-dialog.md) — application-wide options.

### Feature topics

- [Browse and Edit Schema Content](browse-and-edit-schema-content.md) — tree navigation, editors, grid previews, and metadata editing.
- [Add Database Objects](add-database-objects.md) — add more tables/views/functions to the library.
- [Sync and Rebuild](sync-and-rebuild.md) — keep the library in step with the database.
- [Rebuild the Vector Index](rebuild-vector-index.md) — rebuild `vector-index.db` from the markdown files.
- [Learn from Past Projects](learn-from-past-projects.md) — ingest legacy SQL scripts.
- [Data Groups and Precomputed Q&As](data-groups-and-precomputed-qas.md) — business groupings and precomputed question/answer pairs.
- [Tool Functions](tool-functions.md) — AI-callable function definitions.
- [AI-Assisted Descriptions](ai-assisted-descriptions.md) — AI-generated object descriptions.
- [Semantic Models](semantic-models.md) — the semantic layer for the built-in SQL generator.
- [Add to Knowledge Base](add-to-knowledge-base.md) — add SQL questions to the library.
- [Manage Library Folder & Vector Database](manage-library-folder-and-vector-db.md) — open the library folder and inspect the vector database.

[Back to Create Build-in AI Agent](create-build-in-ai-agent.md)

## Screenshot

![Schema Library form](images/Schema_Library.png)
