# AI-Assisted Descriptions

The [Schema Library Form](schema-library-form.md) can use the configured LLM provider to write or complete descriptions of database objects. These commands are in the **AI Assistant** menu; the toolbar also has a **Describe Missing** button.

## Requirements

- A library must be loaded.
- The LLM provider must be configured in [AI Settings](ai-settings.md); otherwise a warning is shown.

## Commands

| Command | Description |
| --- | --- |
| **Describe** | Generates a description for the currently selected table or view (regenerates it). |
| **Describe with…** | Describes the selected table or view using additional context you supply (up to 4000 characters). |
| **Describe missing** | Fills in descriptions only where they are missing, for the selected object. |
| **Batch Describe** | Describes every object in the library sequentially. You may optionally provide additional context. Progress is shown in the status bar and the marquee progress bar. |

## What happens

- The selected object must be a table or view with an existing markdown file; otherwise the status bar asks you to select one.
- The AI call runs with a wait cursor; the AI Assistant menu is disabled during the operation.
- On completion the object's markdown file is updated, the library tree is refreshed, and the described object is re-selected. For batch describe, the currently open file is reloaded.
- In batch mode, a failure on one object is reported in the status bar but does not stop the batch; the completion message reports how many objects were processed.

## Related topics

- [Schema Library Form](schema-library-form.md)
- [Browse and Edit Schema Content](browse-and-edit-schema-content.md)
- [AI Settings](ai-settings.md)

[Back to Create Build-in AI Agent](create-build-in-ai-agent.md)
