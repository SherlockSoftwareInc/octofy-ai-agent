# Sync and Rebuild

The [Schema Library Form](schema-library-form.md) keeps the schema library in step with the live database through two operations: **Sync** (incremental) and **Rebuild** (regeneration). Both respect the current tree selection so you can scope them to a single object, a single schema, or the whole data source.

## Scope follows selection

| Current selection | Scope |
| --- | --- |
| Object node (table/view/function) | That object only. |
| Schema node | That schema only. |
| Anything else (folder/root) | Full data source. |

## Sync (File > Sync)

An incremental synchronization:

1. Reloads the connection's schema metadata.
2. Runs **Sync object**, **Sync schema**, or **Sync** (full) according to the selection.
3. Adds new objects, updates changed metadata, and removes objects that no longer exist.
4. Refreshes the tree and restores the previous selection.

No confirmation is required; progress is shown in the status bar.

## Rebuild (File > Rebuild)

A full regeneration of the selected scope:

1. Reloads the connection's schema metadata.
2. Shows a confirmation prompt naming the scope ("Rebuild can take a while… Do you want to continue?").
3. Runs **Rebuild object**, **Rebuild schema**, or **Rebuild** (full) with progress in the status bar and the marquee progress bar.
4. After a **full** rebuild, the **Review Checklist** dialog is shown with items that need attention.

Rebuild is disabled while a rebuild, sync, vector rebuild, or batch operation is running.

## Review Checklist (View > Review Checklist…, Ctrl+R)

Re-opens the review items for the current library at any time. If no review items exist, an informational message is shown. The checklist collects items from the library on disk (for example, objects whose descriptions could not be generated).

## Related topics

- [Schema Library Form](schema-library-form.md)
- [Add Database Objects](add-database-objects.md)
- [Rebuild the Vector Index](rebuild-vector-index.md)
- [Browse and Edit Schema Content](browse-and-edit-schema-content.md)

[Back to Create Build-in AI Agent](create-build-in-ai-agent.md)
