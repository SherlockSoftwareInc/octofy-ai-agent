# Manage Library Folder & Vector Database

The [Schema Library Form](schema-library-form.md) offers two commands to work with the library's storage directly.

## Where the library lives

Each built-in agent's schema library is a folder under the data-sources root (`%APPDATA%\Sherlock Software Inc\Octofy\skills\data-sources`):

- `{database}_{server}` (lowercased, non-alphanumeric characters removed) for SQL Server connections,
- `{DSN}_ODBC` for ODBC connections,
- other DBMS types add their type as a suffix to the `{database}_{server}` name.

An agent can also be pointed at an assigned folder of its own, in which case that folder is used instead.

The folder holds:

- the markdown content (`schemas/`, `data-groups/`, `tools/`),
- the index files (`.schema-index.json`, `schemas/<schema>/.object-index.json`, `data-groups/.data-group-index.json`),
- the data source metadata (`_data-source.md`),
- the vector database (`vector-index.db`),
- the knowledge base learned from past projects (`kb/`, including the `kb/wiki/` staging library).

## Open Schema Library Folder (File > Open Schema Library Folder)

Opens the current schema library folder in File Explorer so you can inspect or manage files directly. If no library folder is loaded, the status bar reports that the folder is unavailable.

## Open Vector Database (File > Open Vector Database)

Opens the **Vector Collection Viewer** for the data source's `vector-index.db`:

- The left list shows the vector **collections** in the database. Implementation details are hidden — the connector's internal vector tables and their shadow tables, the vector caches and maps, and the embedding cache are not listed, so what you see is the content you can act on.
- Select a collection to view its records in a grid.
- **Edit** — edit the selected record in a grid editor. For few-shot collections, the question and SQL are required.
- **Delete** — delete the selected record (with confirmation; this cannot be undone). A few-shot record is deleted through the knowledge-base store, so its scalar row and its vector row go together.

If the `vector-index.db` file does not exist, an informational message shows the expected path.

> **Caution:** this viewer operates directly on the vector database. Editing or deleting records can affect the built-in agent's retrieval behavior. Prefer the normal editors in the [Schema Library Form](schema-library-form.md) for everyday changes.

## What the vector database contains

`vector-index.db` is one SQLite file per data source, and it now holds every retrieval channel the built-in agent uses:

- **Schema objects** — one discovery row per table/view plus one per column, used to find candidate objects; the full schema payload is still resolved from the markdown files on disk, which remain the source of truth.
- **Few-shot examples** — the question/SQL pairs added through **Add Knowledge Base** (see [Add to Knowledge Base](add-to-knowledge-base.md)) and by script ingestion.
- **Value index** — representative data values extracted from legacy scripts, used to map the terms people use onto the values actually stored.
- **Data groups** — each group's name, description, keywords and member objects, with its cached vectors; these are what group-aware discovery reads.
- **Precomputed Q&As** — the reviewed question/SQL pairs per data group, each with its status. Only approved pairs are searched at query time.
- **Semantic models** — measures, dimensions, joins and governance predicates, plus the searchable embedding of each model.
- **The embedding cache** — a persistent cache of text-to-vector results, capped and evicted least-recently-used first, so repeated ingestion does not pay for the same embedding twice.

Collections labelled with a `vec_` prefix or a `_vec0` suffix in the viewer are vector-store implementation tables; their scalar content is shown in the corresponding plain collection.

## Related topics

- [Schema Library Form](schema-library-form.md)
- [Rebuild the Vector Index](rebuild-vector-index.md)
- [Browse and Edit Schema Content](browse-and-edit-schema-content.md)

[Back to Create Build-in AI Agent](create-build-in-ai-agent.md)
