# Data Groups and Precomputed Q&As

A **data group** is a business-focused grouping of database objects (for example, "Sales Orders" grouping the orders, customers, and invoice tables). Each group has a markdown file under `data-groups/`, an entry in `.data-group-index.json`, and a set of **precomputed Q&As** — reviewed question/answer/SQL pairs that the built-in agent can reuse directly or as few-shot context.

## New data group (Data Group > New data group)

1. Enter a group name — letters, digits, spaces, `_` and `-` only; must not already exist (checked against the index and file names).
2. Select member objects in the **Database Objects Selector** (at least one is required).
3. The description and keywords are generated automatically from the group name and members.
4. If the LLM provider is configured, initial **precomputed Q&A pairs** are generated for the group.
5. The group's markdown file and `.data-group-index.json` are created and the tree is refreshed with the new group selected.

The toolbar **New** button and the tree context menu **Add** create a data group the same way.

## Editing a data group

Select a data-group file node to open the embedded **data group editor** (description, category, keywords, members, business rules). While it is active, the **Data Group** menu offers:

- **Add objects** — add more member objects.
- **Remove** — remove the selected member.
- **Generate keywords** — regenerate keywords from the group name and members.

Changes are saved to the markdown file and index when you navigate away or close.

## Manage Anticipated Questions (Data Group > Manage Anticipated Questions)

Opens the **Review Q&A Pairs** dialog for the selected data group:

- A grid lists the group's precomputed Q&A pairs.
- Select a pair to edit its **Question** and **SQL** in the editor below.
- Set the pair's **status**: `Pending`, `Approved`, `Modified`, or `Error`.
- **Save** persists the pairs to the group's index.

## Precomputed Q&A review panel

The same pair-management functionality is available inside the schema library (used by the agent wizard's review step and by the data-group flow). For the selected data group you can:

- **Generate** — ask AI for more pairs (10 per click).
- **Approve** — mark the selected pair as approved and sync it.
- **Auto-approve** — have AI verify every pending pair against the group's member objects, approving those that generate valid SQL and regenerating the rest (requires AI settings and at least one member).
- **Regenerate SQL** — regenerate the SQL for the selected pair; the status is reset to `Pending` for review.
- **Verify** — re-check the pair with AI.
- **Delete** — remove the selected pair.
- **New** — add a blank pair.
- Edit the question/SQL and set the status directly; manual edits mark the pair as `Modified`.

Statuses are persisted to the group's precomputed query index and the vectors are re-synced.

## Sync Vectors (Data Group > Sync Vectors)

A foreground reconcile of every data group and its coupled precomputed queries into the vector tables. The status bar reports the number of data groups and queries synced. It is a no-op when embedding settings are not configured.

## Related topics

- [Schema Library Form](schema-library-form.md)
- [Learn from Past Projects](learn-from-past-projects.md)
- [Create a Build-in AI Agent](create-build-in-ai-agent.md)

[Back to Create Build-in AI Agent](create-build-in-ai-agent.md)
