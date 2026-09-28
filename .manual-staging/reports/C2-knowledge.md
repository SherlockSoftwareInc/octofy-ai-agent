# C2 — Knowledge pages report

Scope: the seven knowledge pages I own. Baseline read from `.manual-staging\baseline\`, updated files written to `.manual-staging\new\`.
Evidence is `file:line` in `C:\Users\sherl\source\repos\OctofyPro\...` unless stated otherwise.

Verification method: product docs (`OctofyPro\Docs\VECTOR_DATABASE_RAG_SUMMARY.md`, `PRECOMPUTED_QA_ARCHITECTURE.md`, `plans\MCP_TOOL_SUPPORT_PLAN.md`), the shipping OctofyPro UI (`OctofyPro\AI\*`, `OctofyPro\DataExplorer\SchemaLibraryPanel.cs`), the agent library (`Octofy.Agent\AI\BuiltIn\*`), and `git log --since=2026-08-25`. Every `.resx` was parsed to confirm the exact English string, because in several places the `.resx` default differs from the older manual wording.

**Headline:** every page needed correction. There is no `AI Assistant` menu in the schema library form any more; menu wording changed ("Learn from Past Project" singular, "Add Knowledge Base" without ellipsis, "Data Groups" plural, "AI Describe"/"AI Batch Describe"); two documented commands no longer exist anywhere in the shipping UI (`Describe with…`, `File > Save Semantic Model`); the vector DB no longer holds value mappings, skills or a schema-payload column; and the ingest dialog gained a whole second tier (`Stage as knowledge wiki`, `Distill knowledge`, `Quarantined` tab, `Open run manifest`, business-rule review with `Approve`/`Reject`).

---

## 1. `learn-from-past-projects.md` — rewritten

Status: **heavily rewritten.** Baseline described a single-tier run with six artifact types and no review surface.

Changes, with evidence:

- Menu command is **File > Learn from Past Project** (singular). `OctofyPro\AI\SchemaLibraryForm.resx` → `importLegacyScriptsToolStripMenuItem.Text = "Learn from Past Project"`. Was documented as "Learn from Past Projects".
- Dialog title is **Learn from Past Projects**. `LegacyScriptImportForm.resx` → `Form.Title`. Added all the dialog's real fields: **Browse...**, **Include sub-folders** (was "Include subfolders"), **Stage as knowledge wiki (distil later)**, **LLM instructions** with placeholder `e.g. All currency values are in CAD.`, **Start**, **Cancel**, **Distill knowledge**, **Open folder**, **Open run manifest** (`LegacyScriptImportForm.Designer.cs:155,165,468,499,511`).
- Requirements wording: `Error.SchemaLibraryUnavailable = "Schema library folder is unavailable."`, `Error.LlmProviderNotConfigured = "LLM provider settings are not configured."` (`LegacyScriptImportForm.resx`).
- New: the **two-tier model**. Tier 1 = a run over one folder; tier 2 = **Distill knowledge** (`LegacyScriptImportForm.cs:194-280`, `DistillButton_Click`; docstrings call it "the second stage … (plan W2)"). Explained why staging exists (cross-project data lineage) using `LegacyKnowledgeDistiller.cs:74-89`.
- New: supported sources and unit granularity — `.sql/.sas/.r/.py/.java/.c/.cs`, `.sqlproj` expanded (`LegacyScriptIngestionService.cs:1236-1272,1282`); units split on SQL `GO`, SAS `DATA`/`PROC`/`%macro`→`%mend`, R function/`##` banners, per-unit receipt re-dispatch once, per-file cap (`LegacyScriptIngestionResult.cs:359-371`, summary docstrings).
- New: trust gates. A rule with neither line range nor verbatim quote is quarantined, not saved (`LegacyIngestionOptions.RequireEvidence`, default true, `LegacyScriptIngestionResult.cs:246-251`).
- New: the summary/quarantine/manifest/rule-review surfaces, quoting the exact UI strings: `Summary.CompletedFormat` (`Q&A: … | Few-shot: … | Values: … | Skills: … | Semantic: … | Rules: … kept, … quarantined, … generic, … conflicts, evidence …%`), `Tab.BusinessRules` columns (Statement/Kind/Target/Recurrence/Confidence/Status/Evidence), `Rules.Button.Approve`/`Reject`, `Tab.Quarantined`/`Tab.QuarantinedWithCount`, `Quarantine.Column.*`, `Link.OpenManifest`, `Manifest.Missing`, `Rules.SemanticLayerDisabled`, `Rules.StagedForDistillationFormat`, `Distill.*` — all from `LegacyScriptImportForm.resx`, wiring at `LegacyScriptImportForm.cs:115-159,230-261,327-379`.
- New: what a run drops and how it is reported — quarantine reason codes (`no_evidence`, `generic`, `over_cap`, `conflict`, `unknown_object`, `under_extracted`, `unresolved_upstream_dataset`, …) at `LegacyScriptIngestionResult.cs:80-131`; skip reasons (`no_select`, `ddl_only`, `context_limit`, `llm_error`, `parse_error`, `no_units`, `unbacked_query`, `error`, `unit_cap`, `unit_no_result`, `unit_receipt_mismatch`, `resumed`) at `LegacyScriptIngestionResult.cs:30-69`; evidence coverage at `:347`.
- New: staging (`LegacyIngestionOptions.StageKnowledgeWiki`, default false, `LegacyScriptIngestionResult.cs:291-309`) and what a staging run still writes (rules, quarantine, glossary, state, manifest) — `LegacyScriptIngestionResult.cs:296-301`.
- New: the wiki library contents — `kb/wiki/datasets/<name>.md`, `kb/wiki/analyses/<name>.md`, `kb/wiki/projects/<name>.md`, `kb/wiki/index.md` (`LegacyKnowledgeWiki.cs:217-221,1530,1545`; `VECTOR_DATABASE_RAG_SUMMARY.md:516-517`).
- New: distillation outcome string `Summary.DistilledFormat` and the two follow-ups `Distill.NothingStaged`, `Distill.UnresolvedFormat` (`LegacyScriptImportForm.cs:230-258`).
- New: resumability — units already `covered` are skipped, state invalidated when the model/instructions/gates/unit cap change or when a file's content hash changes (`LegacyIngestionOptions.ResumeFromPreviousRun` default true, `LegacyScriptIngestionResult.cs:277-283`; `UnitsResumed`/`FilesResumed` at `:371-375`).
- New: idempotency — deterministic content key, check before embedding, zero duplicate rows on re-run (`VECTOR_DATABASE_RAG_SUMMARY.md:551-558`; `LegacyScriptIngestionResult.cs:396-397` `DuplicatesSuppressed`).
- New: multi-run semantic-model merge and conflict escalation, same model id, `merged` vs `created` vs `deactivated-predecessor` (`LegacyScriptIngestionOptions.MergeIntoExistingSemanticModel`, `LegacyScriptIngestionResult.cs:253-259`; `VECTOR_DATABASE_RAG_SUMMARY.md:560-573`).
- New: reviewer decisions survive re-runs because rules are merged by deterministic key, not appended (`LegacyScriptIngestionResult.cs:637-664` `Key`/`ReviewStatus`; `LegacyScriptIngestionResult` docstring "read-merge-rewrite").
- Kept: "Open folder" link at the end of the run.
- Removed: the claim that a run unconditionally writes "Q&A pairs, Few-shot examples, Value mappings, Skill files, Semantic models" — that is now only true of a non-staging run, and "skills" are one regenerated document per domain, not a set of "markdown skill files".

Heading changes (all new `##` sections, baseline headings preserved):

| Old | New |
| --- | --- |
| `## What happens during ingestion` | replaced by `## What gets learned` and `## Reviewing what a run produced` (old heading removed) |
| — | `## Staging a run`, `## Distilling staged knowledge`, `## Re-running a folder`, `## If the extracted model is not used` (added) |

Screenshots: none in baseline; none added.

Unverifiable: none material. `LegacySkillDocument`/skill-per-domain shape taken from `VECTOR_DATABASE_RAG_SUMMARY.md:510-511` (code-adjacent doc, not the code itself).

---

## 2. `data-groups-and-precomputed-qas.md` — updated

Status: **substantially updated.**

- Menu structure corrected: the menu is **Data Groups** and the create command is **Add**, not "New data group". `SchemaLibraryForm.resx` → `dataGroupToolStripMenuItem.Text = "&Data Groups"`, `newDataGroupToolStripMenuItem.Text = "Add"`; designer drop-down order `add → remove → sep → addObjects → generateKeywords → manageAnticipatedQuestions → syncDataGroupVectors` (`SchemaLibraryForm.Designer.cs:318`).
- **Remove** was added as a data-group command (was absent). `SchemaLibraryForm.cs:631-666`, `Message.ConfirmRemoveDataGroup = "Remove '{0}' from the data-groups index?"`, `Caption.RemoveDataGroup`. Note the Remove item is data-group-level, not member-level.
- Member removal moved to the object list's own right-click menu (`DataGroupItemPanel.cs:34-35`; `ContextMenu.AddObjects = "Add objects"`, `ContextMenu.Remove`). Baseline implied **Data Group > Remove** removed "the selected member" — wrong.
- "Generate keywords" was documented as **Generate keywords**; exact wording is **Generate Keywords** (`SchemaLibraryForm.resx`).
- Editor structure documented from `DataGroupItemPanel.resx`: tabs **Data Group** and **Q&As**, fields Data group / Category / Description / Keywords / Objects / **Business Rules & Metrics**.
- New group flow verified at `SchemaLibraryForm.cs:4340-4487`: name prompt `Dialog.NewDataGroupPrompt`, max 64 chars, `Message.DataGroupNameCannotBeEmpty`, `Message.DataGroupNameInvalidCharacters`, then `DBObjectsSelectForm`, then `Message.SelectAtLeastOneObjectForNewDataGroup`. Stated inline in prose (no error table added).
- Review dialog: title confirmed `Review Q&A Pairs - {groupName}` (`DataGroupQuestionsForm.cs:47`). Status values corrected to the four the combo actually offers — `Pending/Approved/Modified/Error` (`DataGroupQuestionsForm.cs:48-53`); baseline also claimed `Pending/Approved/Modified/Error` but the tier doc's status list differs, so this is now anchored to the UI.
- Toolbar commands corrected to actual labels: **Add** (not "New"), **New by AI** (not "Generate"), **AI Auto Approve** (not "Auto-approve"), **Open**, **Verify**, **Regenerate**, **Approve**, **Delete**, **Save**, **Close** (`GroupQAPanel.resx`). Removed "10 per click" (not evidenced anywhere).
- Auto-approve preconditions and progress string quoted (`GroupQAPanel.resx`: `Message.AutoApproveRequiresAiSettings`, `Message.AutoApproveNoMembers`, `Status.AutoApproveProgress = "Auto-approve progress: {0}/{1} (approved: {2}, regenerated: {3}, pending: {4})"`; code `DataGroupQuestionsForm.cs:640-751`).
- Verify result strings quoted (`Message.VerificationValidAndSatisfied` / `Message.VerificationValidNotSatisfied`).
- **New section `## How data groups steer the agent`**: active groups resolved top-3 and injected as ACTIVE BUSINESS CONTEXT; precomputed fast paths (direct reuse at similarity ≥ 0.93, related pairs as few-shots at ≥ 0.82); only `Approved` rows are vector-searched while the exact-question pre-check also reads `Modified`; group members weight 2.0 in the RRF merge and a group-anchored survivor anchors the result. Evidence: `VECTOR_DATABASE_RAG_SUMMARY.md:369-427,142-150`.
- Sync Vectors status strings quoted (`Status.DataGroupSyncCompleted`, `Status.DataGroupSyncSkippedNotConfigured`; `SchemaLibraryForm.cs:4196-4215`).

Heading changes: two new `##` sections (`## How data groups steer the agent`; the note paragraph is inline, not a heading). No renames.

Screenshots: none in baseline; none added.

Unverifiable: `Rejected` exists in the status model and in `PRECOMPUTED_QA_ARCHITECTURE.md` but is not offered by the review dialog's combo, so I documented the four selectable values only.

---

## 3. `tool-functions.md` — substantially rewritten

Status: **substantially rewritten** (baseline was ~40 lines and mostly about a dialog that no longer matches).

- Baseline's **Add Function Call Definition / Edit Function Call Definition** right-click commands: only `Edit Function Call Definition` still exists (`SchemaLibraryPanel.resx` → `Menu.EditFunctionCallDefinition`; enabled only on a level-2 tool node, `SchemaLibraryPanel.cs:1184`). "Add Function Call Definition" does not exist. Corrected: **Tools/Functions > Add** (`SchemaLibraryForm.resx` → `toolsFunctionsToolStripMenuItem.Text = "&Tools/Functions"`, `addToolFunctionToolStripMenuItem.Text = "Add"`), plus right-click **Add** on the `tools` node (`SchemaLibraryPanel.cs:1183`, `addToolStripMenuItem`).
- New: selecting the **tools** folder shows a grid of **Tool Name / Protocol / Description** (`SchemaLibraryForm.cs:948-975`, `GridHeader.ToolName|Protocol|Description`); selecting a file opens the embedded editor.
- Dialog title confirmed **Edit Tool Function Definition** (`ToolFunctionEditForm.cs:218`). Buttons confirmed: New, Import File, Import Clipboard, Test, Save, Close (`ToolFunctionEditForm.resx`); "Close — close without saving" is accurate (`ToolFunctionEditForm.cs:268-272`).
- New: **MCP protocol support** — `protocol` field with `sub_agent` and `mcp`; protocol-aware fields (`ToolFunctionEditPanel.cs:380-450` `ApplyProtocolLayout`, `:167-174` combo items). Field labels taken from `ToolFunctionEditPanel.resx`: Tool Name, Description, Protocol, Model, Temperature, Parameters Schema JSON, Trigger Instructions, Sub-Agent System Prompt, MCP Server URL (`agentInstructionsLabel.Text` is also "Trigger Instructions").
- New: MCP validation (`Message.McpServerUrlRequired`, `Message.McpServerUrlInvalid = "MCP Server URL must be a valid absolute URL."`) and the fact that a live test for an MCP tool is not supported (`Message.McpTestNotSupported`, `ToolFunctionEditPanel.cs:589-593`). Note the shipping string says "…validate the server URL and trigger instructions manually." whereas `MCP_TOOL_SUPPORT_PLAN.md:370` said "agent instructions"; I documented the shipping text.
- New: **runtime** behaviour — tools are listed in the pre-analysis prompt under `## Available Tools` with their trigger instructions, the model selects one, `sub_agent` runs a secondary LLM call and `mcp` posts JSON-RPC to `mcp_server_url` with arguments sanitized against the parameters schema, and results feed the analysis; if the model answers with a tool call instead of the analysis the agent re-asks without tool triggers (`BuiltInSqlGenerator.cs:2980-3044`; `ToolFunctionInvoker.cs:9-10,29-30,374-378,528-532`). This corrects the baseline's "The built-in agent can invoke them during generation" vagueness and documents the MCP path the task asked about.
- New: a protocol/field table (pipe table) so the two protocols' fields are unambiguous.
- Kept and re-anchored: removal (`Tools/Functions > Remove`, `Message.ConfirmRemoveToolFunction = "Remove '{0}' from tool-functions?"`, `Status.SelectToolFunctionToRemove`).
- Removed: "The message area shows status and errors reported by the editor" kept but re-worded; nothing else removed.

Heading changes: `## Editing a tool function` replaced by `## What a tool definition contains`; `## Add / Edit Function Call Definition (context menu)` replaced by `## Browsing tool functions` + `## How the agent uses tool functions`. `## Browsing tool functions`, `## Removing a tool function`, `## Related topics` kept.

## 4. `ai-assisted-descriptions.md` — substantially rewritten

Status: **substantially updated; one command removed.**

- The **AI Assistant** menu no longer exists. The commands live in the **Schemas** menu: **AI Describe** and **AI Batch Describe** (`SchemaLibraryForm.resx` → `columnToolStripMenuItem.Text = "&Schemas"`, `describeToolStripMenuItem.Text = "AI Describe"`, `batchDescribeToolStripMenuItem.Text = "AI Batch Describe"`; drop-down wiring `SchemaLibraryForm.Designer.cs:278`). The toolbar button is **Describe Missing** (`SchemaLibraryForm.resx`, `describeMissingToolStripButton.Text`).
- **`Describe with…` removed from the page.** For OctofyPro there is no `describeWithToolStripMenuItem` in the designer, no `describeWithToolStripMenuItem.Text` resource, and the click handler at `SchemaLibraryForm.cs:3656` is unreachable dead code. The only `describeWithToolStripMenuItem` resource in the OctofyPro folder is a stray `.Size` row in `SchemaLibraryForm.resx:594` area (no `.Text`). The command still exists in the AgentBuilder shell (`AgentBuilder\AI\SchemaLibraryForm.Designer.cs:339`), which is why the task's earlier note about it is misleading. Consequence: the `Dialog.DescribeWithContextTitle` / `Dialog.AdditionalContextPrompt` resources are still used by the batch path only.
- Requirements wording: `Message.LLMProviderNotConfigured = "LLM provider is not configured. Configure it in AI settings first."`, `Status.AIProviderNotConfigured = "AI provider is not configured."` (`SchemaLibraryForm.resx`).
- Batch flow documented precisely: object count message (`Prompt.BatchDescribeAdditionalContextFormat = "Batch Describe will process {0} objects in Describe Missing mode."`), **Provide additional context for AI?** Yes/No/Cancel, input up to 4000 characters, title **Batch Describe Context** (`SchemaLibraryForm.cs:3724-3750`).
- Progress/completion strings quoted: `Status.DescribingObjectFormat`, `Status.DescribingMissingObjectFormat`, `Status.BatchDescribeProgressFormat = "Batch describe [{0}/{1}]: {2}..."`, `Status.AIDescribeCompletedForObjectFormat = "AI description completed for '{0}'."`, `Status.BatchDescribeCompletedFormat = "Batch describe completed. Processed: {0} objects."`, `Status.WarningFailedOnObjectContinuingFormat = "Warning: failed on {0}. Continuing..."`, `Status.SelectTableOrViewToDescribe`.
- Kept: markdown file updated, tree refreshed, object re-selected, batch failure does not stop the batch. Added: the described file's vector entry is refreshed in the background (`SchemaLibraryForm.cs:4230-4258` `ScheduleVectorIndexUpdateIfNeeded`).

Heading changes: none (Requirements / Commands / What happens / Related topics all kept). Table gained a third row for the toolbar command.

## 5. `semantic-models.md` — updated

Status: **substantially updated.**

- **`File > Save Semantic Model` removed.** There is no `saveSemanticModelToolStripMenuItem` in `SchemaLibraryForm.Designer.cs`; `Menu.SaveSemanticModel` exists only as an orphan `.resx` string, and the only "save" path is the editor's asynchronous auto-save (`SchemaLibraryForm.cs:3254-3328`; `SchemaLibraryForm_FormClosing` at `:2736-2764`). The baseline's "enabled only while the editor is active" was therefore unverifiable and is gone.
- Per-agent toggle label corrected to **Allow semantic layer for this data source** with its tooltip, from `AIAgentManager.resx:344-348` — the baseline called it "Enable semantic layer".
- Per-data-source toggle documented from `SemanticModelEditPanel.resx`: **Enable semantic layer for this data source**. Order of precedence (agent wins; per-data-source is the fallback) from `VECTOR_DATABASE_RAG_SUMMARY.md:335-342`.
- **Tree/folder behaviour corrected.** The baseline said selecting the **semantic-model** folder opens the editor on the latest active model. It now shows a **grid** of every model with **model_name / model_id / status** (`Active`/`Inactive`), and a row opens the editor on double-click (`SchemaLibraryForm.cs:978-1039`, `:3112-3121`, `:1099-1113`; `GridHeader.ModelName|ModelId|Status`, `GridValue.Active|Inactive`).
- New: the editor's actual controls — **Label**, **Data Source Key**, **Is active**, **Enable semantic layer for this data source**, tabs **Measures / Dimensions / Joins / Governance**, **Selected item** detail with **Apply**, and **Compile preview** (`SemanticModelEditPanel.resx`; `SemanticModelEditPanel.cs:509-521`). Baseline described only "measures, dimensions, joins, and governance predicates" with no preview and no Apply.
- New: compile preview failure/success wording (`Status.CompileNoMeasure = "At least one measure is required for preview."`, `Status.CompileFailed`, `Status.CompileSuccess`) and editor validation rules (`Validation.MeasureRequired`, `Validation.DimensionFields`, `Validation.JoinPathRequired`, `Validation.Duplicates`).
- New: save result strings (`Status.SaveSuccess = "Semantic model saved. Embedding updated."`, `Status.SemanticModelSaved`, `Status.SemanticModelAutoSaveFailed`) and the coalescing behaviour (kept from baseline, re-anchored to `SchemaLibraryForm.cs:3286-3328`).
- New: **Remove** for a model, with the exact confirmation `Message.ConfirmRemoveSemanticModel = "Remove semantic model '{0}'? This permanently deletes the model and its embedding."` (`SchemaLibraryForm.resx`; `SchemaLibraryForm.cs:4117-4177`). Baseline had no removal.
- New section `## Merging across runs and conflicting definitions` — the newer multi-run behaviour: merge into the active model under the same model id, conflicts escalated with every candidate kept and only the affected item blocked, distilled dimensions re-pointed (`VECTOR_DATABASE_RAG_SUMMARY.md:560-573`; `LegacyScriptIngestionResult.cs:253-259`).
- Kept: enabling requirements (layer on **and** an active model exists), viewing inactive models, Add never overwrites, model-from-query via the Add to Knowledge Base checkbox.

Heading changes: `## Merging across runs and conflicting definitions` added. No renames.

## 6. `add-to-knowledge-base.md` — substantially updated

Status: **substantially rewritten.**

- Menu wording: **File > Add Knowledge Base** (no ellipsis at runtime; `SchemaLibraryForm.resx` → `addKnowledgeBaseToolStripMenuItem.Text = "Add Knowledge Base"`; `Menu.AddToKnowledgeBase` with the ellipsis is an unused duplicate string). Dialog title **Add to Knowledge Base** (`AddToKnowledgeBaseForm.resx` → `Form.Text`).
- Button label corrected: **Add to KB**, not "Add" (`addButton.Text`).
- Similarity panel documented — **Similar existing entries:** with score+preview rows and the SQL on hover (`similarLabel.Text`, `AddToKnowledgeBaseForm.cs:320-349,439-455`), identical-entry warning `Message.IdenticalEntryExists` and disabled add button, `Status.VectorServiceNotConfigured`, `Message.BothQuestionAndSqlRequired`.
- New: the AI question assist (`Status.GeneratingQuestionByAi`, `Status.QuestionGeneratedByAi`, `Message.EnterSqlToVerify`, `Message.LlmNotConfigured`, `Message.EmptyGeneratedQuestion`; `AddToKnowledgeBaseForm.cs:198-264`).
- New: **`## The thumbs-up flow`** — the 👍 button (`CopilotPanel.resx` → `thumbsUpButton.ToolTip = "Add to knowledge base"`), shown only when an answer contains SQL (`CopilotPanel.cs:452-462`), the dialog is pre-filled with the first question of the conversation and the generated SQL (`CopilotPanel.cs:960-998`, `BuildKnowledgeBaseQuestion`), and the button is hidden after a successful add. This is the flow's real entry point and the baseline never mentioned it.
- New: **`## What is saved, and where`** — built-in writes into the data source's `vector-index.db` `few_shots` collection (question embedded, SQL stored); Octofy-Agent posts to the remote few-shot API (`AddToKnowledgeBaseForm.cs:405-437`); the SQL is stored without the generator's leading `/* … */` reasoning block (`BlockCommentRegex` at `:27`, applied at `:91,364`).
- New: **`## How it relates to contributions and canonical questions`** — curated contribution semantics (the code comment at `AddToKnowledgeBaseForm.cs:360-363` says "Curated contributions must store only clean, executable SQL … so the knowledge base stays a high-signal example library"), the question is the canonical key for the deterministic exact-question match, and how it differs from data-group precomputed Q&As.
- Semantic-model section kept but corrected: the checkbox is only *enabled* for built-in agents with a vector db directory; the extraction + **Edit Semantic Model** step actually runs in the caller after the dialog returns (`SchemaLibraryForm.cs:4540-4583`; `CopilotPanel.cs:1000-1043`), and the empty-extraction message is `SemanticModel.ExtractionEmpty` (`CopilotPanel.resx`).
- Kept: checkbox label **Build a semantic model from this query** and the disabled-state tooltip `ToolTip.BuildSemanticModelDisabled`.

Heading changes: `## The thumbs-up flow`, `## What is saved, and where`, `## How it relates to contributions and canonical questions` added; `## How to use it`, `## Agent mode behavior`, `## Building a semantic model from the query`, `## Related topics` kept.

## 7. `manage-library-folder-and-vector-db.md` — updated

Status: **substantially updated.**

- Folder naming: kept `{database}_{server}` and `{DSN}_ODBC`, and added the DBMS suffix rule, from `DataSourceFolderResolver.cs:18-34` (`RequiresDbmsSuffix` at `:81-88`, ODBC at `:18-25`, sanitize at `:93-100`). Also documented the assigned-folder override (`:12-13`).
- Data-sources root made concrete: `%APPDATA%\Sherlock Software Inc\Octofy\skills\data-sources` (`SchemaIndexService.cs:62`, `VectorSearchService.cs:106`). Baseline said "under the data-sources root" without naming it.
- Folder contents updated: added `kb/` (including `kb/wiki/`) and dropped the implication that storage is only markdown+indexes+vector db (`VECTOR_DATABASE_RAG_SUMMARY.md:516-517`; `LegacyKnowledgeWiki.cs:217-221`).
- **`## What the vector database contains` rewritten.** Baseline said the viewer's collections were "internal support tables and shadow tables are hidden" — the real rule is more specific (`InternalSupportTables` = data_group_vectors_map, data_group_vectors_cache, vec_data_group_query_vectors_cache, embedding_cache, few_shots_meta, plus `_vec0`, `^vec_schemas/_few_shots/_value_index` shadow patterns and `_vec0_` shadow tables; `VectorDBViewer.cs:18-37,157`, listed at `:480-482`). The contents list now covers the three vec0 collections plus data-group tables, precomputed Q&As, semantic-model tables and the embedding cache (`VECTOR_DATABASE_RAG_SUMMARY.md:20-26,125-170`).
- Baseline's claim that the viewer edits "raw rows" is accurate; added that few-shot records are deleted through the knowledge-base store so the scalar row and vector row go together (`VectorDBViewer.cs:14-15,98-99,143-151`).
- Kept: the caution block, the missing-file informational message (`Message.VectorDatabaseNotFoundFormat`), and both File menu commands with their exact wording (`SchemaLibraryForm.resx`: `openSchemaLibraryFolderToolStripMenuItem.Text = "Open Schema Library Folder"`, `openVectorDatabaseToolStripMenuItem.Text = "Open Vector Database"`). Viewer form title is **Vector Collection Viewer** (`VectorDBViewer.cs:137`).
- Removed: the baseline's `value_index` description as "Value mappings"; it is now described in plain language as the value index (data values extracted from legacy scripts, used for term→stored-value mapping).

Heading changes: `## What the vector database contains` added; `## Where the library lives` changed in body only (heading kept). No renames.

---

## Cross-page issues for other owners (do not fix here)

1. `schema-library-form.md` (not mine) still documents **Save Semantic Model** in the File menu (line 60) and says selecting the **semantic-model** folder opens the editor on the latest active model (line 122) — both differ from the shipping build. It also calls the ingest dialog **Import Legacy Scripts** (line 56) when the dialog title is **Learn from Past Projects**.
2. My pages link to `ai-agent-manager-window.md`, `ai-settings.md`, `schema-library-form.md`, `browse-and-edit-schema-content.md`, `rebuild-vector-index.md`, `add-to-knowledge-base.md`, `semantic-models.md`, `data-groups-and-precomputed-qas.md`, `learn-from-past-projects.md`, `create-build-in-ai-agent.md` — all exist in the manual folder.
3. The leftover `Menu.SaveSemanticModel` and `Menu.AddValueIndexes` resource strings, and the unreachable `DescribeWithToolStripMenuItem_Click` handler, are dead code in OctofyPro; worth deleting in the product, not in the manual.

## Screenshots

None of the seven baseline pages contains a `## Screenshots` section or any `![...](images/....png)` line, so nothing had to be preserved byte-for-byte and no image reference was invented.

## Proposed new page (not created)

Two-tier ingestion has grown past what one page can carry, but it is a coherent separate topic only if it is taught as the pipeline reference. Proposal:

- **Filename:** `knowledge-ingestion-pipeline.md`
- **Title:** `Knowledge Ingestion Pipeline`
- **Outline:**
  1. `## Why ingestion has two tiers` — one project's data usually comes from another project; the folder alone cannot resolve the column behind an intermediate table.
  2. `## Tier 1 — learning from a folder` — sources, units, the trust gates (evidence, generic, cap, schema, yield), the canonical vocabulary pre-pass.
  3. `## Staging versus feeding the generator` — what a staging run writes, what it defers, and how to tell which mode a run used.
  4. `## Tier 2 — distillation` — lineage stitching, metric unrolling, dimension re-pointing, project-count recurrence, conflict escalation, glossary aliases.
  5. `## The review surface` — business rules, the quarantine ledger, the run manifest, the distillation manifest.
  6. `## Resumability and idempotency` — run state, settings hash, content hashes, deterministic content keys.
  7. `## Files on disk` — the `kb/` layout (`rules.json`, `quarantine.json`, `glossary.json`, `skill.md`, `wiki/`, `ingestion-state.json`, both manifests).
  8. `## Related topics`

`learn-from-past-projects.md` currently carries all of this in condensed form and would keep the user-facing steps plus a pointer to the new page.

## Status summary

| File | Status |
| --- | --- |
| `learn-from-past-projects.md` | rewritten |
| `data-groups-and-precomputed-qas.md` | updated |
| `tool-functions.md` | rewritten |
| `ai-assisted-descriptions.md` | updated (one command removed) |
| `semantic-models.md` | updated (one command removed) |
| `add-to-knowledge-base.md` | rewritten |
| `manage-library-folder-and-vector-db.md` | updated |
