# Create a Build-in AI Agent

This section explains how to create a **Build-in Agent** for a data source. A built-in agent runs inside Octofy and uses the app's global AI provider settings; its knowledge comes from a local **schema library** that is built from your database and maintained in the [Schema Library Form](schema-library-form.md).

You can start the flow from either:

- **Add new DB Connection**, or
- **Manage DB Connections**.

## Before You Start

- Configure the LLM and embedding endpoints in **AI Assistant > AI Settings** (see [AI Settings](ai-settings.md)).
- Have an active database connection for the data source you want the agent to work with.

---

## Start from Add New DB Connection

1. Open **File** -> **Add new DB Connection**.
2. In **New Connection Dialog**, enter your connection details.
3. In the **Octofy AI Agent** section, click **Add New Agent**.
4. In **AI Agent Manager**, click **New** and select agent type **Build-in Agent**.
5. Click **Create Agent** — because no agent exists for this connection yet, the **New Agent Wizard** opens to create the agent and its schema library in one guided flow.
6. Follow the wizard steps below.
7. Back in **New Connection Dialog**, select the new agent in the **Agent** drop-down and click **OK** to save the data source.

## Start from Manage DB Connections

1. Open **File** -> **Manage DB Connections**.
2. Select an existing connection, or click **New** to create one.
3. In the **Octofy AI Agent** section, click **Add New Agent**.
4. In **AI Agent Manager**, click **New** and select agent type **Build-in Agent**.
5. Click **Create Agent** to open the [New Agent Wizard](create-build-in-ai-agent.md#the-new-agent-wizard).
6. Follow the wizard steps below.
7. Select the new agent in the connection's **Agent** drop-down and click **OK** to save connection changes.

**Note:** The **Create Agent** button only starts the wizard while you are adding a *new* agent that has no schema library folder yet. When you select an existing **Build-in Agent** in **AI Agent Manager**, the same button is labeled **Manage Schema Library** and opens the [Schema Library Form](schema-library-form.md) instead.

---

## The New Agent Wizard

The wizard builds the agent's backend (the schema library folder) and its initial knowledge in nine steps. It validates each step before you can continue, and your progress is saved automatically as a draft — if you cancel or close the wizard, reopening the wizard for the same connection restores your draft (agent name, description, reuse/scratch choice, selected objects, and data-group choices). The draft is deleted when you click **Finish**.

While a long operation runs, **Next**, **Back**, **Finish**, and **Cancel** are disabled and **Cancel Task** becomes available.

### Step 0 — Precheck

Click **Next** to validate the connection and load the database schema metadata (tables, views, functions with their columns). The step title is **Step 0 - Precheck** and the validation line reads **Click Next to run precheck and load schema metadata.** If the connection cannot be reached or metadata cannot be loaded, an error is shown and the wizard stays on this step.

### Step 1 — Agent name

- Enter a unique agent name (defaults to the connection's agent name, or the connection name, or the database name; ` (2)`, ` (3)`, … is appended automatically if the name is already taken).
- The **backend folder** preview shows where the schema library will live — the full path under the data-sources root — with its current state (**New** or **Exists**).
- The folder name is the agent's assigned schema data directory when one exists, otherwise `{database}_{server}` (lowercased, non-alphanumeric characters removed) for SQL Server connections, `{DSN}_ODBC` for ODBC connections, or `{database}_{server}_{dbms}` (for example `_postgresql`) for other database types.
- If backend data already exists, choose **Reuse existing backend data** (the default, which keeps and extends the existing library) or **Start from scratch (delete and rebuild)** (which deletes the existing backend folder and requires a double confirmation).

### Step 2 — Database description

- Write a short business description of the database (required), or click **Generate with AI** to create one from the loaded schema metadata (requires an LLM provider configured in [AI Settings](ai-settings.md), and the precheck must have loaded the schema).
- **AI generate mode** controls what happens when you generate with existing text: **Replace** or **Append**.

### Step 3 — Select objects

Choose which database objects the agent will work with. At least one object is required.

- **Add / Remove Objects** — pick objects in the **Database Objects Selector** (filter by **Object Type** — `All`, `Table`, `View`, `Function` — and by **Schema**, search by name with **Filter**, and move objects with **>** / **>>** / **<** / **<<**; `F4` opens the table schema and `F8` previews data).
- **Load from File** — import object names from a text file (`*.txt` / `*.csv`).
- **Load from Clipboard** — import object names from the clipboard.
- Object names use the full form `schema.object_name`; entries can be separated by line breaks, commas, or semicolons. Invalid lines are skipped, duplicates are ignored, and the number of skipped items is reported.

### Step 4 — Schema building

Click **Next** to build the schema library for the selected objects. Progress is shown in the step label and the status log; you can click **Cancel Task** to stop. The step requires the backend folder to resolve, and existing markdown metadata is preserved for objects that are already in the library.

### Step 5 — Propose data groups

If the library already has data groups (from an earlier build or import), they are listed with checkboxes:

- Check the groups to **keep**; uncheck the ones to **delete**.
- Selecting a group shows its member objects on the right.
- The impact line reports "Keep: *n* group(s), Delete: *m* group(s)." At least one group must be kept before you can continue.

### Step 6 — Data group building

Click **Next** to apply the selection: unchecked groups and their files are deleted, the data-group index and the data-source `.data-groups` map are rewritten, and for each kept group precomputed Q&A pairs are generated (requires the LLM provider). Progress is shown in the step label and the status log.

### Step 7 — Review precomputed Q&A

Select a data group in the drop-down and review its precomputed Q&A pairs in the embedded Q&A panel. You can add, regenerate, verify, approve, auto-approve with AI, or delete pairs before finishing — see [Data Groups and Precomputed Q&As](data-groups-and-precomputed-qas.md) for the full set of operations. When the library has no data groups, the step reports that no groups are available.

### Step 8 — Review

The summary shows:

- Schema: Added / Updated / Removed counts.
- Data groups: Kept / Deleted counts.
- Review items: the number collected during the build, listed as `[category] location - detail`.

If there are review items, the **Review Checklist** dialog is shown once. Click **Finish** to create the agent and close the wizard.

---

## Validate the Agent in SQL Builder

1. Open a query editor for the data source that uses the new Build-in Agent.
2. Open the **AI Assistant** panel.
3. Submit a simple request (for example: "List top 10 customers by sales").
4. Confirm SQL is generated in the editor.

If generation is blocked, re-check:

- AI provider configuration,
- agent selection on the data source,
- schema library readiness (the built-in **Test** button in AI Agent Manager checks for `.schema-index.json` files and LLM connectivity, and reports **Built-in agent is ready.** when both pass).

## Next Steps

After the agent exists, maintain and grow its knowledge:

- [AI Agent Manager Window](ai-agent-manager-window.md) — edit, delete, reorder, or test agents.
- [Schema Library Form](schema-library-form.md) — the maintenance window for the agent's knowledge.
- [Add Database Objects](add-database-objects.md) — bring more tables/views/functions into the library.
- [Sync and Rebuild](sync-and-rebuild.md) — keep the library in step with the database.
- [Learn from Past Projects](learn-from-past-projects.md) — ingest legacy SQL scripts.
- [Data Groups and Precomputed Q&As](data-groups-and-precomputed-qas.md) — business groupings and precomputed question/answer pairs.
- [Semantic Models](semantic-models.md) — the semantic layer for the built-in SQL generator.

[Back to Octofy User Manual](user-manual.md)
