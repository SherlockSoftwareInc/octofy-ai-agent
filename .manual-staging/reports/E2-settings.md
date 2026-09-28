# E2 — Settings pages verification report

Scope: three public manual pages updated to match Octofy Pro desktop HEAD `612912fc` (v8.8.3.0).
Baseline: `.manual-staging/baseline/`. Output: `.manual-staging/new/`.
Evidence paths are relative to `C:\Users\sherl\source\repos\OctofyPro\`.

---

## 1. `ai-settings.md` — status: UPDATED (rewritten, structure preserved)

Dialog title, group-box names, toolbar and default values were re-confirmed against the `.resx`
(the authoritative source for user-visible wording).

### Confirmed as still correct (no change)

- Dialog title **AI Provider Settings** — `AISettingsForm.resx`: `$this.Text = [AI Provider Settings]`.
- Group boxes: `settingsGroupBox.Text = [LLM Settings]`,
  `embeddingGroupBox.Text = [Embedding Settings (Vector Search)]`,
  `precomputedGroupBox.Text = [Precomputed Query Routing]`,
  `_semanticGroupBox.Text = [Semantic Options]`. The section name
  **Precomputed Query Routing** still exists with exactly that wording.
- Toolbar buttons and order: `AISettingsForm.Designer.cs:80` →
  `okToolStripButton, cancelToolStripButton, toolStripSeparator1, testToolStripButton, helpToolStripButton`
  (`&OK`, `&Cancel`, `Test Connection`, `Help`).
- Provider → suggested-model mapping and every model string in the provider table:
  `AISettingsForm.cs:29-41` and `:172-216`. General fallback list: `:21-27` (matches baseline verbatim).
- zh locale endpoint ordering: `AISettingsForm.cs:218-228` + `:67-81`.
- API key masked by default: designer default is `Checked = true` but
  `AISettingsForm.cs:109` sets `showApiKeyCheckBox.Checked = false`, so masked on open.
- OK/Cancel/Test behaviours, 30 s test timeout (`:286`), Gemini `GET /v1beta/models` probe (`:369-373`),
  Azure `?api-version=2024-02-01` (`:359-363`), "model exists in provider list" fallback (`:402-406`),
  embedding probe input `"test"` (`:513`, `Probe.EmbeddingInput = [test]`), status-bar double-click copy
  (`:855-858`).
- Embedding fields/labels and the embedding-change confirm + rebuild messages (`:604-629`, `Prompt.EmbeddingChange*`).
- Threshold/BM25 defaults: `AISettingsForm.cs:114-120`; `Octofy.Agent\AI\LLMProviderSettings.cs:42-52`
  (BM25 off, weight 0.5, k1 1.2, b 0.75).
- Semantic fallback default = on (`LLMProviderSettings.cs:58`).
- Status bar and "double-click to copy" behaviour.

### Changes made (with evidence)

| Change | Evidence |
| --- | --- |
| Menu path **Tools > AI Settings** → **AI Assistant > AI Settings** | `AI Settings` (`aISettingsToolStripMenuItem`) is added to `chatbotToolStripMenuItem` whose text is `AI Assistant`, and `chatbotToolStripMenuItem` is a top-level menu: `AdvancedQuery\AdvancedQueryAnalysisForm.Designer.cs:633` and `:177`; `AdvancedQueryAnalysisForm.resx`: `chatbotToolStripMenuItem.Text = [AI Assistant]`, `aISettingsToolStripMenuItem.Text = [AI Settings]`. The **Tools** menu contains only `Options` + `Edit box font` (`Designer.cs:588`). No code re-parents the item. |
| Help button described as **Help** (question-mark icon with text), not "**?** (Help)" | `helpToolStripButton.Text = [Help]`; icon is `SystemIcons.Question` (`Designer.cs:115`). |
| OK now documented as requiring endpoint **and** API key **and** model | `AISettingsForm.cs:776-795` `ValidateInputs()` (no Ollama exemption), so the file's previous blanket "API key … Not required for local Ollama endpoints" was narrowed to Test/Refresh only (`:300-305`, `:898-904`). |
| OK now described as two prompts: confirm change, then "Schema Library Rebuild Recommended" | `:604-629`. |
| Model refresh endpoint list corrected/expanded: `/compatible-mode/` special case, `{version}` = version segment found in the path (default `v1`) | `:993-1030` `BuildModelsListUrl`. |
| Model refresh result behaviour added (keeps selection, else selects the first; status reports count/failure) | `:931-951`, `Status.ModelsLoaded`, `Status.RefreshModelsFailed`, `Error.NoModelsReturned`. |
| Ollama row of the provider table corrected: no pre-populated list for `localhost:11434`; **Refresh** loads `/api/tags` | `GetSuggestedModelsForEndpoint` (`:172-216`) has no Ollama branch, so it falls through to `SuggestedModels`; `/api/tags` is only used by refresh (`:1004-1005`). |
| Added the chat-completions-unsupported hard failure to Test Connection | `:399-400`, `:445-453`. |
| Added sentence that the dialog has no tabs and lists its five groups | `AISettingsForm.Designer.cs:379-385` (no `TabControl`; five `GroupBox` controls + status label). |
| **New section `## AI Data Analysis`** | `_previewGroupBox.Text = [AI Data Analysis]`; `_enableAiDataAnalysisCheckBox.Text = [Allowing AI to analyze real data]`; `Designer.cs:361-373`; default off `LLMProviderSettings.cs:61`; consent prompt on enabling, reverts to off if declined `AISettingsForm.cs:252-273` (`Prompt.AiDataAnalysisConsentTitle = [AI Data Analysis Consent]`, body `Properties\Resources.resx` A245). |
| **New row `Object search vector threshold`** in Precomputed Query Routing (0.00–1.00, default 0.50) | `objectSearchVectorThresholdLabel.Text = [Object search vector threshold:]`; `Designer.cs:239-240`; default `AISettingsForm.cs:116` + `LLMProviderSettings.cs:13`. |
| Added the embedding API-key show/hide checkbox | `showEmbeddingApiKeyCheckBox.ToolTip = [Show / hide embedding API key]`; `:239-242`. |
| Status-bar paragraph now names the real status strings | `AISettingsForm.resx` `Status.*` keys. |

### Unverifiable / not verifiable from code alone (flagged, not asserted)

- Whether the deployed manual actually has `images/AI_Provider_Settings.png` — there is no `images`
  folder in the local manual checkout (`public_html\docs\octofy-pro\content\manual`). The image line was
  copied byte-for-byte and no new image reference was added.
- Exact rendered appearance of the text-free API-key check box (no `Text`, tooltip only). Documented by
  its tooltip wording and location, not as an "eye" icon.
- Chinese-locale ordering was read from code, not exercised on a zh-CN machine.
- Red colour of error text is `Color.OrangeRed` (`AISettingsForm.cs:852`); kept the baseline's plain "red".

---

## 2. `application-options-dialog.md` — status: UPDATED

### Changes made (with evidence)

| Change | Evidence |
| --- | --- |
| Removed the duplicated second H1 (`# Options Dialog`); page H1 stays `# Application Options Dialog` | Baseline line 3. Window caption is `Options` (`OctofyLib\Common\OptionsForm.resx`: `$this.Text = [Options]`), so the stray heading was pure duplication. |
| Menu path "the **Options** menu item" → **Tools > Options** | `AdvancedQuery\AdvancedQueryAnalysisForm.Designer.cs:588` (`toolsToolStripMenuItem.DropDownItems` contains `optionsToolStripMenuItem`, text `&Options`), handler at `AdvancedQueryAnalysisForm.cs:1576`. |
| Added one sentence: no tabs; groups are **Calculation exclusions** and **Loading data**; **OK**/**Cancel** | `OptionsForm.Designer.cs` has three `GroupBox`es and no `TabControl`; `okButton.Text = [OK]`, `cancelButton.Text = [Cancel]`. |
| y-axis max corrected 82,595,522 → **82,595,524** | `OptionsForm.cs:141-144`: `const long maxValue = Int32.MaxValue / 26;` = `2147483647 / 26` = `82595524`; message template `B026 = [Please enter a number between 256 and {0}.]`. |
| **Connection timeout default corrected 30 → 120 seconds** | The designer's `timeoutTextBox.Text = [30]` is overwritten on load by `OptionsForm.cs:204` from `Properties.Settings.Default.ConnectionTimeout`; `OctofyPro\App.config` and `Properties\Settings.settings` both default that to `120`. |
| Added the validation rules actually enforced | y: 256–82,595,524 (`:142`); x: 16–128 (`:112`); name length: 16–32,768 (`:85`); non-numeric rejected (`B024 = [Please enter numeric only.]`, `B025 = [Invalid input]`); connection timeout is **numeric-only with no range** (`:212-222`). |
| Added exact quoted messages for out-of-range input | `OctofyLib\Properties\Resources.resx` B026/B027/B046. |
| Defaults confirmed unchanged: 524,288 / 64 / 1,024 / Merge NULL and Blank checked | `OptionsForm.resx` (`maxYTextBox.Text=[524288]`, `maxXTextBox.Text=[64]`, `maxLengthTextBox.Text=[1024]`, `mergeNullBlankCheckBox` `Checked=true`); also `App.config`. |

### Present in code but deliberately NOT documented

- **Quick analysis** group (`groupBox2`, `Text = [Quick analysis]`, "Read top" N "rows for quick analysis",
  100–999,999) is `groupBox2.Visible = [False]` in `OptionsForm.resx` and never re-shown, so it is not
  user-visible. Its value (`NumOfRowOnDoubleClick`, default 10,000) is still read/written by **OK**.
- `OptionsForm.DarkMode` exists as a property but has no control in the dialog; dark mode is toggled from
  **View > Dark Mode** in the main window (`AdvancedQueryAnalysisForm.resx`: `darkModeToolStripMenuItem.Text = [Dark Mode]`).

### Unverifiable

- `images/Octofy_Options.png` existence (as above); image line kept byte-for-byte.
- Users who already changed **Connection timeout** see their own stored value; 120 is the shipped default.

---

## 3. `ai-agent-manager-window.md` — status: UPDATED (substantially rewritten, structure preserved)

### Claims that no longer hold (removed or corrected)

| Removed / corrected | Evidence |
| --- | --- |
| **"the grid columns" / grid** — the window has no grid. It is a single-column `ListBox` (`agentsListBox`) labelled **AI Agents:** showing agent names (`AIAgent.ToString() => Name`, `Octofy.Agent\AI\AIAgent.cs:98`). Nothing was documented as columns. | `AIAgentManager.Designer.cs:64`, `:391-398`; `connectionsLabel.Text = [AI Agents:]`. |
| Fields **Server** and **Database** removed | Not present in `AIAgentManager.Designer.cs`; the code comment states "the Octofy AI Agent window no longer edits the server and database directly" (`AIAgentManager.cs:1348-1352`). They are taken from `CurrentConnection`/the edited agent (`:1353-1373`). |
| **Source ID** (read-only) field removed | Replaced by **Data Source:** (`label3.Text = [Data Source:]`) — an editable combo box that displays data source *names* and stores the source ID (`AIAgentManager.cs:1015-1047`, `:632-654`). |
| Toolbar list corrected | `Designer.cs:360`: `addToolStripButton (New), deleteToolStripButton (Delete), moveUp, moveDown, TestToolStripButton (Test), closeToolStripButton (&OK), cancelToolStripButton (&Cancel), helpToolStripButton (Help)`; tooltips from `AIAgentManager.resx`. Baseline's list omitted **Help** and did not mention the panel/toolbar labels. |
| Opening path corrected: **File ? Manage DB connections** → **File > Manage AI Agents** (plus the existing `Add New Agent` route) | `AdvancedQueryAnalysisForm.cs:3167-3174` (`ManageAIAgentsToolStripMenuItem_Click`); menu text `Manage AI Agents`; `ConnectionManageForm.cs:769-784`; `ConnectionManageForm.resx`: `newAgentsButton.Text = [Add New Agent]`, `chatGPTGroupBox.Text = [Octofy AI Agent]`. |
| Agent-type radio label added (**Agent Type:**) | `connectionTypeLabel.Text = [Agent Type:]`; radios `Octofy AI Agent` / `Build-in Agent`. |
| Built-in agent field name corrected: **"Enable semantic layer"** → **"Allow semantic layer for this data source"** | `semanticLayerCheckBox.Text = [Allow semantic layer for this data source]`. |
| Built-in agent hides the **Name** field and the whole **Octofy AI Agent** group | `AIAgentManager.cs:449-456` `UpdateAgentTypeControls()`: `connectionNameLabel.Visible = !isBuiltInAgent`, `chatGPTGroupBox.Visible = !isBuiltInAgent`, `schemaLibraryButton.Visible = isBuiltInAgent`. |
| **Manage Schema Library** button text becomes **Create Agent** when adding | `AIAgentManager.cs:475-480`; `schemaLibraryButton.CreateAgent.Text = [Create Agent]`. Wizard launch condition `:594-603`. |
| Delete confirmation wording quoted accurately | `Message.DeleteAgentPrompt = [Do you want to delete '{0}'?]`, `Caption.DeleteAgent = [Delete Agent]`. |
| Duplicate-name rule stated as enforced on **Add** | `AIAgentManager.cs:1058-1062`, `Message.AgentAlreadyExists = [An agent named '{0}' already exists.]`. Pre-fill uniquifier appends `(2)`, `(3)` (`:164-179`). |
| Close-with-unsaved-changes prompt wording added | `:394-425`, `Message.ConfirmUnsavedChanges`, `Caption.ConfirmUnsavedChanges = [Unsaved Changes]`. |
| **Cancel** now documented as reloading stored agents | `:371-379` `AIAgents.Instance.Reload()`. |
| Test section: external agent test = root health endpoint, endpoint+key required, exact success message; built-in test = `.schema-index.json` presence + AI-provider probe, exact messages | `:261-276` (`OctofyAgentHelper.GetRootHealthAsync()` → `GET /` , `Octofy.Agent\AI\OctofyAgentHelper.cs:41-46`), `:278-350` (probe body "Reply with only OK.", 32 tokens, 30 s; `Message.BuiltInAgentReady`, `Message.SchemaLibraryNotReady`, `Message.AiProviderNotConfigured`, `Message.AiProviderConnectionFailed`). |
| **Source ID Resolution** rewritten to the real mechanism: list loaded from `GET /api/v1/admin/data-sources`, automatic on field validation and on selection, manual via reload button, 20 s timeout, name/ID stored as a pair on **OK** | `AIAgentManager.cs:826-881` (`LoadDataSourcesAsync`, `DataSourceRequestTimeout = 20 s` at `:21`), `:976-991`, `:1396-1414`, `:933-958`, `OctofyAgentHelper.cs:419-428`. |
| Built-in backend-folder rule kept (still accurate) | `:1278-1292` `{database}_{server}`, lowercased, non-alphanumerics removed; `{DSN}_ODBC` at `:1081-1088`. |
| Added link to [Octofy AI Agent backend API](octofy-ai-agent-backend-api.md) to contrast the external agent with the built-in agent | Page exists in the manual folder; backend contract `octofy-ai-agent-backend-api.md` (`GET /` health, `X-API-Key`, `/api/v1`). |

### Unverifiable / not asserted

- The exact add-a-built-in-agent click sequence: for a **Build-in Agent** the **Name** text box is hidden
  (`:451-452`) while `SaveButton_Click` still requires a non-empty name (`:1051-1056`), so in `AddNew`
  mode the documented path is the **Create Agent** → New Agent Wizard flow. I documented the field
  visibility rules and the wizard route rather than a step order I could not execute.
- Whether the left list ever shows anything other than the agent name (it uses `ToString()`; no columns,
  no icons found).
- `images/AI_Agent_Manager.png` existence (as above); image line kept byte-for-byte.

---

## Cross-page notes for the parent (outside my write scope)

1. **Stale menu path in a sibling page.** `create-build-in-ai-agent.md:12` says
   "Configure the LLM and embedding endpoints in **Tools > AI Settings**" — the dialog is now under the
   **AI Assistant** menu (evidence above). Also `:21` says the **Agent** section has **Manage Agents**;
   the actual controls are the **Agent:** combo box plus **Add New Agent** inside the **Octofy AI Agent**
   group (`ConnectionManageForm.resx`). These affect `create-build-in-ai-agent.md`, which I do not own.
2. **Stale in-product string.** `AIAgentManager.resx`:
   `Message.AiProviderNotConfigured = [- The AI provider has not been configured. Open Tools -> AI Provider Settings to set your endpoint and API key.]`
   — the built-in agent **Test** dialog tells users to open a menu path that no longer exists. Worth a
   product-side fix; I documented the message's meaning, not the stale path.
3. `OctofyPro\OctofyPro\Docs\built-in-agent-guide.md` is also stale (references "Tools ? AI Provider
   Settings", a **Manage Agents** button and a **Schema Library** button on the manager). Not authoritative;
   all wording in my pages comes from the `.resx` files.
