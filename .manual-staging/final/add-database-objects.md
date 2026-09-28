# Add Database Objects

You can add more tables, views, and functions to the schema library without rebuilding everything. This is useful when the database grows or when the initial [Create a Build-in AI Agent](create-build-in-ai-agent.md) flow covered only a subset of objects.

## How to add objects

In the [Schema Library Form](schema-library-form.md), open **Schemas > Add objects**.

1. The **Database Objects Selector** opens for the current connection. Filter by **Object Type** (`All`, `Table`, `View`, `Function`) and by **Schema**, search by name with **Filter** (clear with **X**), and move objects with **>** / **>>** / **<** / **<<** (or double-click an item). **Open Table Schema** (`F4`) and **Preview Data** (`F8`) are available from the toolbar or the right-click menu to inspect an object before adding it.
2. Click **OK** to add the selected objects.

## What happens next

- Selected objects are deduplicated by type + `schema.name`.
- Objects already present in the library are skipped, except **functions**, which are always (re)built.
- If nothing new is selected, the status bar reports **No new objects selected. All selected objects already exist.** and the operation stops. If the selector returns no objects at all, an informational message asks you to select at least one object.
- Otherwise the connection's schema metadata is reloaded and a **scoped rebuild** runs for only the newly added objects (progress in the status bar and the marquee progress bar), then the data source keywords are refreshed.
- The library tree is refreshed, the first newly added object is selected, and the **Review Checklist** is shown if the build produced review items.

## Notes

- Requires an active database connection and a loaded schema library folder; without either, the command reports it in the status bar.
- While the rebuild runs, the **Rebuild**, **Sync**, **Rebuild Vector Index**, and **Value Index** commands are disabled and the tree and editors are locked.
- Existing object metadata (descriptions, keywords, usage examples) is preserved for objects already in the library.

## Related topics

- [Schema Library Form](schema-library-form.md)
- [Sync and Rebuild](sync-and-rebuild.md)
- [Browse and Edit Schema Content](browse-and-edit-schema-content.md)

[Back to Create Build-in AI Agent](create-build-in-ai-agent.md)
