# Sync and Rebuild

The [Schema Library Form](schema-library-form.md) keeps the schema library in step with the live database through two operations: **Sync** (incremental) and **Rebuild** (regeneration). Both respect the current tree selection so you can scope them to a single object, a single schema, or the whole data source.

## Scope follows selection

| Current selection | Scope |
| --- | --- |
| Object node (table/view/function) | That object only. |
| Schema node | That schema only. |
| Data source (root) node | The schema collection only — schemas and their object lists are refreshed without rewriting every object. |
| Anything else (folder, search result) | Full data source. |

## Sync (File > Sync)

An incremental synchronization. It starts by reloading the connection's schema metadata, then runs one of:

1. **Sync object** — for an object node. The object's markdown is regenerated.
2. **Sync schema** — for a schema node.
3. **Sync** (full) — for every other selection.

New objects are added, changed metadata is updated, and objects that no longer exist are removed. Existing markdown is kept wherever possible, so an incremental sync is the lighter option after small schema changes. The tree is refreshed and the previous selection restored.

No confirmation is required; the status bar reports progress and the completed counts (**Sync completed. Added: n, Updated: n, Removed: n.**). A wait cursor is shown while the operation runs.

## Rebuild (File > Rebuild)

A full regeneration of the selected scope:

1. Reloads the connection's schema metadata.
2. Shows a confirmation prompt naming the scope ("*Rebuild object 'schema.object'* / *Rebuild schema 'schema'* / *Rebuild full schema library* may take a while, especially on large databases. Do you want to continue?").
3. Runs the matching rebuild with progress in the status bar and the marquee progress bar. A full rebuild rewrites object markdown and reports the added/updated/removed counts.
4. After a **full** rebuild, the **Review Checklist** dialog is shown with items that need attention.

If the library folder does not exist yet, the form asks whether to build it now and runs an initial full build instead, then reports **Schema library created. Added: n.** and shows the review checklist.

Rebuild is disabled while a rebuild, sync, vector rebuild, or batch operation is running, and during that time the tree, the preview grid, and the object and data-group editors are locked as well.

## Review Checklist (View > Review Check List, Ctrl+R)

Re-opens the review items for the current library at any time. If no review items exist, an informational message is shown. The checklist collects items from the library on disk — for example objects whose descriptions could not be generated, schemas missing a purpose, missing data-source fields, unknown data coverage, missing keywords, function usage examples that still contain placeholders, and precomputed Q&A pairs that still need review and approval.

## Related topics

- [Schema Library Form](schema-library-form.md)
- [Add Database Objects](add-database-objects.md)
- [Rebuild the Vector Index](rebuild-vector-index.md)
- [Browse and Edit Schema Content](browse-and-edit-schema-content.md)

[Back to Create Build-in AI Agent](create-build-in-ai-agent.md)
