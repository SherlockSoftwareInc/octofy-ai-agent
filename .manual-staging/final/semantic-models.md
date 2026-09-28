# Semantic Models

The **semantic layer** lets a built-in agent answer natural-language questions through a semantic model of the data source: the LLM emits a structured SMQ request that is compiled to physical SQL against the active semantic model (stored in the data source's `vector-index.db`).

## Enabling the semantic layer

- **Per agent**: in [AI Agent Manager](ai-agent-manager-window.md), a built-in agent has an **Allow semantic layer for this data source** checkbox (**Enable semantic layer routing for this built-in agent data source.**). When checked, the agent's data source uses the semantic layer. This is the setting that wins.
- **Per data source**: the embedded semantic model editor has an **Enable semantic layer for this data source** checkbox. This is the fallback switch, consulted when no owning agent resolves the setting.
- **Global fallback**: in [AI Settings](ai-settings.md) under **Semantic Options**, the **Allow semantic compile fallback to raw SQL** option controls whether semantic mode can fall back to raw SQL if SMQ parsing or compilation fails (when off, failures surface as errors instead of silently reverting).

The layer only engages when it is enabled **and** an active semantic model exists for the data source. If the layer is off, a model can still be saved — it simply will not be used for generation. Saving is also what initializes the semantic tables in `vector-index.db`.

## Viewing models

In the [Schema Library Form](schema-library-form.md), the tree has a **semantic-model** branch listing every model in the data source's vector database, newest first. Inactive models are labeled **(inactive)** but can still be opened and edited.

- Selecting the **semantic-model** folder shows a grid of every model with its **model_name**, **model_id** and **status** (`Active` or `Inactive`). Double-click a row to open that model in the embedded editor.
- Selecting a specific model node opens the embedded editor on that model.

## Adding a semantic model

Use **Semantic Model > Add**, or **Add Semantic Model** on the **semantic-model** node's right-click menu. A brand-new model (a fresh model id) opens in the embedded editor, added alongside existing models — it never overwrites one.

**Semantic Model > Remove** (or **Remove** on the node's right-click menu) deletes the selected model and its measures, dimensions, joins, governance predicates and embedding. The confirmation reads **Remove semantic model '*name*'? This permanently deletes the model and its embedding.** If no model is selected, the status bar asks you to select one.

## Editing and saving models

- The embedded **semantic model editor** shows the model's **Label**, its **Data Source Key**, an **Is active** checkbox, and tabs for **Measures**, **Dimensions**, **Joins** and **Governance**. Select a row to edit it in the **Selected item** area and click **Apply** to write the change back to the grid.
- **Compile preview** compiles the current model into physical SQL so you can check it before saving. At least one measure is required for a preview; a failure is reported as **Compile failed: *stage* - *message***.
- Models **auto-save** asynchronously when you leave the editor or close the form, because saving may call the embedding endpoint. While a save is in flight, further changes are coalesced into one follow-up save so the latest state always wins. The status bar reports **Semantic model saved.** on success, and the matching tree node text is refreshed afterwards; a brand-new model also rebuilds the tree so it appears in the list.
- A model that carries no measures cannot be saved; the editor reports **At least one measure is required.** Dimensions must name their table and column, and joins are required when dimensions span multiple tables.

## Creating a model from a query

In the [Add to Knowledge Base](add-to-knowledge-base.md) dialog, check **Build a semantic model from this query** to extract a model from a SQL question (LLM-first with a SQL-parse fallback) and review it in the pre-seeded **Edit Semantic Model** dialog before saving.

## Merging across runs and conflicting definitions

- A semantic model built by [Learn from Past Projects](learn-from-past-projects.md) is **merged into the data source's existing active model** and saved under the same model id, so repeated ingestion runs accumulate knowledge instead of leaving an older model shadowed. The same model therefore grows as more projects are ingested.
- When a run's definition of a measure, dimension or join disagrees with the stored one, the disagreement is **escalated, not overwritten**: the affected item alone is blocked, every candidate definition and the file that stated it are kept for review, and the run counts the conflict and records it in its quarantine ledger. Nothing is silently renamed or suffixed, so a metric never changes meaning without a visible decision.
- Distilling staged knowledge re-points dimensions at the raw table and column and re-ranks the rules that become governance predicates, then merges the result into the model the same way.

## Related topics

- [Schema Library Form](schema-library-form.md)
- [AI Agent Manager Window](ai-agent-manager-window.md)
- [AI Settings](ai-settings.md)
- [Add to Knowledge Base](add-to-knowledge-base.md)

[Back to Create Build-in AI Agent](create-build-in-ai-agent.md)
