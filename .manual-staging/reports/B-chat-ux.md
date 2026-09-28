# Report — Group B (chat UX): `ai-agent-sql-builder.md`, `how-to-use-ai-assistant.md`

Baseline read from `.manual-staging/baseline/`; sources verified against `OctofyPro` working tree (Octofy Pro v8.8.3.0 era, `DataChatControl.cs` 2026-09-25 12:14, `DataChatControl.Modes.cs` 2026-09-25 11:54, `DataChatControl.resx` 2026-09-25 11:32).

Both files written to `.manual-staging/new/`:
- `.manual-staging/new/ai-agent-sql-builder.md` — **updated** (was 99 lines, now 113)
- `.manual-staging/new/how-to-use-ai-assistant.md` — **updated** (was 116 lines, now 221)

No headings were renamed in either file; all pre-existing heading text is preserved verbatim.

---

## 1. `ai-agent-sql-builder.md`

Status: **updated**, all original headings kept.

### Changes with evidence

- **Panel location corrected.** "shown on the right side of the query editor" → the panel is docked on the right side of the **Visual Query Builder** window. `_chatPanel.Dock = Right` and the panel/splitter are added to the form itself, not to `QueryEditPanel`: `AdvancedQueryAnalysisForm.resx` (`_chatPanel.Dock` → `Right`), `AdvancedQueryAnalysisForm.Designer.cs:1058-1059` (`this.Controls.Add(_chatSplitter); this.Controls.Add(_chatPanel);`).
- **How it is opened, and the exact button wording (new).** Button text `Discuss with AI` / tooltip `Discuss the current database with AI`, toggling to `Hide discuss panel`: `AdvancedQueryAnalysisForm.resx:878-886` (`aiChatToolStripButton.Text` = `Discuss with AI`, `ChatPanel.HideButtonText` = `Hide discuss panel`), `AdvancedQueryAnalysisForm.cs:3403-3414` (`expanded ? AiChatHideButtonText : AiChatShowButtonText`). Previously the page did not say how to open the panel at all.
- **Button visibility gated on an assigned agent (new).** `AdvancedQueryAnalysisForm.cs:3250-3251` (`var hasAgent = ConnectionHasAIAgent(connection); aiChatToolStripButton.Visible = hasAgent;`) and `:3265-3266` (panel collapsed when the data source has no agent).
- **Mode picker documented (new).** "Select **Agent** in the mode box in the row above the message box"; the box offers `Discuss`, `Discovery`, `Agent`: `DataChatControl.Modes.cs:546-552` (`Mode.Discuss`, `Mode.Discovery`, `Mode.Agent`; the `Plan` entry is commented out at :551).
- **Newline key corrected: Ctrl+Enter → Shift+Enter.** `DataChatControl.cs:842-849` (`if (e.KeyCode == Keys.Enter && !e.Shift && !e.Control)` sends); `DataChatControl.resx:15-17` `Input.Placeholder` = `Ask about this data… (Enter to send, Shift+Enter for newline)`.
- **Submit button corrected: "?" → Send, plus Stop while streaming.** `DataChatControl.resx:18-23` (`Button.Send` = `Send`, `Button.Stop` = `Stop`); `DataChatControl.cs:1580-1581` (`_sendButton.Visible = !busy; _stopButton.Visible = busy;`).
- **"If no AI settings are ready … a warning is shown" corrected.** The status label no longer exists, so the reason is shown as the *input placeholder* with the input disabled: `DataChatControl.cs:1601-1605` (`SetStatus(...); _inputTextBox.PlaceholderText = UnavailableStatusText;`), `DataChatControl.cs:2740-2744` (`SetStatus` body commented out). The verbatim placeholder texts quoted in the page come from `DataChatControl.resx:45-47` (`Status.NotConfigured`) and `:156-158` (`Agent.Status.NoAgent`).
- **Context-checkbox defaults corrected.** The baseline said every enabled checkbox "is checked by default". Actual: `Query` is enabled-but-unchecked, `Error` is auto-checked, `Objects` is auto-checked: `DataChatControl.Modes.cs:730-743` (`queryCheckBox.Enabled = hasQuery; … else if (autoCheck) queryCheckBox.Checked = true;`), `:745-750` (`errorCheckBox.Checked = hasError;`), `:752-758` (`objectsCheckBox.Enabled = hasObjects; objectsCheckBox.Checked = hasObjects;`). Editing the query clears `Query` again: `DataChatControl.Modes.cs:396-407` (`if (queryChanged && !keepCheckedForErrorContext) queryCheckBox.Checked = false;`).
- **Context checkboxes are shown in Agent *and* Discuss mode (was implied Agent-only).** `DataChatControl.Modes.cs:628-631` (`queryCheckBox.Visible = agentMode || discussMode;` etc.).
- **Object Type list corrected: `(All)` → `All`.** `DBObjectsSelectForm.resx` `ObjectType.All` = `All`; the items are built at `DBObjectsSelectForm.cs:72-79`. No `(All)` string exists anywhere in the project (grep for `\(All\)` → 0 matches).
- **"+" button tooltip added.** `DataChatControl.resx:183-185` (`selectObjectsButton.ToolTip` = `Select database objects`); opens `DBObjectsSelectForm` at `DataChatControl.Modes.cs:778-793`.
- **Objects tooltip + new-session reset (new).** Hovering `Objects` lists the selected object names (`DataChatControl.Modes.cs:760-776`); a new session drops the selection (`DataChatControl.cs:348-359`).
- **Bubble click / double-click claims removed — no longer true.** The only click handler on a message bubble is the copy button: `DataChatControl.cs:3134` and `:3235` (`btn.onclick = function () { OctofyChat.copyMessage(id); };`); grep for `ondblclick`/`dblclick`/`addEventListener` in `DataChatControl.cs` → 0 matches. Replaced with: SQL is applied automatically, generated SQL renders as a `sql` code block with its own copy button, and each reply has a `Copy` button (`DataChatControl.resx:33-35` `Button.Copy` = `Copy`).
- **Automatic insert + immediate re-parse stated precisely.** `DataChatControl.Modes.cs:1025-1031` (`ResponseText = answerText; SqlGenerated?.Invoke(...)`) → `AdvancedQueryAnalysisForm.cs:2425-2433` (`CurrentEditor?.SetGeneratedSql(sql)`) → `QueryEditPanel.cs:357-362` (`SetSQL` + raise `QueryScriptGenerated`).
- **Error/fix flow corrected and expanded.** Error auto-check + Query auto-check + prefill: `DataChatControl.Modes.cs:424-446` (`errorCheckBox.Checked = hasError`; `UpdateQueryCheckboxState(autoCheck: true)`; `_inputTextBox.Text = SR("Prompt.FixThisError", "Fix this error.")`), key value from `DataChatControl.resx:306-308`. Request failures render inside the reply bubble: `DataChatControl.Modes.cs:1088-1093` (`SR("Status.Error", "AI request failed: {0}", ex.Message)` passed as `errorHtml` to `finishAssistant`).
- **Follow-up behaviour refined.** Per-session history + established topic context carried into terse follow-ups: `DataChatControl.Modes.cs:952-954` (session `SemanticContext` fed to the built-in generator), `:57-61` ("established filters, domains and output grain"), `:944-945` (`BuildAgentRequestHistory` merges the visible thread across modes), `:937-943` (mode switches never clear the chat history).
- **Agent-mode greeting quoted (new).** `DataChatControl.resx:231-233` (`Greeting.Agent` = `Ready to generate SQL. Describe what you need and I will build the query.`).
- **"Go to AI Settings via Tools"** wording: the AI Assistant menu carries an `AI Settings` item (`AdvancedQueryAnalysisForm.resx:905-907`) and `Tools > AI Settings` exists (`visual-query-builder-window.md:83`).

### Removed content
- "Or click the **?** submit button" (no such button; the button is `Send`).
- "Click an AI answer bubble containing SQL to apply that SQL" and "Double-click an AI answer bubble to insert the full answer text as a SQL comment block" (both handlers no longer exist).
- `(All)` as the Object Type entry.

### Heading renames
None.

### Unverifiable / caveats
- The visual stacking "mode box + checkboxes in the row above the message box" is derived from the designer dock order (`DataChatControl.Designer.cs:174` `_modePanel.Dock = Bottom`, `:98` `_inputPanel.Dock = Bottom`, added `_modePanel` before `_inputPanel`), not from a runtime screenshot; the docs disagree with each other (`DATACHAT_MODES_AND_COPILOT_MIGRATION.md:28` says "at the top").
- Only the neutral English `.resx` was checked; satellite translations were not reviewed.
- The `SetStatus` strings (e.g. `Status.Stopped`, `Analysis.CommandFailed`) are still in the resx but are invisible in the current layout, so the manual does not promise them.

---

## 2. `how-to-use-ai-assistant.md`

Status: **updated**; all original headings and both `## Screenshots` image lines preserved byte-for-byte (verified by diff of the image lines and the last 5 lines).

### New sections (additions, not renames)
- `## Chat Modes` (+ `### What Discovery shows`)
- `## Chat Sessions` (+ `### Manage Chat Sessions dialog`)
- `## Progress and Tool Calls`

### Changes with evidence

- **Scope broadened: where the assistant appears (new).** Visual Query Builder (`Discuss with AI`, right-docked), Data Preview (its own `Discuss with AI`: `PreviewDataForm.resx:203-207` `askAiToolStripButton.Text` = `Discuss with AI`, tooltip `Discuss the previewed data with AI`; `_chatPanel.Dock` = `Right`), Data Analysis (`AI Assistant` / `Hide AI Chat`: `DataAnalysisForm.resx` `aiChatToolStripButton.Text` = `AI Assistant`, `viewAiChatToolStripMenuItem.Text` = `AI Assistant`, `ChatPanel.HideButtonText` = `Hide AI Chat`; label swap at `DataAnalysisForm.cs:4520-4528`), plus Schema Library / tool function editor panes (`DataChatControl.ToolFunction.cs:9-22`, `DataChatControl.SchemaLibrary.cs:21-49`).
- **"AI Assistant is a panel in the query editor" corrected** to a window-level panel; it survives query-tab switching (`AdvancedQueryAnalysisForm.Designer.cs:1058-1059`) and the `Query` context follows the active tab (`AdvancedQueryAnalysisForm.cs:2533-2538`).
- **Panel contents listed (new).** `⊕ New Session` button (`DataChatControl.cs:89` `$"⊕ {SR("Button.NewSession", "New Session")}"`), mode + context row, message box (`DataChatControl.Designer.cs:69-181`); sessions panel only when sessions are enabled (`DataChatControl.cs:662-667`).
- **Enter/Shift+Enter, Send/Stop, partial answer kept on Stop** — as above plus `DataChatControl.Modes.cs:1081-1087` (cancel finalizes the partial text in the thread).
- **Markdown rendering capability stated (new).** `DATA_CHAT_CONTROL.md:84-87` (headings, bold/italic, inline code, fenced blocks with copy button, lists, blockquotes, links, pipe tables, `http(s)`-only images) and `DataChatControl.cs:3245-3280` (`showProgress`/`finishAssistant` add the copy button).
- **Chat modes documented (new).** Three modes only, with wording taken from the resx: `Discuss` (`DataChatControl.resx:225-227` greeting), `Discovery` (`:228-230`), `Agent` (`:231-233`); mode list at `DataChatControl.Modes.cs:546-552`; Add-to-KB button and progress row are Agent-only (`DataChatControl.Modes.cs:632`, `:1028`); `CanInteract` requirements per mode at `:478-488` (Discuss needs a provider, Discovery/Agent need a usable agent).
- **Mode choice is remembered (new).** `DataChatControl.Modes.cs:605-609` (`Settings.Default.ChatbotMode` saved), `:595-603` (restored on start).
- **`### What Discovery shows` (new).** Candidate grid title `Candidate Objects` (`DataChatControl.resx:204-206`), columns `#`/`Object`/`Match`/`Type`/`Matched Columns` (`:192-209`), grid inserted *before* the assistant bubble (`DataChatControl.Modes.cs:1726-1727` with `renderDiscoveryGrid(..., beforeMessageId)`), match percentage normalized to the top score with `—` when absent (`DataChatControl.Modes.cs:2184-2199`), keyword fallback exists (`:1924`, `:1938`, `:2035`, `:2058`), no-match wording is model-written (`:2126` "state that no matching database objects were found").
- **Context table kept, rules corrected** — same evidence as file 1 (`DataChatControl.Modes.cs:730-758`, `:396-407`), plus the Data Preview window showing no context checkboxes (`DataChatControl.Modes.cs:678-683` `_modePanel.Visible = false` for `DataPreview`).
- **`### Using error messages` corrected** (no status-line promise; prefill behaviour stated) — `DataChatControl.Modes.cs:432-437`.
- **`### Specifying objects…` corrected**: `All` not `(All)`; added the `Select database objects` tooltip, the per-session reset, and the Objects tooltip.
- **`## Apply Replies in the Editor` rewritten.** The "click a bubble / double-click a bubble" instructions are gone (no such handlers, see file 1); replaced by automatic insert + immediate re-parse and the reply/code-block `Copy` buttons.
- **`## Add to knowledge base (thumbs up)` expanded and corrected.** Button appears only in Agent mode with generated SQL (`DataChatControl.Modes.cs:1028`, `:632`); opens `AddToKnowledgeBaseForm` pre-filled with the session's first question and the generated SQL (`DataChatControl.Modes.cs:796-814`, `:875-893`); dialog wording from `AddToKnowledgeBaseForm.resx` (`Add to Knowledge Base`, `Question:`, `SQL:`, `Similar existing entries:`, `Add to KB`, `Cancel`, `Build a semantic model from this query`, duplicate message `An identical entry already exists in the knowledge base.`, tooltip `Using AI to verify`); semantic-model checkbox enabled only for built-in agents with a library folder (`DataChatControl.Modes.cs:828-830`, `AddToKnowledgeBaseForm.resx` `ToolTip.BuildSemanticModelDisabled`); KB usage as exact/near-exact short-circuit plus few-shot context (`Docs/ai-functions-summary.md:45,61,119`).
- **`## Chat Sessions` (new).** Session created/switched (`DataChatControl.cs:318-332`, `:375-383`), no-op while the session is still empty (`:323-324` `if (IsCurrentChatEmpty()) return;`), title = first question truncated to 40 chars + `…` (`DataChatControl.cs:764-776`), **no rename feature** (no rename entry point in `ChatSessionManagerForm.*`, `AdvancedQueryAnalysisForm.*` or `ChatWorkspaceStore.cs`; grep for `Rename` in `OctofyPro/AI` only hits legacy folder/property renames), new session clears Query/Error/Objects and drops the selection (`DataChatControl.cs:348-359`), switching keeps the selection (`:392-410`), menu items `New session` / `Chat Sessions` / `Delete current session` / `Manage Chat Sessions` under the **AI Assistant** menu (`AdvancedQueryAnalysisForm.resx:893-904`, `Designer.cs:631-637`), menu capped at 25 with `(no sessions)` when empty (`AdvancedQueryAnalysisForm.cs:3776-3785`, `ChatWorkspaceStore.cs:68` `MaxSessionsShownInMenu = 25`), persistence per data source in `%APPDATA%\Sherlock Software Inc\Octofy\ChatSessions` and last-used session restored (`ChatWorkspaceStore.cs:11-12`, `:929-931`; `DataChatControl.cs:600-618`), runtime window keeps sessions because `KeepChatHistory = true` and `SessionsEnabled = true` (`AdvancedQueryAnalysisForm.cs:103-107`).
- **`### Manage Chat Sessions dialog` (new).** Title `Manage Chat Sessions` and all labels/columns from `ChatSessionManagerForm.resx` (`Search:`; columns `Topic`, `Created`, `Last used`, `Messages`; buttons `&Delete`/`&Open`/`&Cancel`; `Sessions: {0}`; `No saved chat sessions for this data source`; `No matching chat sessions found`; `Search topics…`; confirm `Are you sure you want to permanently delete the chat session '{0}'? This cannot be undone.`), default order "most recently used first" (`ChatSessionQuery.cs:44-53`), filter matches title/first question (`ChatSessionQuery.cs:58-70`), Delete key handler (`ChatSessionManagerForm.cs:344-353`), double-click opens (`:355-359`), no data-source picker (`:131-147` — always keyed to the bound workspace), session-scoped deletion leaves KB entries alone (`DATA_CHAT_CONTROL.md:149`).
- **`## Progress and Tool Calls` (new).** Progress row inside the pending assistant bubble, flicker guard 250 ms, removed on success/stop/error, never persisted: `DataChatControl.cs:2756-2860`, `:75` (`ProgressFlickerGuardMs = 250`), `Docs/plans/DATACHAT_AGENT_PROGRESS_PLAN.md:485-495`. The listed stage strings are verbatim `Progress.*` values from `DataChatControl.resx:57-137`. Tool-call chip is `'⚙ ' + toolName` inserted above the reply (`DataChatControl.cs:3196-3211`, `:1846`, `:1475-1478`); native function calling limited to OpenAI-compatible chat and Responses endpoints (`DataChatControl.cs:1800-1804`). Analysis-command chips use the host's returned messages (`DataAnalysisForm.cs:265,271,334,343,410,227`).
- **`## Before You Start` corrected.** Discuss needs a provider; Discovery/Agent need a usable agent (`DataChatControl.Modes.cs:478-488`); consent gate with the `A245` text and `Allowing AI to analyze real data` only in Data Preview / Data Analysis / Schema Library (`PreviewDataForm.cs:266-276`, `DataAnalysisForm.cs:4549-4564`, `SchemaLibraryForm.cs:2834-2847`, `AISettingsForm.resx:1183-1188`); the query window does **not** ask (`DATA_CHAT_CONTROL.md:126-131`, no `EnableAiDataAnalysis` reference in `AdvancedQueryAnalysisForm.cs`).
- **`## Related Topics`** extended with `visual-query-builder-window.md`, `data-preview-window.md`, `data-analysis-window.md`, `add-to-knowledge-base.md`, `tool-functions.md` — all files exist in `public_html/docs/octofy-pro/content/manual/`. The pre-existing anchor link `visual-query-builder.md#method-4-generate-sql-with-ai-agent-if-set` was kept unchanged.

### Removed content
- "The **AI Assistant** is a chat-style panel in the query editor" (it is a window-level panel that also serves other windows).
- "Press **Ctrl+Enter** to insert a new line" (the key is **Shift+Enter**).
- "Click an answer bubble that contains SQL to apply that SQL" / "Double-click an answer bubble to insert the full reply text as a SQL comment block".
- "When enabled, it is checked by default" for every checkbox (only Error and Objects are auto-checked).
- `(All)` as the Object Type entry.

### Heading renames
None. (Additions only: `## Chat Modes`, `### What Discovery shows`, `## Chat Sessions`, `### Manage Chat Sessions dialog`, `## Progress and Tool Calls`.)

### Unverifiable / caveats
- **No renames confirmed** but this is a negative: no rename UI exists in the session manager resx/designer, the `AI Assistant` menu, or the store. Nothing in code suggests renaming was ever exposed, but absence of evidence is not proof that an older build lacked it.
- The exact stacking of the mode/context row above the message box is from dock order, not a runtime screenshot (same caveat as file 1).
- The knowledge-base "used in two ways" statement is supported by `Docs/ai-functions-summary.md` only (no runtime verification of the exact-match short-circuit); it was already in the baseline and was retained with narrowed wording (local vector DB for built-in agents, Octofy agent service for Octofy agents).
- Tool-call chips are only documented for Discuss mode (the `TryResolveToolLookupAsync` path is invoked from `SendMessageAsync`); Agent mode invokes tool functions through the generator pipeline, which the manual does not describe in detail.
- Only the neutral English resx was checked for wording.

---

## Coordinator notes — findings outside the two owned files

These were not changed (files not owned), but they are now factually wrong:

1. `data-preview-window.md:43,46,48,94` documents an **Ask AI** button/panel in the preview window. The visible toolbar label is **Discuss with AI** (`PreviewDataForm.resx:203-207`); `askAiToolStripButton` is only the internal control name.
2. `visual-query-builder-window.md` (Toolbar table, lines 98-106) lists Analysis/Preview data/Parse/Data source/Add connection but not **Discuss with AI**; its **Tools** menu table has no **AI Assistant** menu (`AdvancedQueryAnalysisForm.resx:890-904`).
3. `data-analysis-window.md` should gain the **AI Assistant** toolbar button / **View > AI Assistant** menu item, the **Hide AI Chat** label, the **Include chart data** / **Include raw data** checkboxes and the analysis-command behaviour.
4. `add-to-knowledge-base.md:10` says "Click **Add**"; the dialog button is **Add to KB** (`AddToKnowledgeBaseForm.resx` `addButton.Text`).
5. `ai-assisted-descriptions.md` and `schema-library-form.md` describe an **AI Assistant** menu in the Schema Library form; that menu still exists and is separate from the chat pane.

## Proposed new page (not created)

- **Proposed filename:** `chat-sessions.md`
- **Proposed title:** "Chat Sessions and the Session Manager"
- **Proposed `toc.json` placement:** under **How to Use the AI Assistant** (sibling), or as a child of *Windows and Elements* next to `how-to-use-ai-assistant`.
- **Proposed outline:**
  1. **What a chat session is** — one saved conversation; several per data source; the assistant's context is per session.
  2. **Starting and switching sessions** — `⊕ New Session` in the panel; **AI Assistant > New session**; the **Chat Sessions** submenu (up to 25, most recent first, active session checked, `(no sessions)` when empty); session titles come from the first question (no rename command).
  3. **Deleting a session** — **AI Assistant > Delete current session** vs deleting inside the manager; what the chat does afterwards.
  4. **Manage Chat Sessions dialog** — `Search:`, columns `Topic` / `Created` / `Last used` / `Messages`, sorting, `&Delete` (with confirmation), `&Open`, `&Cancel`, status line, scope (one data source, no picker).
  5. **Where sessions live** — per data source under `%APPDATA%\Sherlock Software Inc\Octofy\ChatSessions`; restored on restart; last-used session reopened; knowledge-base entries survive session deletion.
  6. **Related topics** — `how-to-use-ai-assistant.md`, `ai-agent-sql-builder.md`, `add-to-knowledge-base.md`.
