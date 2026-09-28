# Manage Library Folder & Vector Database

The [Schema Library Form](schema-library-form.md) offers two commands to work with the library's storage directly.

## Where the library lives

Each built-in agent's schema library is a folder under the data-sources root:

- `{database}_{server}` (lowercased, non-alphanumeric characters removed) for SQL Server connections,
- `{DSN}_ODBC` for ODBC connections.

The folder contains the markdown content (`schemas/`, `data-groups/`, `tools/`), the index files (`.schema-index.json`, `.object-index.json`, `.data-group-index.json`), the data source metadata (`_data-source.md`), and the vector database (`vector-index.db`).

## Open Schema Library Folder (File > Open Schema Library Folder)

Opens the current schema library folder in File Explorer so you can inspect or manage files directly. If no library folder is loaded, the status bar reports that the folder is unavailable.

## Open Vector Database (File > Open Vector Database)

Opens the **Vector Collection Viewer** for the data source's `vector-index.db`:

- The left list shows the vector **collections** in the database (internal support tables and shadow tables are hidden).
- Select a collection to view its records in a grid.
- **Edit** — edit the selected record in a grid editor. For few-shot collections, the question and SQL are required.
- **Delete** — delete the selected record (with confirmation; this cannot be undone).

If the `vector-index.db` file does not exist, an informational message shows the expected path.

> **Caution:** this viewer operates directly on the vector database. Editing or deleting records can affect the built-in agent's retrieval behavior. Prefer the normal editors in the [Schema Library Form](schema-library-form.md) for everyday changes.

## Related topics

- [Schema Library Form](schema-library-form.md)
- [Rebuild the Vector Index](rebuild-vector-index.md)
- [Browse and Edit Schema Content](browse-and-edit-schema-content.md)

[Back to Create Build-in AI Agent](create-build-in-ai-agent.md)
