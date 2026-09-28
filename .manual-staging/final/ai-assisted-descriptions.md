# AI-Assisted Descriptions

The [Schema Library Form](schema-library-form.md) can use the configured LLM provider to write or complete descriptions of database objects. These commands are in the **Schemas** menu (**AI Describe** and **AI Batch Describe**); the toolbar also has a **Describe Missing** button.

## Requirements

- A library must be loaded.
- The LLM provider must be configured in [AI Settings](ai-settings.md); otherwise a message says **LLM provider is not configured. Configure it in AI settings first.** and the status bar says the AI provider is not configured.

## Commands

| Command | Description |
| --- | --- |
| **AI Describe** | Generates a description for the currently selected table or view (regenerates it). |
| **AI Batch Describe** | Describes every object in the library. You may optionally provide additional context. Progress is shown in the status bar and the progress bar. |
| **Describe Missing** (toolbar button) | Fills in descriptions only where they are missing, for the selected object. The button's tooltip reads "Use AI to describe the selected table or view when its description is missing." |

The **AI Describe** and **AI Batch Describe** menu items are disabled while a describe operation is running.

## What happens

- The selected object must be a table or view with an existing markdown file; otherwise the status bar asks you to select a table or view to describe.
- **AI Batch Describe** first tells you how many objects it will process in Describe Missing mode and asks **Provide additional context for AI?** — answer **Yes** to type context (up to 4000 characters), **No** to run without it, or **Cancel** to stop.
- The AI call runs with a wait cursor and a progress bar; the status bar shows **Describing '*object*'...** or **Describing missing documentation for '*object*'...** as it works.
- On completion the object's markdown file is updated, the library tree is refreshed, and the described object is re-selected; the status bar reports **AI description completed for '*object*'.** For batch describe, the currently open file is reloaded and the status bar reports how many objects were processed.
- In batch mode, a failure on one object is reported as **Warning: failed on *object*. Continuing...** and does not stop the batch.
- Descriptions are written into the object's markdown file, which is the library's source of truth; the object's vector entry is refreshed in the background so search reflects the new text.

## Related topics

- [Schema Library Form](schema-library-form.md)
- [Browse and Edit Schema Content](browse-and-edit-schema-content.md)
- [AI Settings](ai-settings.md)

[Back to Create Build-in AI Agent](create-build-in-ai-agent.md)
