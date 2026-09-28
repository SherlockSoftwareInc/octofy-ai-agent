# Data Groups and Precomputed Q&As

A **data group** is a business-focused grouping of database objects (for example, "Sales Orders" grouping the orders, customers, and invoice tables). Each group has a markdown file under `data-groups/`, an entry in `.data-group-index.json`, and a set of **precomputed Q&As** — reviewed question/answer/SQL pairs that the built-in agent can reuse directly or as few-shot context. A group's business rules, metrics, description and keywords also travel with it into the agent's prompt context, which is how grouping steers discovery towards the right tables.

## New data group (Data Groups > Add)

1. Enter a group name — letters, digits, spaces, `_` and `-` only; must not already exist (checked against the index and file names). The prompt is **Enter name for the new data group:**.
2. Click **Select Objects** and pick member objects in the **Database Objects Selector** (at least one is required).
3. The description and keywords are generated automatically from the group name and members.
4. If the LLM provider is configured, initial **precomputed Q&A pairs** are generated for the group.
5. The group's markdown file and `.data-group-index.json` are created and the tree is refreshed with the new group selected.

The toolbar **New** button and the tree context menu **Add** on the **data-groups** node create a data group the same way.

> **Note:** the menu itself reads **Data Groups**; the individual item is **Add**, and the dialog that follows is titled **New Data Group**.
## Editing a data group

Select a data-group file node to open the embedded **data group editor**. It has a **Data Group** tab (name, category, description, keywords, member objects, and **Business Rules & Metrics**) and a **Q&As** tab for the group's precomputed pairs.

While the data group editor is active, the **Data Groups** menu offers:

- **Add Objects** — add more member objects.
- **Generate Keywords** — regenerate keywords from the group name and members.
- **Remove** — remove the group from the data-groups index (after a confirmation prompt). If no data group is selected, the status bar asks you to select one.

The member object list also has its own right-click menu with **Add objects** and **Remove** for individual members. Changes are saved to the markdown file and index when you navigate away or close.

## Manage Anticipated Questions (Data Groups > Manage Anticipated Questions)

Opens the **Review Q&A Pairs - *group*** dialog for the selected data group:

- A grid lists the group's precomputed Q&A pairs.
- Select a pair to edit its **Question** and **SQL** in the editor below.
- Set the pair's **Status**: `Pending`, `Approved`, `Modified`, or `Error`.
- **Save** persists the pairs to the group's index and closes; **Close** closes without saving.

The same dialog is available from the **Manage Anticipated Questions** command on a data-group node's right-click menu.

## Precomputed Q&A review panel

The same pair-management functionality is available inside the schema library (in the data group editor's **Q&As** tab, and in the agent wizard's review step). For the selected data group you can:

- **Add** — add a blank pair.
- **New by AI** — ask AI for more pairs. You may supply request details; the guidance is combined with the group's object metadata.
- **AI Auto Approve** — have AI verify every pending pair against the group's member objects, approving those that generate valid SQL and regenerating the rest. It requires AI settings, an active database connection, and at least one member; it reports progress as `Auto-approve progress: processed/total (approved: n, regenerated: n, pending: n)` and finishes with a count of approved, regenerated and still-pending pairs.
- **Open** — open the selected pair's SQL.
- **Verify** — re-check the pair with AI. The result states whether the SQL query is valid and whether it satisfies the question.
- **Regenerate** — regenerate the SQL for the selected pair; the status is reset to `Pending` for review.
- **Approve** — mark the selected pair as approved and sync it.
- **Delete** — remove the selected pair (with confirmation).
- Edit the question/SQL and set the status directly; manual edits mark the pair as `Modified`.

Statuses are persisted to the group's precomputed query index and the vectors are re-synced.

## How data groups steer the agent

- At query time the agent resolves the most relevant active data groups and uses their member objects, business rules and metrics as business context for discovery.
- Precomputed Q&As participate directly: a reviewed pair that matches the question closely enough is reused as the answer, and pairs that match less closely are injected as few-shot examples. Only pairs with the status `Approved` take part in vector search; the exact-question match also reads `Modified` pairs.
- A group whose members include a survivor of discovery anchors the result set to that group's objects.

## Sync Vectors (Data Groups > Sync Vectors)

A foreground reconcile of every data group and its coupled precomputed queries into the vector tables. The status bar reports **Synchronized *n* data group vector record(s) and *n* precomputed query vector record(s).** It is a no-op when embedding settings are not configured, in which case the status bar says the sync was skipped.

## Related topics

- [Schema Library Form](schema-library-form.md)
- [Learn from Past Projects](learn-from-past-projects.md)
- [Create a Build-in AI Agent](create-build-in-ai-agent.md)

[Back to Create Build-in AI Agent](create-build-in-ai-agent.md)
