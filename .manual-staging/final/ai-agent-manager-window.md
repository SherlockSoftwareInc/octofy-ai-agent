# AI Agent Manager Window

The **AI Agent Manager** window is used to create and maintain AI agent profiles used by Octofy.

The window lists the configured agents under **AI Agents:** on the left and shows the details of the selected agent in the panel on the right. The details panel is disabled until you select an agent or start a new one; its title is the name of the agent being shown (or **New Agent** while you are adding one).

## Open the AI Agent Manager

You can open this window from two places:

- In the main window, choose **File > Manage AI Agents**.
- Open **File > Manage DB Connections**, select a connection, and click **Add New Agent** in the **Octofy AI Agent** section. The same window opens ready to add an agent for that connection.

## What You Can Do

In the toolbar, you can:

- **New**: start a new agent. The details panel is cleared, enabled, and titled **New Agent**, and the **Add** button appears.
- **Delete**: remove the selected agent.
- **Move up / Move down**: reorder agents in the list.
- **Test**: validate the selected agent configuration.
- **OK**: save all changes and close.
- **Cancel**: discard unsaved changes, reload the stored agents, and close.
- **Help**: open this documentation page in your default browser.

If you close the window (for example with the **X** button) while there are unsaved changes, you are asked whether to save, discard, or cancel the close.

## Agent Types

The **Agent Type:** option group offers two agent types:

- **Octofy AI Agent** — an agent hosted by an external Octofy AI agent service, configured with an endpoint and API key.
- **Build-in Agent** — an agent that runs inside Octofy and uses the app's global AI provider settings together with a local schema library.

### Octofy AI Agent fields

- **Name**
- **Endpoint** — the URL of the Octofy AI agent service (for example `https://localhost:8000`). If you type only a host, `https://` is added for you.
- **API key** — the key used to authenticate with the agent service.
- **Data Source** — the data source this agent uses. The drop-down lists the data sources registered in the agent service by name, and the source ID of the selection is saved with the agent. You can also type a source ID directly. The reload button beside the box loads the list again from the agent service.

The server and database used to resolve the data source are no longer edited in this window; they are taken from the connection the window was opened for (or from the agent being edited).

### Build-in Agent fields

- **Manage Schema Library** button — opens the [Schema Library Form](schema-library-form.md) for the agent's data source. When you are creating a built-in agent for a connection that has no built-in agent yet, the button reads **Create Agent** and opens the [New Agent Wizard](create-build-in-ai-agent.md#the-new-agent-wizard) instead, which creates the agent and builds its schema library in one guided flow.
- **Allow semantic layer for this data source** check box — enables the semantic layer (SMQ compilation against a semantic model) for this agent's data source. See [Semantic Models](semantic-models.md).
- The **Name** field and the **Octofy AI Agent** group are hidden for a built-in agent: its name and schema-library folder are derived from the data source.
- Uses the current AI provider settings configured in the app ([AI Settings](ai-settings.md)).

## Add a New Agent

- Click **New**.
- Select the agent type.
- Enter agent details.
- Click **Add** (the button appears for a new agent; existing agents save on **OK**).

For a full end-to-end guide specific to **Build-in Agent**, see [Create a Build-in AI Agent](create-build-in-ai-agent.md).

Notes:

- Agent names must be unique; adding a duplicate name reports that an agent with that name already exists.
- If opened from a connection with **Add New Agent**, fields may be pre-filled from the current connection, and the suggested agent name is made unique automatically by appending `(2)`, `(3)`, and so on.
- For built-in agents, the backend folder is computed automatically: `{database}_{server}` (or `{DSN}_ODBC` for ODBC connections), lowercased with non-alphanumeric characters removed.

## Edit an Existing Agent

- Select an agent in the left list.
- Modify fields in the right panel.
- Changes are saved when you click **OK**.

## Test an Agent

- Select an agent.
- Click **Test**.

Behavior:

- **Octofy AI Agent**: tests endpoint/API key connectivity by calling the root health endpoint of the agent service. An endpoint and an API key are required; on success the message "Connection to agent endpoint succeeded." is displayed.
- **Build-in Agent**: checks that the schema library is ready (the data source folder contains `.schema-index.json` files) and that the AI provider is configured and reachable (sends a minimal probe request to the configured LLM endpoint). A summary of any problems is shown; if everything is ready, "Built-in agent is ready." is displayed.

## Source ID Resolution

For **Octofy AI Agent**, the **Data Source** box shows the data sources registered in the agent service by their names and stores the matching **Source ID** with the agent.

- The list is loaded from the agent service automatically when the **Endpoint** and **API key** are filled in and the field loses focus, and again when you select an agent. The reload button loads it on demand. The request times out after 20 seconds.
- A source ID you type that matches a listed data source resolves to that data source's name, so the name and the source ID always travel together.
- When you click **OK**, if only a source ID is known the window asks the agent service for the name that belongs to it, so both are saved as a pair.

## Delete an Agent

- Select an agent.
- Click **Delete**.
- Confirm the delete prompt.

## Related Topics

- [Create a Build-in AI Agent](create-build-in-ai-agent.md)
- [Schema Library Form](schema-library-form.md)
- [Octofy AI Agent backend API](octofy-ai-agent-backend-api.md)

[Back to Create Build-in AI Agent](create-build-in-ai-agent.md)

## Screenshots

![AI Agent Manager window](images/AI_Agent_Manager.png)
