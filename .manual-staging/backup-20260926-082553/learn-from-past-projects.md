# Learn from Past Projects

**Learn from Past Projects** ingests a folder of legacy SQL scripts into the schema library so a built-in agent can learn from queries written in past projects. It is available from the [Schema Library Form](schema-library-form.md): **File > Learn from Past Projects**.

## How to use it

1. **Select the scripts folder** — click **Browse** and pick the folder containing the legacy SQL scripts.
2. Optionally check **Include subfolders** (checked by default) to recurse into subdirectories.
3. Optionally enter **Additional instructions** (up to 1000 characters) to guide how the scripts are interpreted.
4. Click **Start**.

## Requirements

- A schema library must be loaded (the command is disabled otherwise).
- The LLM provider must be configured in [AI Settings](ai-settings.md) — the ingestion parses and analyzes scripts with AI, so a warning is shown if it is not.

## What happens during ingestion

- The selected folder is scanned for SQL script files.
- Each script is analyzed and the results are written into the schema library:
  - **Q&A pairs** — question/answer pairs derived from the scripts.
  - **Few-shot examples** — example queries used to guide later SQL generation.
  - **Value mappings** — column value mappings found in the scripts.
  - **Skill files** — markdown skill files describing how to work with the objects.
  - **Semantic models** — semantic model extractions for applicable queries (see [Semantic Models](semantic-models.md)).
- A progress log shows per-file status; you can **Cancel** at any time.
- When finished, a summary reports the counts for each artifact type, and an **Open folder** link lets you inspect the library folder.

## Related topics

- [Schema Library Form](schema-library-form.md)
- [Data Groups and Precomputed Q&As](data-groups-and-precomputed-qas.md)
- [Semantic Models](semantic-models.md)
- [AI Settings](ai-settings.md)

[Back to Create Build-in AI Agent](create-build-in-ai-agent.md)
