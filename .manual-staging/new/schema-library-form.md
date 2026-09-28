# Schema Library Form

The **Schema Library** form is the maintenance window for the local, searchable schema library that a built-in AI agent uses to discover database objects. It lets you view, edit, and maintain:

- **Schema and object metadata** — descriptions, keywords, column documentation, usage examples, and business rules for tables, views, and functions.
- **Data groups** — business-focused groupings of database objects with anticipated questions and precomputed queries.
- **Tool functions** — AI-callable function definitions stored in the library's `tools` folder.
- **Semantic models** — the semantic layer used by the built-in SQL generator, edited inline in the form.
- **Value indexes** — the distinct column values stored in the vector database for value-level search.

The form also synchronizes and rebuilds the library from the live database, maintains the vector index used for semantic search, offers AI-assisted description generation, and hosts an **AI Assistant** chat panel that can fill in the editor you are looking at.

## Open the Schema Library Form

From **AI Agent Manager**:

1. Select **Build-in Agent**.
2. Click **Manage Schema Library**.

The form opens for the current database connection. (While you are adding a brand-new agent the same button is labeled **Create Agent** and starts the [New Agent Wizard](create-build-in-ai-agent.md) instead.)

## Layout

The form has six main areas:

- **Menu bar** — **File**, **View**, **Edit**, **Schemas**, **Data Groups**, **Tools/Functions**, **Semantic Model**, and **Value Index** menus.
- **Toolbar** — **New** data group, **Cut** / **Copy** / **Paste**, **Describe Missing**, and — right-aligned — the **AI Assistant** toggle.
- **Left panel** — the schema library tree for the current data source, with a search box.
- **Right panel** — the content area. Depending on the tree selection it shows a text editor (Scintilla) for `_data-source.md` and JSON index files; a read-only grid preview of the schema index, a schema's objects, the data-group index, the tool functions, the semantic models, or one column's indexed values; an embedded **database object editor** (tables/views/functions); an embedded **data group editor**; an embedded **tool function editor**; or an embedded **semantic model editor**.
- **AI Assistant panel** — the schema-library assistant, docked to the right and collapsed when the form opens. Click **AI Assistant** on the toolbar to show or hide it.
- **Status bar** — current file path, operation status, and messages from the embedded editors. A marquee progress bar appears while rebuilds, syncs, or batch operations run.

## Schema library tree

The left panel shows the library folder for the current connection (the folder name is the agent's `SchemaDataDirectory`, or `{database}_{server}` for SQL Server connections, `{DSN}_ODBC` for ODBC connections, or `{database}_{server}_{dbms}` for other database types) with the following branches:

| Node | Contents |
| --- | --- |
| **schemas** | One node per schema, each listing the schema's tables, views, and functions as file-backed nodes. Expanding a table or view node loads one child node per column that has a **value index**. |
| **data-groups** | One node per data group (a business grouping of objects with its own markdown file). |
| **tools** | One node per tool function definition file (`.md` under `tools/`). |
| **semantic-model** | One node per semantic model in the data source's vector database, newest first. Inactive models are labeled with **(inactive)**. |

Expanding a table or view node for the first time shows **Loading...** and then either the indexed columns (each with a tooltip like `schema.table.column - n value(s)`) or the status message **No value index columns for ...**. An object without indexed columns simply stays a leaf.

## File menu

| Command | Description |
| --- | --- |
| **Open Schema Library Folder** | Opens the current schema library folder in File Explorer. Enabled when a library is loaded. |
| **Open Vector Database** | Opens a viewer for the data source's `vector-index.db` file. Enabled when a library is loaded; an information box shows the expected path when the file does not exist yet. |
| **Add Knowledge Base** | Opens the **Add to Knowledge Base** dialog for adding SQL questions to the library. For built-in agents with a configured vector database, checking **"Build a semantic model from this query"** extracts a semantic model from the query (LLM-first with SQL-parse fallback) and opens the **Edit Semantic Model** dialog pre-seeded for review. |
| **Sync** | Incrementally synchronizes the library with the database. Scope follows the current selection: selected object → that object; selected schema → that schema; otherwise full sync. |
| **Rebuild** | Rebuilds library content from the database. Scope follows the current selection (object / schema / full). A confirmation prompt names the scope and warns that the rebuild can take a while, and progress is shown in the status bar. A review checklist of items needing attention is shown after a full rebuild. |
| **Rebuild Vector Index** | Rebuilds the vector index (`vector-index.db`) from the markdown files on disk. Confirmation is required; it is disabled while a rebuild is already running. |
| **Learn from Past Project** | Opens the **Learn from Past Projects** dialog to ingest legacy SQL scripts into the knowledge base. |
| **Exit** | Closes the form. |

## View menu

| Command | Description |
| --- | --- |
| **Review Check List** (`Ctrl+R`) | Opens the review items collected from the last build/sync operations (or re-collected from disk). Enabled when a library is loaded; when nothing was collected, an information box reports that no review items were found. |
| **AI Assistant** | Shows or hides the AI Assistant panel (same as the toolbar toggle). |

## Edit menu

| Command | Description |
| --- | --- |
| **Cut** (`Ctrl+X`) / **Copy** (`Ctrl+C`) / **Paste** (`Ctrl+V`) | Clipboard operations. They target whichever control has focus: the tree panel, the text editor, the database object editor, or a text box. |

## Schemas menu

| Command | Description |
| --- | --- |
| **Add objects** | Opens the **Database Objects Selector**; the selected objects (deduplicated by type + schema.name) are added to the library by rebuilding for just those objects. Objects already in the library are skipped unless they are functions. |
| **Add Column Reference** | Adds a column reference to the currently edited database object. Enabled only while the database object editor is active. |
| **AI Describe** | Describes the currently selected table or view (regenerates its description). |
| **AI Batch Describe** | Describes every object in the library sequentially. You may optionally provide additional context. |

## Data Groups menu

| Command | Description |
| --- | --- |
| **Add** | Creates a new data group. Prompts for a name (up to 64 characters, letters, digits, spaces, `_`, `-`; must not already exist), then opens the **Database Objects Selector** to pick member objects. The description and keywords are generated automatically from the group name and members, and — when an LLM provider is configured — initial precomputed question/answer pairs are generated and stored with the group. |
| **Remove** | Removes the data group currently selected in the tree from the library, after a confirmation prompt. Enabled only when a data-group node is selected. |
| **Add Objects** | Adds more objects to the currently edited data group. Enabled only while the data group editor is active. |
| **Generate Keywords** | Regenerates keywords for the data group from its name and members. Enabled only while the data group editor is active. |
| **Manage Anticipated Questions** | Opens the **Anticipated Questions** dialog for the selected data group. |
| **Sync Vectors** | Foreground reconcile of every data group and its coupled precomputed queries into the vector tables (a "not configured" message is shown when embedding settings are absent). |

## Tools/Functions menu

| Command | Description |
| --- | --- |
| **Add** | Opens the modal **tool function editor** to define a new AI-callable tool. Enabled when a library is loaded. |
| **Remove** | Removes the tool function currently selected in the tree, after a confirmation prompt. Enabled only when a tool function node is selected. |

## Semantic Model menu

| Command | Description |
| --- | --- |
| **Add** | Starts a **brand-new** semantic model in the embedded semantic model editor. Enabled when a library is loaded. |
| **Remove** | Removes the semantic model currently selected in the tree, including its measures, dimensions, joins, governance predicates, and embedding, after a confirmation prompt. Enabled only when a semantic model node is selected. |

## Value Index menu

| Command | Description |
| --- | --- |
| **Add** | Opens the **value index column selector**; for every selected column the distinct non-blank values read from the database replace the column's records in the value index. Requires a configured embedding provider. |
| **Remove** | Opens the **value index column selector** and, after a confirmation prompt, removes the selected columns' value index records. Requires a configured embedding provider. |

## AI Assistant (chat panel)

The **AI Assistant** panel is the schema-library editor assistant. It is collapsed when the form opens and is opened with the toolbar toggle or **View > AI Assistant**. It requires a configured LLM provider; the first time it opens in a session, the app asks for permission if "allow AI to analyze real data" has not been enabled yet.

- The assistant follows your tree selection: the currently open editor (database object, data group, tool function, or semantic model) and its file content are sent as context on every turn.
- When you ask it to fill in an editor, it returns a single action that the form applies to the **embedded editor on screen** — for example populating tool function settings, updating a description/business rules/usage example, appending precomputed questions, or adding semantic model synonyms and mappings.
- The action must match the editor that is active, otherwise the assistant reports that the action does not match the active editor.
- Apart from appended precomputed questions (stored immediately), the actions only change the editor on screen — review the values and let the normal save behavior persist them.

The three AI description commands in the **Schemas** menu (**AI Describe**, **AI Batch Describe**, and the toolbar **Describe Missing**) also require a valid LLM provider (see [AI Settings](ai-settings.md)); otherwise a warning is shown.

## Toolbar

| Button | Description |
| --- | --- |
| **New** | Create a new data group: prompts for a name and creates an empty group markdown file and index entry (no object selection and no Q&A generation). |
| **Cut / Copy / Paste** | Clipboard operations for the active editor. |
| **Describe Missing** | Use AI to describe the selected table or view when its description is missing. The object's description, usage example, keywords, and columns are filled in where empty; other content is left alone. |
| **AI Assistant** | Shows or hides the AI Assistant panel. |

## Tree and content behavior

Selecting nodes in the left tree drives the content area:

| Selection | Content area |
| --- | --- |
| **schemas** folder | Grid preview of the schema index (**schema_name** + **description**), sorted by name. |
| Schema node | Grid preview of that schema's object index (**object_name** + **object_type** + **description**). |
| **data-groups** folder | Grid preview of the data-group index (**group_name** + **description**). |
| **tools** folder | Grid preview of the tool function definitions (**tool_name** + **protocol** + **description**), one row per file in `tools/`. |
| **semantic-model** folder | Grid preview of every model in the vector database (**model_name** + **model_id** + **status**, where status is **Active** or **Inactive**). The status bar shows the `vector-index.db` path. |
| Semantic model node | Embedded semantic model editor on that specific model. Inactive models can still be opened and edited. |
| Object file node (table/view/function) | Embedded database object editor. |
| Value-index column node (child of a table/view) | Grid preview of the values indexed for that column (a **Value** column). |
| Data-group file node | Embedded data group editor. |
| Tool function file node | Embedded tool function editor. |
| `_data-source.md` | Text editor. |
| JSON index file | Text editor with JSON syntax highlighting. |
| Markdown file with no editor | Read blocked: an empty text surface with the status message **Read blocked for markdown: ...**. Only `_data-source.md` is editable as text; other `.md` files open in their dedicated editors. |
| Root node / no file | Empty text surface. |

### Grid preview editing

In the schema, object, and data-group grid previews, **double-click a row** (or right-click and choose **Edit Item**) to edit the row's metadata:

- **Schema rows** — a dialog edits the schema description and keywords; `.schema-index.json` is updated.
- **Data-group rows** — a dialog edits description, keywords, members, and business rules; the group's markdown file and `.data-group-index.json` are regenerated.
- **Object rows** — a dialog edits description, usage example, keywords, and columns; the object's markdown file and `.object-index.json` are updated, and a background vector-index update is scheduled.

In the tool function and semantic model list previews, **double-click a row** (or **Edit Item**) opens that entity's embedded editor panel. The value-index values preview is read-only.

## Context menu (tree)

Right-clicking tree nodes offers context commands (in addition to the menu bar): **Open**, **Copy Name**, **Add** (on the `data-groups` and `tools` folder nodes), **Manage Anticipated Questions** (data groups), **Edit Function Call Definition** (tool functions, opens the modal tool function editor), **Add Semantic Model** (on the `semantic-model` node — starts a brand-new model in the embedded editor), **Remove**, **Sync**, and **Rebuild**. Removing the root node or the top-level `schemas` / `data-groups` nodes is blocked.

## Save behavior

- **Text edits** are auto-saved when you switch selection or close the form. A save attempt on a read-blocked markdown file is refused.
- **Database object editor** changes are saved to the object index and the object's markdown file; a background vector-index update is scheduled for changed object files.
- **Data group editor** changes are saved to `.data-group-index.json` and the group's markdown file.
- **Tool function editor** changes are saved to the tool function definition.
- **Semantic model** edits are saved asynchronously (saving may call the embedding endpoint). While a save is in flight, further changes are coalesced into one follow-up save so the latest state always wins; when the form closes with unsaved model changes, the final state is saved before the form closes. There is no separate save command for the semantic model editor.

## First-time setup

When no schema library folder exists for the connection:

1. The form creates the data source folder structure (`_data-source.md`, `.schema-index.json`, `schemas/`, `data-groups/`, `.data-groups`) and registers it in the catalog `_index.md`.
2. A basic library is built from the live database, and the form then starts a full rebuild automatically — including its confirmation prompt.
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
