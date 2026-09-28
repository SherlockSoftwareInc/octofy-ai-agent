# Rebuild the Vector Index

The schema library's **vector index** (`vector-index.db`, stored inside the data source folder) powers semantic search over the schema markdown. Normally it is updated automatically — changed object files trigger a background vector update — but you can rebuild it entirely from the markdown files on disk.

## How to rebuild

In the [Schema Library Form](schema-library-form.md), open **File > Rebuild vector index**.

1. A confirmation prompt shows the data source folder name and explains that the rebuild regenerates the index from the markdown files.
2. The rebuild runs with the marquee progress bar and status messages; the menu is disabled while it runs.
3. The result is reported in the status bar: the number of objects indexed, or a "no objects" message when nothing was indexed.

## When to use it

- After bulk changes to object markdown files outside the form.
- When you suspect the index is out of sync with the library content.
- After changing embedding settings (see [AI Settings](ai-settings.md) — existing vectors may not match the new embedding configuration).

## Notes

- Requires a loaded schema library folder; otherwise the command reports that no library folder is loaded.
- The rebuild reads the markdown files under the data source folder and re-embeds them using the configured embedding provider.
- You can cancel with **No** at the confirmation; the operation itself cannot be cancelled once started (the marquee progress bar runs until completion).

## Related topics

- [Sync and Rebuild](sync-and-rebuild.md)
- [Schema Library Form](schema-library-form.md)
- [Manage Library Folder & Vector Database](manage-library-folder-and-vector-db.md)

[Back to Create Build-in AI Agent](create-build-in-ai-agent.md)
