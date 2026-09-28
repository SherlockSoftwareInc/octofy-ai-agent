# Semantic Models

The **semantic layer** lets a built-in agent answer natural-language questions through a semantic model of the data source: the LLM emits a structured SMQ request that is compiled to physical SQL against the active semantic model (stored in the data source's `vector-index.db`).

## Enabling the semantic layer

- **Per agent**: in [AI Agent Manager](ai-agent-manager-window.md), a built-in agent has an **Enable semantic layer** checkbox. When checked, the agent's data source uses the semantic layer.
- **Global fallback**: in [AI Settings](ai-settings.md) under **Semantic Options**, the **Allow semantic compile fallback to raw SQL** option controls whether semantic mode can fall back to raw SQL if SMQ parsing or compilation fails (when off, failures surface as errors instead of silently reverting).

## Viewing models

In the [Schema Library Form](schema-library-form.md), the tree has a **semantic-model** branch listing every model in the data source's vector database, newest first. Inactive models are labeled **(inactive)** but can still be opened and edited.

- Selecting the **semantic-model** folder opens the embedded editor on the latest active model (or a fresh model when none exists).
- Selecting a specific model node opens the editor on that model.

## Adding a semantic model

Right-click the **semantic-model** node and choose **Add Semantic Model**. A brand-new model (a fresh model id) opens in the embedded editor, added alongside existing models — it never overwrites one.

## Editing and saving models

- The embedded **semantic model editor** edits the model's measures, dimensions, joins, and governance predicates.
- **File > Save Semantic Model** saves the model explicitly (enabled only while the editor is active).
- Models also **auto-save** asynchronously (saving may call the embedding endpoint). While a save is in flight, further changes are coalesced into one follow-up save so the latest state always wins; when the form closes with unsaved model changes, the final state is saved before the form closes.
- After a successful save, the matching tree node text is refreshed; a brand-new model triggers a tree rebuild so it appears in the list.

## Creating a model from a query

In the [Add to Knowledge Base](add-to-knowledge-base.md) dialog, check **Build a semantic model from this query** to extract a model from a SQL question (LLM-first with a SQL-parse fallback) and review it in the pre-seeded **Edit Semantic Model** dialog before saving.

## Related topics

- [Schema Library Form](schema-library-form.md)
- [AI Agent Manager Window](ai-agent-manager-window.md)
- [AI Settings](ai-settings.md)
- [Add to Knowledge Base](add-to-knowledge-base.md)

[Back to Create Build-in AI Agent](create-build-in-ai-agent.md)
