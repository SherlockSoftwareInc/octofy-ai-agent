# AI Agent Manager Window

The **AI Agent Manager** window is used to create and maintain AI agent profiles used by Octofy.

## Open the AI Agent Manager

You can open this window from **Manage Data Sources**:

- Open **File** ? **Manage DB connections**.
- In the connection details panel, click **Add New Agent** in the **Octofy AI Agent** section.

## What You Can Do

In the toolbar, you can:

- **New**: create a new agent
- **Delete**: remove the selected agent
- **Move up / Move down**: reorder agents
- **Test**: validate the selected agent configuration
- **OK**: save all changes and close
- **Cancel**: discard unsaved changes and close

If you close the window (for example with the **X** button) while there are unsaved changes, you are asked whether to save, discard, or cancel the close.

## Agent Types

The window supports two agent types:

- **Octofy AI Agent** — an agent hosted by the Octofy AI agent service, configured with an endpoint and API key.
- **Build-in Agent** — an agent that runs inside Octofy and uses the app's global AI provider settings together with a local schema library.

### Octofy AI Agent fields

- **Name**
- **Server**
- **Database**
- **Endpoint**
- **API key**
- **Source ID** (read-only; resolved automatically when possible)

### Build-in Agent fields

- **Manage Schema Library** button — opens the [Schema Library Form](schema-library-form.md) for the agent's data source. When you are creating a built-in agent for a connection that has no agent yet, it opens the [New Agent Wizard](create-build-in-ai-agent.md#the-new-agent-wizard) instead, which creates the agent and builds its schema library in one guided flow.
- **Enable semantic layer** checkbox — enables the semantic layer (SMQ compilation against a semantic model) for this agent's data source. See [Semantic Models](semantic-models.md).
- Uses the current AI provider settings configured in the app ([AI Settings](ai-settings.md)).

## Add a New Agent

- Click **New**.
- Select the agent type.
- Enter agent details.
- Click **Add** (the button appears for a new agent; existing agents save on **OK**).

For a full end-to-end guide specific to **Build-in Agent**, see [Create a Build-in AI Agent](create-build-in-ai-agent.md).

Notes:

- Agent names must be unique.
- If opened from a connection with **Add New Agent**, fields may be pre-filled from the current connection.
- For built-in agents, the backend folder is computed automatically: `{database}_{server}` (or `{DSN}_ODBC` for ODBC connections), lowercased with non-alphanumeric characters removed.

## Edit an Existing Agent

- Select an agent in the left list.
- Modify fields in the right panel.
- Changes are saved when you click **OK**.

## Test an Agent

- Select an agent.
- Click **Test**.

Behavior:

- **Octofy AI Agent**: tests endpoint/API key connectivity by calling the agent service health endpoint.
- **Build-in Agent**: checks that the schema library is ready (the data source folder contains `.schema-index.json` files) and that the AI provider is configured and reachable (sends a minimal probe request to the configured LLM endpoint). A summary of any problems is shown; if everything is ready, a success message is displayed.

## Source ID Resolution

For **Octofy AI Agent**, when **Endpoint** and **API key** are entered and validated, the system attempts to resolve **Source ID** using **Server** and **Database**.

## Delete an Agent

- Select an agent.
- Click **Delete**.
- Confirm the delete prompt.

## Related Topics

- [Create a Build-in AI Agent](create-build-in-ai-agent.md)
- [Schema Library Form](schema-library-form.md)

[Back to Create Build-in AI Agent](create-build-in-ai-agent.md)

## Screenshots

![AI Agent Manager window](images/AI_Agent_Manager.png)
