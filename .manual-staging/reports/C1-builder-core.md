# C1 — Builder Core (New Agent Wizard + Schema Library Form)

Six pages updated. All claims below were verified against the current working tree of
`C:\Users\sherl\source\repos\OctofyPro` (v8.8.3.0, HEAD `612912fc`), whose newest
`OctofyPro/Docs/SCHEMA_LIBRARY_FORM.md` revision (rev 3, 2026-09-20) is itself behind the
code in places (noted below). Output written to
`...\.manual-staging\new\<filename>.md`.

## Global finding that drove most edits

The Schema Library menu bar was **reorganised** in commit `c1fed3a1` ("changed the menu
structure for SchemaLibraryForm", 2026-09-20) and extended by `00000724` ("Added dynamic
value-index node to object node") and `db8703a3` ("Show tools/semantic-model lists in
Schema Library grid"). The baseline pages still described the pre-reorganisation menus
(`File / View / Edit / Column / Data Group / AI Assistant`, with `File > Add to Knowledge
Base`, `File > Add Value Indexes`, `File > Save Semantic Model`). Every baseline page
touched by the menu bar was therefore factually wrong, not merely stale in detail.
Authority for exact wording: `OctofyPro/AI/SchemaLibraryForm.Designer.cs` (menu item
tree, L152/L158/L230/L254/L278/L318/L365/L384/L403) plus the `*.Text` values in
`OctofyPro/AI/SchemaLibraryForm.resx`.

Current menu bar (Designer L152):
`File | View | Edit | Schemas | Data Groups | Tools/Functions | Semantic Model | Value Index`

- File: Open Schema Library Folder, Open Vector Database, Add Knowledge Base, Sync, Rebuild, Rebuild Vector Index, Learn from Past Project, Exit
- View: Review Check List (Ctrl+R), AI Assistant
- Edit: Cut, Copy, Paste (Ctrl+X/C/V)
- Schemas: Add objects, Add Column Reference, AI Describe, AI Batch Describe
- Data Groups: Add, Remove, Add Objects, Generate Keywords, Manage Anticipated Questions, Sync Vectors
- Tools/Functions: Add, Remove
- Semantic Model: Add, Remove
- Value Index: Add, Remove

Removed from the product and therefore from the pages: the top-level **Column** menu
(became **Schemas**), the top-level **AI Assistant** menu (its `Describe`/`Describe
with…`/`Describe missing`/`Batch Describe` commands became **Schemas > AI Describe / AI
Batch Describe** plus the toolbar **Describe Missing** and the right-aligned **AI
Assistant** chat toggle), **Save Semantic Model**, **File > Add Value Indexes**,
**File > Add to Knowledge Base**. `Describe with…` and `Undo`/`Redo`/`Select All` have
**no** designer wiring at all in the current tree (handlers `DescribeWithToolStripMenuItem_Click`
L3656 and `UndoToolStripMenuItem_Click` L4293 are dead code; `Menu.DescribeWith`,
`Menu.Undo`, `Menu.Redo`, `Menu.SelectAll`, `Menu.SaveSemanticModel` are unused resx keys),
so they were removed from the manual.

---

## 1. `create-build-in-ai-agent.md` — status: COMPLETE

### Heading renames (old → new)

| Old | New | Why |
| --- | --- | --- |
| `## Start from Add New Data Source` | `## Start from Add New DB Connection` | The command in the main window is `addNewDBConnectionToolStripMenuItem.Text = Add new DB Connection` (`OctofyPro/AdvancedQuery/AdvancedQueryAnalysisForm.resx`; menu parent confirmed at `AdvancedQueryAnalysisForm.Designer.cs:183`). |
| `## Start from Manage Data Sources` | `## Start from Manage DB Connections` | `manageConnectionsToolStripMenuItem.Text = Manage DB Connections` (same files). |

No anchor in `toc.json` references either heading, and nothing in the folder links to those
anchors, so the renames are safe.

### Changes with evidence

- **"Manage Agents" → "Add New Agent"; "Manage Schema Library" → "Create Agent" (new agents only).**
  `NewSQLServerConnectionDialog.resx`: `newAgentsButton.Text = Add New Agent`, `agentLabel.Text = Agent:`, `$this.Text = New Connection Dialog`.
  `ConnectionManageForm.resx`: same button, `$this.Text = Manage Connections`.
  `AIAgentManager.cs:475-479`: `schemaLibraryButton.Text = AddNew ? SR("schemaLibraryButton.CreateAgent.Text") : SR("schemaLibraryButton.Text")` → **Create Agent** vs **Manage Schema Library** (`AIAgentManager.resx`: `schemaLibraryButton.CreateAgent.Text = Create Agent`). The Agent drop-down includes `(None)` (`NewSQLServerConnectionDialog.cs:455`); the baseline's invented "AI Agent section"/"Octofy AI Agent section" wording was replaced by the real group box caption **Octofy AI Agent** (both dialogs' `chatGPTGroupBox.Text`).
- **Wizard-draft behaviour corrected.** `NewAgentWizard.cs:1885-1962`: `PersistDraftState()` writes `%APPDATA%\Sherlock Software Inc\Octofy\wizard-drafts\new-agent-{key}.json` on every name/description/radio/object/group change, on a successful schema build (L1435) and on `FormClosing` when the dialog result is not OK (L1974); `LoadDraftState()` (L1907) restores agent name, description, scratch/reuse choice, folder fields, selected objects and **checked data-group file names**; `RemoveDraftState()` runs only from `BtnFinish_Click` (L950). Added the explicit list of what is restored and that Finish clears it.
- **Nine-step list re-verified** against `WizardStep` (L15-26) and the `lblStepTitle` texts (L864-876): `Step 0 - Precheck` … `Step 8 - Review`. Step titles/order unchanged from the baseline.
- **Step 0 wording.** `Wizard.Precheck.Help`/`Wizard.Validation.PrecheckRun`; `RunPrecheckAsync` (L1029-1060) creates a fresh `DBSchema`, `OpenAsync(loadColumns: true)`, assigns `Connection.DBSchema`, and returns `false` on failure so the wizard stays on the step.
- **Step 1 folder naming corrected.** `DataSourceFolderResolver.ResolveFolderName` (`Octofy.Agent/AI/BuiltIn/DataSourceFolderResolver.cs:11-38`) adds `_{dbms}` (lowercased) for every DBMS other than SQL Server/Other, plus `RequiresDbmsSuffix`/`BuildBaseFolderName`; ODBC keeps `{DSN}_ODBC`. The preview shows the **full path** with state `New`/`Exists` (`ResolveFolderPreview` L1795-1805, `Wizard.AgentFolder.Format`); the baseline implied a bare folder name. The unique-name suffix format is `"{baseName} ({suffix})"` starting at 2 (`GetUniqueAgentName` L195-210) — the baseline's vague "numeric suffix" is now exact. The folder can also come from an existing agent's `SchemaDataDirectory` (L1807-1829).
- **Step 2** now states the description is required (`ValidateCurrentStep` L891) and that **Generate with AI** needs both the precheck metadata (L1067) and a configured LLM (L1073).
- **Step 3 corrected.** Selector is `DBObjectsSelectForm` (L1265-1287) with title **Database Objects Selector**; object types are `All` / `Table` / `View` / `Function` (`DBObjectsSelectForm.cs:73-79`) — the baseline's `(All)` was confirmed wrong against `ObjectType.All = All` (only **Schema** uses `(All)`). Import accepts line breaks, commas **and semicolons** (L1334) and reports skipped items via `Wizard.Objects.ImportPartial` (L1375).
- **Step 4 corrected.** It is `SchemaLibraryBuilder.RebuildAsync(..., selectedObjects: ...)` restricted to the chosen objects (`RunSchemaBuildAsync` L1421-1429), not a generic "build"; it calls `PrepareDataSourceFolder` (L1452) which is where the double-confirmed delete-and-rebuild happens.
- **Step 5** unchanged in substance; added that at least one group must be kept to continue (`Wizard.Validation.DataGroupProposal` L894). Falsifiable baseline wording "If the data source already has data groups" is consistent with `LoadGroupProposalsFromIndex` (L1534 reads `data-groups\.data-group-index.json`).
- **Step 6** now lists what actually happens: uncheck-delete of group files, rewrite of `.data-group-index.json` **and** the `.data-groups` map (`RunDataGroupBuildAsync` L1696-1716), then `GenerateDataGroupQaAsync` per kept group (L1733).
- **Step 7** now names the operations verified in `GroupQAPanel.resx`: `Add`, `New by AI`, `AI Auto Approve`, `Open`, `Verify`, `Regenerate`, `Approve`, `Delete` (the baseline omitted **Verify**), and the no-groups case (`Wizard.QaReview.NoGroups` L1622).
- **Step 8 summary made exact** (`BuildReviewSummary` L1766-1780): schema Added/Updated/Removed, data groups Kept/Deleted, review items count, list format `[category] location - detail`; the checklist dialog is shown once (`_reviewDialogShown`, `ShowReviewDialogForCurrentRun` L1782-1793).
- **Validate section** now quotes the real test result text `Message.BuiltInAgentReady = Built-in agent is ready.` and the toolbar button name `Test` (`AIAgentManager.resx`, `AIAgentManager.cs:278-348`).
- Added one sentence that Next/Back/Finish/Cancel are disabled while busy and **Cancel Task** becomes available (`UpdateNavigationState` L911-925).

### Unverifiable / deliberately not asserted

- The exact `%APPDATA%` draft path is derived from `DraftFilePath` (L1865-1883); the manual
  text keeps it generic ("reopening the wizard for the same connection restores your draft")
  to avoid promising a user-browsable path.
- `EnsureDataSourceMarkdown` (L1492-1510) still hard-codes `**Type:** SQL Server` for every
  connection type. This is a product inconsistency, not manual content, so it was not
  documented.

---

## 2. `schema-library-form.md` — status: COMPLETE (largest rewrite)

### Heading renames (old → new)

| Old | New |
| --- | --- |
| `## Column menu` | `## Schemas menu` |
| `## Data Group menu` | `## Data Groups menu` |
| `## AI Assistant menu` | `## AI Assistant (chat panel)` |

Three new headings were added for the new top-level menus (no baseline counterpart):
`## Tools/Functions menu`, `## Semantic Model menu`, `## Value Index menu`.
No `toc.json` entry references any of these headings (toc.json only carries `doc` +
`section` for other pages), and no sibling page links to them, so anchors keep working.

### Changes with evidence

- **Open section**: kept, plus the note that the button reads **Create Agent** and starts the
  New Agent Wizard while the agent is being added (`AIAgentManager.cs:475-479`, `ShouldOpenNewAgentWizardForBuiltInAdd` L594-603).
- **Layout rewritten.** Menu bar list updated to the eight current menus. Toolbar is
  `New | Cut | Copy | Paste | Describe Missing | AI Assistant` (`SchemaLibraryForm.Designer.cs:441`,
  texts from resx). Added the **AI Assistant panel** as a fifth area — docked right, collapsed
  at load (`SchemaLibraryForm_Load` forces `_chatPanel.Visible = false` + `Collapse()`; Designer
  `Controls.Add(_chatSplitter)/_chatPanel` L592-593) — and removed the baseline's claim that
  the Column/Data Group/AI Assistant menus carry the describe/edit commands.
- **Tree section**: added the **value-index children**. `SchemaLibraryPanel.cs:1337-1341` adds a
  `ValueIndexPlaceholderNode` (`Node.ValueIndexLoading = Loading...`) under each table/view;
  `ResultsTreeView_BeforeExpand` (L1107) → `LoadValueIndexColumns` (L1118-1172) replaces it with
  one `ValueIndexColumnNode` per indexed column read from `vector-index.db`
  (`ValueIndexVectorService.ListIndexedColumnsAsync`), tooltip
  `ToolTip.ValueIndexColumnFormat = {0}.{1}.{2} - {3} value(s)`; statuses
  `Status.ValueIndexColumnsLoaded` / `...NotFound` / `...Unavailable`. Folder-name rule widened
  to the DBMS-suffixed form (see file 1). Node display text for the semantic branch is
  **Semantic Model** (`Node.SemanticModel = Semantic Model`) while the key stays `semantic-model`
  (`SemanticModelNodeKey` L19) — the docs' `semantic-model` label was left as the branch name
  because that is what the code matches on.
- **File menu table rebuilt** and each row checked against its handler:
  Open Schema Library Folder L2294; Open Vector Database L4489; **Add Knowledge Base** L4518
  (menu text `addKnowledgeBaseToolStripMenuItem.Text = Add Knowledge Base`) → `AddToKnowledgeBaseForm`,
  `SemanticModelCheckBoxEnabled = BuiltIn && folder set` (L4540-4542), `ExtractHybridAsync` +
  pre-seeded `SemanticModelEditForm` (L4562-4578); Sync L3547; Rebuild L2428;
  Rebuild Vector Index L2580; **Learn from Past Project** L2317 (`importLegacyScriptsToolStripMenuItem.Text = Learn from Past Project`)
  → `LegacyScriptImportForm { SchemaLibraryFolder = _dataSourceFolder }`; Exit L2289.
  Removed: Save Semantic Model (`Menu.SaveSemanticModel` is an unused resx key — the only
  remaining `SaveSemanticModel*` identifiers are the internal auto-save methods L3258/L3292/L3309).
- **View menu**: command is **Review Check List** (resx `reviewChecklistToolStripMenuItem.Text = Review Check List`),
  `Ctrl+R` (resx `ShortcutKeys`), handler L4304 (`CollectReviewItemsFromDisk`, "no items"
  information box from `Message.NoReviewItemsFound`). Added the **AI Assistant** toggle row
  (`aiAssistantViewToolStripMenuItem`, handler `AiChatToolStripButton_Click`).
- **Edit menu**: reduced to Cut/Copy/Paste with Ctrl+X/C/V. **Undo, Redo and Select All were
  removed** — they are not in `editToolStripMenuItem.DropDownItems` (Designer L254), their
  handlers are unreferenced, and no `KeyPreview`/`ProcessCmdKey`/`KeyDown` override exists in
  `SchemaLibraryForm.cs` (grep for `KeyPreview|ProcessCmdKey|KeyDown|ShortcutKeys` returns nothing).
- **Schemas menu** (was `Column menu`): **Add objects** moved here from the old File menu
  (`addDatabaseObjectsToolStripMenuItem`, handler L4586); **Add Column Reference** retained but
  correctly described as belonging to the object editor surface (handler L2402,
  `UpdateColumnMenuState` L594-602); `AI Describe` / `AI Batch Describe` replaced
  `Describe`/`Describe with…`/`Describe missing`/`Batch Describe` (Designer L278;
  `DescribeWithToolStripMenuItem_Click` L3656 has no designer wiring and is dead code).
- **Data Groups menu**: **Add** now carries the real behaviour (`NewDataGroupToolStripMenuItem_Click`
  L4340: `InputBox` with `MaxLength = 64`, invalid-character and duplicate rejection,
  `DBObjectsSelectForm`, auto description/keywords, optional LLM Q&A, tree reload); **Remove**
  is new (`RemoveDataGroupToolStripMenuItem_Click` L631, confirmation
  `Message.ConfirmRemoveDataGroup`); **Add Objects**/**Generate Keywords** keep their
  surface gating; **Manage Anticipated Questions**; **Sync Vectors**
  (`SyncDataGroupVectorsToolStripMenuItem_Click` L4335). The baseline's separate
  `New data group` row was merged into `Add`.
- **New menu sections** written from code: Tools/Functions Add/Remove
  (`AddToolFunctionToolStripMenuItem_Click` L4055 → modal `ToolFunctionEditForm`;
  `RemoveToolFunctionToolStripMenuItem_Click` L4065, `Message.ConfirmRemoveToolFunction`);
  Semantic Model Add/Remove (`AddSemanticModelToolStripMenuItem_Click` L4106;
  `RemoveSemanticModelToolStripMenuItem_Click` L4117, `Message.ConfirmRemoveSemanticModel`
  — deletes the model and its embedding); Value Index Add/Remove
  (`AddValueIndexesToolStripMenuItem_Click` L4699 → `ValueIndexColumnSelector` →
  `RunValueIndexUpdateAsync` L4738; `RemoveValueIndexesToolStripMenuItem_Click` L4841 →
  `RunValueIndexRemoveAsync` L4887, confirmation `Message.ConfirmRemoveValueIndexes`), both
  requiring `ValueIndexVectorService.TryCreateFromGlobalSettings` and reporting
  `Message.ValueIndexProviderNotConfigured` otherwise.
- **New "AI Assistant (chat panel)" section.** Content limited to user-visible behaviour:
  collapsed at start, toggle labels, LLM requirement, the real-data consent prompt (the
  baseline never mentioned it), context follows the tree selection, one action applied to the
  active embedded editor, mode-match error, and the fact that only appended precomputed
  questions persist immediately. Evidence: `UpdateChatEditingContext` /
  `ExecuteSchemaLibraryChatAction` / `ExecutePopulateTool` / `ExecuteUpdateObject` /
  `ExecuteAppendQuestions` / `ExecuteUpdateSemanticModel` in `SchemaLibraryForm.cs`,
  `DataChatControl.SchemaLibrary.cs`, `AiChatToolStripButton_Click`, and
  `SCHEMA_LIBRARY_FORM.md` §15.7/§15.8. Note: rev 3 of the internal doc says `KeepChatHistory = true`;
  the code now sets **`false`** (`SchemaLibraryForm.cs:128`). That is an internal detail and the
  manual says nothing about session persistence.
- **Toolbar table**: `New` is documented with its *real* behaviour (name prompt → empty group
  markdown + index entry; no object selection, no Q&A — `NewToolStripButton_Click` L2334;
  the baseline wrongly equated it with **Data Group > New data group**, which was accurate
  only for the *old* menu). **Describe Missing** now says what it fills; the **AI Assistant**
  toggle row was added.
- **Tree/content table rebuilt**: the `tools` and `semantic-model` **folder** nodes now show
  list grids instead of opening an editor (`SchemaLibraryPanel1_AfterSelect` L3085-3123;
  `ShowToolFunctionPreview` L892, `ShowSemanticModelPreview` L983), the value-index column
  selection shows `ShowValueIndexValuesPreview` (L833, `GridPreviewMode.ValueIndexValues`,
  `Status.ValueIndexValuesFormat`), and `_data-source.md` / read-blocked markdown are stated
  precisely (`IsMarkdownReadBlocked` L3353, `Status.ReadBlockedMarkdownFormat`,
  `Status.SaveBlockedMarkdown`). The baseline's "`_data-source.md` … the only markdown file
  that is editable as text" was kept and made exact.
- **Grid preview editing**: added the **tools** and **semantic-model** row behaviour
  (`EditGridRowAt` L1149-1181 → `OpenToolFunctionEditor` L1075 / `OpenSemanticModelEditor`
  L1099-1111) and that the value-index preview is read-only.
- **Context menu**: corrected the **Add** gating (`ContextMenuStrip_Opening`
  `SchemaLibraryPanel.cs:1174-1186` enables **Add** on the `data-groups` **and** `tools`
  roots — the baseline mentioned only data groups) and the **Add Semantic Model** label
  (`Menu.EditSemanticModel = Add Semantic Model`, enabled only on the `semantic-model` folder
  node). `Edit Function Call Definition` is enabled only on a level-2 tool node.
- **Save behavior**: unchanged in substance; added that a save attempt on read-blocked
  markdown is refused and that the semantic model editor has **no** separate save command
  (`SavePendingEditorChanges` L3254 → semantic → object → data group → tool function → text;
  `FormClosing` L2736 cancels the close once to flush the semantic model). The baseline's
  "Save Semantic Model" File-menu row was deleted.
- **First-time setup**: corrected the sequence to match `RunLoad` (L2710 bootstrap →
  `_startupBuildTimer` → `BuildBasicAsync` → `BeginInvoke(RebuildToolStripMenuItem_Click)`,
  i.e. the full rebuild **also shows its own confirmation prompt**, `SCHEMA_LIBRARY_FORM.md`
  §20.6) and added the files actually created (`.data-groups` placeholder, `_index.md` entry).

### Unverifiable / kept as-is

- **`## Screenshots` / image lines**: this page's baseline section is `## Screenshot` (singular)
  with `![Schema Library form](images/Schema_Library.png)`; both were preserved **byte-for-byte**
  (verified by diff). No image reference was added or changed. The target
  `images/Schema_Library.png` is not present in the manual folder listing, but the rule is to
  never invent or alter image references, so it was left untouched.
- Grid column headers are documented from `GridHeader.*` resx values (`schema_name`,
  `object_name`, `object_type`, `group_name`, `tool_name`, `protocol`, `model_name`,
  `model_id`, `status`, `description`, `Value`) rendered in **bold** as the visible header
  text; the resx stores lowercase identifiers and I did not claim a specific casing beyond
  the key name.

---

## 3. `browse-and-edit-schema-content.md` — status: COMPLETE

No heading renames.

### Changes with evidence

- **Tree table**: added the value-index children (same evidence as file 2) and a new paragraph
  describing the search box and the fact that search-result nodes carry no file path so their
  content area is empty (`SCHEMA_LIBRARY_FORM.md` §5 `RunSearch`, panel L823/L924).
- **Selection table**: `tools` folder → tool list grid; `semantic-model` folder → model list
  grid; added the **Value-index column node** row; added the **read-blocked markdown** row.
- **Text editor**: replaced the baseline's "**Undo / Redo**, **Cut / Copy / Paste**, and
  **Select All** from the **Edit** menu" with the current Edit menu (Cut/Copy/Paste only) and
  the editor's own Ctrl+X/C/V; added a paragraph that object/data-group/tool markdown is read
  blocked and that saving such a file is refused.
- **Grid previews**: added the tools/semantic-model list behaviour and the read-only
  value-index preview.
- **Embedded editors**: added the **tool function editor** and **semantic model editor**
  bullets (the baseline listed only the object and data-group editors even though the
  selection table promised all four).
- **Context menu**: corrected the **Add** gating (data-groups **and** tools roots).
- **Save behavior**: added the read-block refusal.

### Kept as-is

The `## Related topics` links (all four files exist in the manual folder).

---

## 4. `add-database-objects.md` — status: COMPLETE

No heading renames.

### Changes with evidence

- **Command corrected**: `**File > Add Database Objects**` → `**Schemas > Add objects**`
  (`columnToolStripMenuItem.DropDownItems` Designer L278 first child
  `addDatabaseObjectsToolStripMenuItem.Text = Add objects`).
- **Object Type list corrected**: `All`, `Table`, `View`, `Function`
  (`DBObjectsSelectForm.cs:73-79`, `ObjectType.All = All`). Only **Schema** uses `(All)`
  (`Schema.All = (All)`, L455/L470/L497).
- **No-selection vs no-new-selection split** (`AddDatabaseObjectsToolStripMenuItem_Click`
  L4586-4689): empty selection → `Message.SelectAtLeastOneObject`; all-duplicate selection →
  `Status.NoNewObjectsSelected` = "No new objects selected. All selected objects already exist."
- **Added** that data-source keywords are refreshed (`UpdateDataSourceKeywordsFromObjects`,
  L4668) and that a scoped `RebuildAsync(..., selectedObjects:)` runs (L4658).
- **Notes corrected**: the lock message now names the real commands disabled by
  `SetRebuildUiState` (L2238-2255: Rebuild, Sync, Rebuild Vector Index, Add/Remove Value Index,
  plus tree/grid/editors) instead of the baseline's vague "rebuild/sync commands"; added the
  "schema library folder loaded" precondition (`Status.NoSchemaLibraryLoaded`, L4588-4592).

### Unverifiable

`F4`/`F8` are confirmed (`openTableSchemaToolStripMenuItem.ShortcutKeys = F4`,
`previewDataToolStripMenuItem.ShortcutKeys = F8`, toolbar captions
`Open Table Schema (F4)` / `Preview Data (F8)`), so the baseline claim was kept.

---

## 5. `sync-and-rebuild.md` — status: COMPLETE

### Heading renames (old → new)

| Old | New |
| --- | --- |
| `## Review Checklist (View > Review Checklist…, Ctrl+R)` | `## Review Checklist (View > Review Check List, Ctrl+R)` |

The old heading embedded the pre-reorganisation menu path and the ellipsis-bearing command
name. The new heading uses the confirmed command text (`reviewChecklistToolStripMenuItem.Text
= Review Check List`) and the current **View** menu.

### Changes with evidence

- **Scope table corrected.** The baseline had three rows. The root/data-source node is its
  own scope: `selectedLevel == 0` → `RebuildSchemaCollectionOnlyAsync`
  (`RebuildToolStripMenuItem_Click` L2530-2542). The baseline's "Anything else (folder/root)
  → Full data source" was wrong for the root node.
- **Sync section corrected.** The object scope calls **`RebuildObjectAsync`**, not a sync
  method (`SyncToolStripMenuItem_Click` L3600-3612; `SyncSchemaAsync` L3613 for schema nodes,
  `SyncAsync` L3625 otherwise, with `Status.SyncCompletedFormat` counts). This internal quirk
  is now stated as user-visible behaviour ("the object's markdown is regenerated"). Added the
  wait-cursor/no-confirmation facts.
- **Rebuild section corrected.** Confirmation prompt text now quoted accurately from the
  scope keys (`Status.ScopeRebuildObjectFormat` / `…SchemaFormat` / `Status.ScopeRebuildFull`
  plus `Prompt.RebuildCanTakeAWhileFormat` and `Prompt.ContinueQuestion`); the review checklist
  is shown only for the **full** scope (`showReviewChecklist = true` only in the full branch,
  L2555/L2562) — the baseline implied it generally. Added the missing-folder path
  (`ResolveOrCreateDataSourceFolderAsync` L2629-2648 asks "The schema library folder '{0}'
  does not exist. Build now?" and reports `Status.SchemaLibraryCreatedAddedFormat`).
- **Lock state corrected** to the real `SetRebuildUiState` set (see file 4).
- **Review Checklist section** expanded with the actual categories from
  `SchemaLibraryReviewForm.cs:147-157` (Objects Missing Descriptions, Schemas Missing Purpose,
  Data Source - Required Fields, Data Coverage - Needs Update, Missing Keywords, Function
  Usage Examples - Review Needed, Precomputed Q&A - Review and Approve) and the dialog title
  `Title.ReviewChecklist = Review Checklist`, empty-state `Message.NoReviewItemsFound`.

### Unverifiable

`SyncObjectAsync` exists in `SchemaLibraryBuilder` but has **no callers** in the repo, which
is why the object-scope text describes a rebuild rather than a sync.

---

## 6. `rebuild-vector-index.md` — status: COMPLETE

No heading renames.

### Changes with evidence

- **Menu path corrected**: `**File > Rebuild vector index**` → `**File > Rebuild Vector Index**`
  (`rebuildVectorIndexToolStripMenuItem.Text = Rebuild Vector Index`).
- **Confirmation text made exact** from `Prompt.RebuildVectorIndexFormat` ("Rebuild vector
  index for '{0}'?") and `Prompt.RebuildVectorIndexDetail` ("This recreates vector-index.db
  from current schema library files."), dialog title `Title.RebuildVectorIndex`
  (handler L2580-2627).
- **Result strings quoted exactly**: `Status.VectorIndexRebuildCompletedIndexedFormat` and
  `Status.VectorIndexRebuildCompletedNoObjects` (the baseline paraphrased them).
- **Added the value-index caveat**: the command re-ingests object markdown only
  (`SchemaLibraryBuilder.RebuildVectorIndexFromDiskAsync`, L2611) and does not restore the
  value-index records that the **Value Index** menu manages — a real user-visible gap the
  baseline did not mention.
- **Notes corrected**: the no-folder message is `Status.NoSchemaLibraryFolderLoaded` (a
  readiness check), and `SetRebuildUiState(true)` disables the menu and the other rebuild
  commands during the run.

### Unverifiable

The claim that the rebuild "reads the markdown files … and re-embeds them using the
configured embedding provider" comes from `SCHEMA_LIBRARY_BUILDER_BUILT_IN_AGENT.md`
(`RebuildVectorIndexFromDiskAsync` - "Rehydrate vector index from existing markdown files")
and `VECTOR_DATABASE_RAG_SUMMARY.md` §4; the embedding-failure path is silent by design, so
the manual does not promise an error when no embedding provider is configured.

---

## Cross-page checks

- **Images**: for all six files the set of `![...](...)` lines is byte-identical to the
  baseline (only `schema-library-form.md` has one). Nothing was added, removed, or renamed.
  The rule text mentioned `## Screenshots`; the actual section in this page is
  `## Screenshot` and was preserved verbatim.
- **Headings**: full before/after comparison run for all six files. Every difference is
  listed above; all other headings are byte-identical, so all existing anchors resolve.
- **Links**: every relative link target in the six new files was checked against the manual
  folder listing; all targets exist (only `images/Schema_Library.png` is outside the listing,
  preserved verbatim as required).
- **Markdown dialect**: all six files were machine-checked for blockquotes, nested bullets,
  and h5+ headings and are clean (h1-h4, bold, inline code, links, flat bullets, numbered
  lists, pipe tables only).
- **Not touched**: `toc.json`, `user-manual.md`, and every page not in the C1 list.

## Note for the coordinating agent

Two stale references to the same commands exist in pages owned by other agents and should be
reconciled for consistency:

1. `.manual-staging\baseline\add-to-knowledge-base.md` line 3 and line 7 say the command is
   `File > Add to Knowledge Base`; the menu text is **`File > Add Knowledge Base`**
   (`addKnowledgeBaseToolStripMenuItem.Text = Add Knowledge Base`). The dialog itself is still
   titled **Add to Knowledge Base**, so only the menu path is wrong.
2. `schema-library-form.md`'s own **Related topics** list keeps the label
   `[Add to Knowledge Base](add-to-knowledge-base.md)` (the page title, not the menu path),
   which is consistent with the target page's `# Add to Knowledge Base` heading and so was
   left unchanged.

`built-in-agent-guide.md` also still describes pre-reorganisation menu paths
(**Tools ? AI Provider Settings**, **File ? Manage Connections**, **View ? Open Schema
Library Folder**) and is stale, but it is a `OctofyPro/Docs` input document, not a manual
page, so it was used only as corroboration and never as authority.
