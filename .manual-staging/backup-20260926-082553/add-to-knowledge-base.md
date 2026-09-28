# Add to Knowledge Base

**Add to Knowledge Base** adds a SQL question and its query to the schema library so the built-in agent can reuse it. It is available from the [Schema Library Form](schema-library-form.md): **File > Add to Knowledge Base**.

## How to use it

1. Open **File > Add to Knowledge Base**.
2. In the **Add to Knowledge Base** dialog, enter the **question** and the **SQL**.
3. For built-in agents, the **Build a semantic model from this query** checkbox is available (disabled for Octofy Agent mode and when no vector database directory is set). Check it to also extract a semantic model from the query.
4. Click **Add**.

## Agent mode behavior

- **Octofy Agent**: the dialog uses the agent's endpoint and API key.
- **Built-in Agent**: the dialog uses the data source's library folder (the vector database directory) as the target.

## Building a semantic model from the query

When the checkbox is checked:

1. The query is extracted into a semantic model — LLM-first, with a SQL-parse fallback — covering measures, dimensions, joins, and tables.
2. The **Edit Semantic Model** dialog opens pre-seeded with the extracted model for review and adjustment.
3. Saving the dialog persists the model to the data source's vector database and refreshes the library tree (the model appears under the **semantic-model** node).

See [Semantic Models](semantic-models.md) for more about models.

## Related topics

- [Schema Library Form](schema-library-form.md)
- [Semantic Models](semantic-models.md)
- [Data Groups and Precomputed Q&As](data-groups-and-precomputed-qas.md)

[Back to Create Build-in AI Agent](create-build-in-ai-agent.md)
