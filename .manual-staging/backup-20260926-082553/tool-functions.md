# Tool Functions

**Tool functions** are AI-callable function definitions stored in the `tools/` folder of the schema library. The built-in agent can invoke them during generation, extending what it can do beyond plain SQL.

## Browsing tool functions

In the [Schema Library Form](schema-library-form.md), the tree has a **tools** branch listing the tool function definition files (`.md`). Selecting a tool file opens the embedded **tool function editor**.

## Editing a tool function

While the tool function editor is active, changes are saved to the tool definition when you navigate away or close the form.

## Add / Edit Function Call Definition (context menu)

Right-click the **tools** branch (or a tool file) and choose **Add Function Call Definition** / **Edit Function Call Definition** to open the **Edit Tool Function Definition** dialog:

- **New** — create a new tool function.
- **Import File** — import a tool definition from a markdown file.
- **Import Clipboard** — import a tool definition from the clipboard.
- **Test** — test the tool function definition with a live LLM call.
- **Save** — save the definition and close.
- **Close** — close without saving (changes are lost).

The message area shows status and errors reported by the editor.

## Removing a tool function

Right-click a tool file and choose **Remove** to delete the tool function from the library (with confirmation).

## Related topics

- [Schema Library Form](schema-library-form.md)
- [Browse and Edit Schema Content](browse-and-edit-schema-content.md)
- [AI-Assisted Descriptions](ai-assisted-descriptions.md)

[Back to Create Build-in AI Agent](create-build-in-ai-agent.md)
