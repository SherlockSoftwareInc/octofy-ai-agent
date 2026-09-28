# Tool Functions

**Tool functions** are AI-callable function definitions stored in the `tools/` folder of the schema library. The built-in agent can call them while it prepares a query, extending what it can do beyond plain SQL — for example looking a code up in an external service before writing the filter.

## Browsing tool functions

In the [Schema Library Form](schema-library-form.md), the tree has a **tools** branch listing the tool function definition files (`.md`). Selecting the **tools** folder shows a grid of every definition with its **Tool Name**, **Protocol** and **Description**. Selecting a tool file opens the embedded **tool function editor** for that definition.

The same list is the entry point for the **Tools/Functions** menu:

- **Tools/Functions > Add** — create a new function call definition.
- **Tools/Functions > Remove** — delete the tool function currently selected in the tree, after a confirmation prompt. If no tool is selected, the status bar asks you to select one.

Right-clicking the **tools** branch also offers **Add**, and right-clicking a tool file offers **Edit Function Call Definition**. Both open the **Edit Tool Function Definition** dialog, and the definition is saved back into the library when you click **Save**:

- **New** — start a blank definition.
- **Import File** — import a tool definition from a markdown file.
- **Import Clipboard** — import a tool definition from the clipboard.
- **Test** — validate the definition and, for a sub-agent tool, run a live LLM test with arguments you supply. Live testing of an MCP tool is not supported yet; the dialog says so and asks you to validate the server URL and instructions manually.
- **Save** — save the definition and close.
- **Close** — close without saving (changes are lost).

The message area shows status and errors reported by the editor, and the assistant pane on the right can fill the editor in from a plain-language request — review the values and click **Save**.

## What a tool definition contains

Every definition has a **Tool Name**, a **Description** (the agent uses it to decide when the tool applies), a **Protocol**, a **Parameters Schema JSON** describing the arguments, and instructions that say when the tool should be triggered. What the remaining fields mean depends on the protocol:

| Field | Applies to | Meaning |
| --- | --- | --- |
| **Protocol** | both | `sub_agent` runs a local AI agent; `mcp` calls a remote MCP server. |
| **Model** | `sub_agent` | LLM model used by the sub-agent; empty uses the default model. |
| **Temperature** | `sub_agent` | Sampling temperature for the sub-agent (0 to 2). |
| **Trigger Instructions** | `sub_agent` | Instructions that tell the AI when this tool should be triggered. |
| **Sub-Agent System Prompt** | `sub_agent` | System prompt for the sub-agent that executes the tool. |
| **MCP Server URL** | `mcp` | URL of the remote MCP server that provides this tool. Must be a valid absolute URL. |
| **Trigger Instructions** | `mcp` | Instructions that tell the AI when this MCP tool should be triggered. |

Choosing the protocol shows only the fields that apply: the sub-agent fields are hidden for an MCP tool and the MCP fields are hidden for a sub-agent tool. The trigger instructions are optional; a tool with no trigger instructions is not offered to the model.

## How the agent uses tool functions

- Before generating SQL, the agent lists the definitions in the library and adds each tool's trigger instructions to its analysis prompt.
- The model decides from those instructions whether a tool is needed, and if so which one and with which arguments. The agent then executes the call: a `sub_agent` tool runs a second LLM call with the tool's own model, temperature and system prompt; an `mcp` tool posts the call to its MCP Server URL. Arguments are validated against the Parameters Schema before an MCP call is made, so fields the schema does not declare cannot be injected.
- Whatever the tool returns is fed into the query analysis, so the generated SQL can filter on looked-up values it could not have derived from the schema alone.
- If the model answers with a tool call instead of the analysis, the agent follows up with a plain call so the analysis is always produced and the agent cannot loop on tool calls.

## Related topics

- [Schema Library Form](schema-library-form.md)
- [Browse and Edit Schema Content](browse-and-edit-schema-content.md)
- [AI-Assisted Descriptions](ai-assisted-descriptions.md)

[Back to Create Build-in AI Agent](create-build-in-ai-agent.md)
