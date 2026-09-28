# E1 — Windows pages update report

Scope: eight manual pages for the Query Data Analysis window group, verified against OctofyPro HEAD `612912fc` (v8.8.3.0, 2026-09-25).

Evidence paths below are relative to `C:\Users\sherl\source\repos\OctofyPro\OctofyPro\` unless stated otherwise. UI strings were read from the neutral `.resx` files (the product resolves them with `resources.ApplyResources(...)` / `ComponentResourceManager`), and behaviour from the `.cs` files.

Baseline used for comparison: `C:\Users\sherl\source\repos\octofy-ai-agent\.manual-staging\baseline\`.

Outputs: `C:\Users\sherl\source\repos\octofy-ai-agent\.manual-staging\new\<file>`.

---

## 1. main-window.md — status: UPDATED (substantially rewritten)

### What was wrong in the baseline
- Menus were incomplete/stale: no **Search**, **Windows** or **AI Assistant** menus; a non-existent **Windows** section was described in prose; **Tools** was documented with **AI Settings** (it has moved).
- No AI chat surface was documented although the window always had one at HEAD.

### Verified changes
- Menu bar order and membership: `AdvancedQueryAnalysisForm.Designer.cs:177` — `fileToolStripMenuItem, editToolStripMenuItem, searchToolStripMenuItem, databaseObjectsToolStripMenuItem, analysisToolStripMenuItem, viewToolStripMenuItem, toolsToolStripMenuItem, parserToolStripMenuItem, windowsToolStripMenuItem, chatbotToolStripMenuItem, helpToolStripMenuItem`.
- File menu items and order: `AdvancedQueryAnalysisForm.Designer.cs:183`; texts/shortcuts from `AdvancedQueryAnalysisForm.resx` (`connectToToolStripMenuItem.Text = "&Connect to ..."`, `newToolStripMenuItem.ShortcutKeys = Ctrl+N`, … `exitToolStripMenuItem.Text = "E&xit"`).
- Edit menu: `Designer.cs:290` + resx (`&Undo`…`Lowercase`).
- Search menu: `Designer.cs:390` → `Quick Find...` (Ctrl+F), `Find...` (Ctrl+Alt+F), `Find and Replace...` (Ctrl+H).
- Object menu: `databaseObjectsToolStripMenuItem.Text = "&Object"` (resx); items `Designer.cs:414` → `Data analysis` F7, `Data preview` F8, `Table Schema` F4, `Add to the visual editor` F9, `Copy object name`.
- Analysis menu: `Designer.cs:455` → `Analysis` F5, `Preview data` F6, `Parse` Ctrl+F5, `Use build-in parser` (checkable).
- View menu: `Designer.cs:493` → object explorer / visual editor / error window / toolbar / status bar, `Zoom In`, `Zoom Out`, `Zoom 100%`, `Collapse All`, `Expand All`, `Dark Mode`.
- Tools menu: `Designer.cs:588` → `Options`, `Edit box font` only. **AI Settings was removed from this menu** and now lives in the AI Assistant menu (`Designer.cs:633`).
- AI Assistant menu: `Designer.cs:633` → `Chat Sessions`, `New session`, `Delete current session`, `Manage Chat Sessions`, `AI Settings`, `Manage Schema Library`; session entries gated by agent availability (`AdvancedQueryAnalysisForm.cs:3250-3260`); session submenu contents built at open time (`AdvancedQueryAnalysisForm.cs:3767-3807`, `MaxSessionsShownInMenu`, disabled `(no sessions)` item).
- Help menu: `Designer.cs:670` → `Octofy home`, `Octofy online help`, `About ...` F1.
- Toolbar: `Designer.cs:710` → `Analysis`, `Preview data`, `Parse`, label `Data source:`, data-source combo, `Add connection`, `Discuss with AI`. Button label swap verified in `AdvancedQueryAnalysisForm.cs:3403-3414` (`aiChatToolStripButton.Text = expanded ? AiChatHideButtonText : AiChatShowButtonText`, `"Hide discuss panel"` / `"Discuss with AI"`).
- Explorer panel: tabs are **Object Explorer** and **Search** (`DataExplorer\DBObjectPanel.resx`: `tabPage1.Text = "Object Explorer"`, `tabPage2.Text = "Search"`), replacing the baseline's informal "object tree tab"/"search tab".
- Object tree context menu: `DataExplorer\DBObjectTree.Designer.cs:78`; texts from `DataExplorer\DBObjectTree.resx` — `Quick analysis on top 10000 rows`, `Data analysis`, `Data preview`, `Table Schema`, `Copy object name`, `Build SELECT script`, `Add to the visual editor`, `Column value frequency`, `Refresh`, `Collapse all`. Availability per node type at `DBObjectTree.cs:552-616`.
- Double-click a table/view node adds it to the visual editor: `DBObjectTree.cs:631-644` (`AddToolStripMenuItem_Click` when `ShowColumns` is true; `DBObjectPanel.Designer.cs:996` sets `ShowColumns = true`).
- Search tab: `DataExplorer\TableSearchPanel.resx` (`Search for:`, `Search for what kind of objects:`, `Table/View`, `Column`, `AI`, `Results:`); Enter/Escape handling `TableSearchPanel.cs:1355-1366`; the **AI** radio is shown only when the agent supports AI search (`TableSearchPanel.cs:126`, `CanUseAISearch` `:782-791`); results context menu `TableSearchPanel.Designer.cs:98`.
- Tab context menu: `Designer.cs:952` → `Tab alias`, `Close`, `Save` (`Tab alias` resx text, prompt `Please enter alias:` = resource `A126`).
- Visual editor disabled message: `Properties/Resources.resx` `A229 = "The query statement cannot be represented in the visual editor."`, used when the statement has set operations (`Docs\UNION_STATEMENT_VISUAL_EDITOR_DISABLE.md:18`).
- Error grid columns: `Designer.cs:1087-1125` (`Line`, `Number`, `Class`, `State`, `Message`, `Source`, `Server`, `Procedure`); error context menu `Designer.cs:1003` with literal texts `"Go to error"` (`:1011`) and `"Copy"` (`:1018`).
- Status bar: `Designer.cs:925`; status message shows connection progress (`A003 "Connect to {0}..."`, `AdvancedQueryAnalysisForm.cs:989`), the selected table/view name (`:1033`), or the current file name (`:2376`); SQL Server shows server + database and non-SQL Server shows the DSN with tooltip `A147 "ODBC DSN"` and hides the database field (`:1491-1504`).
- AI Assistant panel (new section): modes `Discuss / Discovery / Agent` (`AI\DataChatControl.Modes.cs:546-552`); mode panel and context checkboxes `Query` / `Error` / `Objects` with `+` (select objects) and 👍 (add to knowledge base) (`Modes.cs:558-570`, `:626-638`); `⊕ New Session` (`DataChatControl.cs:89`); greetings/placeholders from `AI\DataChatControl.resx`; per-data-source persisted sessions (`AdvancedQueryAnalysisForm.cs:106-107`, `SessionsEnabled`/`KeepChatHistory` true); Agent mode pushes generated SQL into the active editor (`AdvancedQueryAnalysisForm.cs:110`, `:2425-2432`); panel/button only shown when the data source has an available agent (`:3250-3260`).
- Also documented (new): toolbar **Data source:** label, the visual-editor **Collapse All / Expand All / Dark Mode** View items, the Search menu, and the object explorer context menu.

### Heading/anchor changes
None that affect anchors. New `## AI Assistant` section added; `### AI Assistant` subsection added under Menus.

### Unverifiable / deliberately not documented
- A hidden **Parser** menu exists (`AdvancedQueryAnalysisForm.resx`: `parserToolStripMenuItem.Visible = False`, `ShortcutKeys = Ctrl+Shift+D`) — not user-visible, so not documented.
- `Go To Line...` (`goToLineToolStripMenuItem`, Ctrl+G) exists in the resx but is on no menu — not documented.
- The exact set of "available agent" checks (`ConnectionHasAIAgent`) was read but not traced through every connection type.

---

## 2. visual-query-builder-window.md — status: UPDATED

Same window (`AdvancedQueryAnalysisForm`), so all facts in section 1 apply and were re-verified against the same evidence.

### Verified changes
- Menu tables corrected as in section 1 (**Search** added, **Analysis** gained `Use build-in parser`, **View** gained zoom/collapse/dark-mode, **Tools** lost `AI Settings`, **AI Assistant** and its six commands added, `Windows` re-described as the dynamic tab list).
- Toolbar table gained the **Discuss with AI** row with the `Hide discuss panel` label swap (`AdvancedQueryAnalysisForm.cs:3403-3414`) and the `Data source:` label.
- Main panels: explorer tabs renamed to **Object Explorer** / **Search**; object tree context menu listed with exact labels; **Add to the visual editor** / **Add to visual editor** distinction between the two tabs; visual editor disabled message; error window `Go to error`/`Copy`; new **AI Assistant panel** bullet.
- Status bar corrected: server shows the DSN for ODBC data sources and the database field is SQL Server only (`AdvancedQueryAnalysisForm.cs:1491-1504`).
- Added relative link to [Visual Query Builder](visual-query-builder.md) (file exists).

### Heading/anchor changes
None.

### Unverifiable
Same as section 1.

---

## 3. visual-query-builder.md — status: UPDATED

### Verified changes
- **Add Tables or Views**: tab names corrected to **Object Explorer** / **Search**; double-click a table/view adds it to the visual editor (`DataExplorer\DBObjectTree.cs:631-644`); context command is **Add to the visual editor** in the explorer and **Add to visual editor** in the search results (`DBObjectTree.resx`, `TableSearchPanel.resx`); `AllowDrop` is on for the explorer (`AdvancedQueryAnalysisForm.Designer.cs:990`) and the visual editor supports drag-drop table adds (`AdvancedQuery\VisualEditor\VisualEditor.md:43`).
- **Select Columns**: rewritten. The baseline's "double-click a column" and "press Space" are not the product behaviour. The visual editor's table panels use a checked list (`AdvancedQuery\DBTablePanel.Designer.cs:76` `columnCheckedListBox.ItemCheck`), so a column is selected by its checkbox; the column context menu is `Column values frequency`, `Select`, `Unselect`, `Select all columns`, `Unselect all columns`, `Column values to clipboard` (`DBTablePanel.Designer.cs:88-97`, texts in `DBTablePanel.resx`); the table-title context menu is `Preview data`, `Table Schema`, `Alias`, `Remove`, `Select all columns`, `Unselect all columns` (`DBTablePanel.Designer.cs:186-195`). No `Keys.Space` column-selection handler exists in `DBTablePanel.cs` (the only `Keys.Space` use in `AdvancedQuery` is SQL-editor completion, `SQLEditorBox.cs:1970`).
- **Alias an Object**: `Alias` command confirmed (`DBTablePanel.resx` `aliasToolStripMenuItem.Text`); alias validation messages added: `A124 "Invalid alias"`, `A125 "The length of the alias is too long."`, `A230 "The alias already in use"`, `A231 "Duplicated alias"`.
- **Method 2**: the old join-type/icon table (`inner_join`, `left_join`, …) was replaced with the real join menu of the join box: `INNER JOIN`, `LEFT OUTER JOIN`, `RIGHT OUTER JOIN`, `FULL OUTER JOIN`, `Remove` (`AdvancedQuery\JoinBox.resx`; handlers `JoinBox.cs:410-490`). `CROSS JOIN`, `CROSS APPLY` and `OUTER APPLY` have no menu command and come from parsed SQL (`JoinBox.cs:336-364`, `VisualEditor\VisualEditor.md:59-67`).
- **Method 4**: rewritten for the real AI route — **Discuss with AI** toolbar button opens the AI Assistant panel, select the **Agent** mode, generated SQL is pushed into the active query editor (`AdvancedQueryAnalysisForm.cs:110`, `:2425-2432`), then review/refine and validate with **Parse** / **Preview data**.
- **Parse the Statement**: added the `Use build-in parser` toggle and its effect (`AdvancedQueryAnalysisForm.cs:1093-1094`, `:1652-1674`), the two status messages `A122 "Parse executed successfully."` / `A123 "Parse executed with error. Please see the details in the error window."`, and `A243 "Server-side parser is unavailable for the current connection. Enable built-in parser or configure a valid data source."`.
- **Preview Object Data / Check Column Value Frequency**: now give both entry points with their exact labels (`Preview data` / `Data preview` / `Quick analysis on top 10000 rows`; `Column values frequency` / `Column value frequency`) and link to the Column Values Frequency page.

### Heading/anchor changes
None. All required anchors (`ways-to-generate-a-query-statement`, `add-tables-or-views`, `select-columns`, `alias-an-object`, `method-2-build-in-the-visual-editor`, `method-3-manually-edit-the-sql-statement`, `method-4-generate-sql-with-ai-agent-if-set`, `parse-the-statement`, `preview-query-data`, `perform-data-analysis`, `preview-object-data`, `check-column-value-frequency`) verified present by slug comparison against `toc.json`.

### Unverifiable
- "Visual query builder is not available in Octofy Express edition." (kept verbatim from the baseline; no evidence for edition feature gating exists in this repository).
- The exact drag-and-drop code path from the object tree into the visual editor was not traced line by line; verified indirectly (`AllowDrop = true`, `VisualEditor.md:43`).

---

## 4. data-analysis-window.md — status: UPDATED

### What was wrong in the baseline
- File menu items were named `Export chart data` / `Export raw data`; the real labels are **Save Chart Data as...** / **Save Raw Data as...**.
- The **Analysis** menu item names were approximations ("Category percentile and average", "Scatter plot of count", "Scatter plot of sum").
- The **View** item `Show all data` is really **Show all raw data**; **Tools > Percentiles** is really **Percentils** (sic).
- The **AI Assistant** chat surface was missing entirely.

### Verified changes
- Window title: `DataAnalysisForm.resx` `$this.Text = [Data table analysis]`.
- Menu membership: `DataAnalysisForm.Designer.cs:325` → File, Edit, Analysis, View, Tools only (no Help/Windows menu).
- File: `Designer.cs:293`; resx `exportChartDataToolStripMenuItem.Text = [Save Chart Data as...]`, `exportRawDataToCSVToolStripMenuItem.Text = [Save Raw Data as...]`, `closeToolStripMenuItem.Text = [Close]`.
- Edit: `Designer.cs:331`; resx `Copy Chart`, `Copy Chart Data`, `Copy Raw Data Selections`.
- Analysis: `Designer.cs:358`; resx names in the exact UI wording (see section 5).
- View: `Designer.cs:429` → `Data filter`, `Chart data`, `Raw data list`, `Toolbar`, `Status bar`, `Show all raw data`, **`AI Assistant`** (`viewAiChatToolStripMenuItem.Text = [AI Assistant]`, tooltip `Toggle AI chat panel`).
- Tools: `Designer.cs:493` → `Options`, `Percentils`; percentile dialog contents verified in `OctofyLib\Common\PercentilesDialog.resx` (`Calculate the percentiles by:`, `Minimum:`, `Q1:`, `Median:`, `Q3:`, `Maximum:`, `%`, `OK`/`Cancel`/`Reset`).
- Toolbar order and wording: `Designer.cs:511`; texts from `DataAnalysisForm.resx` (`Close`, `Analysis type:`, nine buttons, `Exclude blanks of Y-axis`, the sort drop-down with tooltip `Choose the sort order`, `Large to small` with tooltip `Sort from large to small`, `Search for:`, `0/0`, `↓`/`Next`, `↑`/`Previous`, `AI Assistant`).
- AI chat surface (new `## AI Assistant` section): host mode (`DataAnalysisForm.cs:89` `_chatControl.Mode = DataChatMode.DataAnalysis`); opening flow with provider check and the consent prompt `A245` (`:4536-4578`); button label swap `AI Assistant` ⇄ `Hide AI Chat` (`:4520-4528`, `ChatPanel.HideButtonText = [Hide AI Chat]`, tooltip `Toggle AI chat panel`); the panel is always closed at load (`:1377-1382`); only the **Include chart data** / **Include raw data** toggles are shown in this mode (`DataChatControl.Modes.cs:634-638`, `:672-690`); placeholder `Analysis.InputPlaceholder` and greeting `Greeting.DataAnalysis` (`AI\DataChatControl.resx`); context pushed on every analysis/toggle change (`DataAnalysisForm.cs:4587-4624`); the command surface (`set-chart`, `set-vars`, `group-by`, `filter`, `clear-filter`, `exclude-blanks`, `sort`, `update-analysis-context`) from `AI\DataChatControl.cs:2293-2357` and `Docs\data-analysis-summary.md:201-225`; `Send`/`Stop`, Enter/Shift+Enter, per-reply `Copy`.
- Context menus: `Designer.cs:181` (chart data grid → `Copy chart data`, `Save Chart Data as...`) and `Designer.cs:223` (raw grid → `Copy raw data selections`, `Save Raw Data as...`).
- Status bar: `Designer.cs:692` with eight labels; exact formats from `Properties/Resources.resx` — `A017 "Raw data rows: {0}"`, `A016 "Load data: {0}s"`, `A020 "Data set analysis: {0}s"`, `A022 "Build chart data: {0}s"`, `A025 "Categories: {0}"`, and `"Rn: {0}"` (`DataAnalysisForm.cs:3312`).
- Notes kept and sharpened: NULL/blanks as `(Null)`/`(Blanks)` (`A150`/`A001`), search availability (more than 10 chart-data rows, non-scatter — `Docs\data-analysis-summary.md:127`), sort control visibility (`:126`), percentile box plot (`:300`).

### Heading/anchor changes
None (no anchors on this page).

### Unverifiable
- The exact wording of the AI "tool event chip" result strings (`Analysis command failed: {0}`, `No command.`, `Unsupported command: ...`) is code-literal, not resource text; not quoted in the manual.

---

## 5. data-analysis.md — status: UPDATED

### Heading/anchor changes (all anchor headings kept byte-identical)
Renamed sub-headings under `## Analysis Types` to the exact UI names:

| Old heading | New heading |
| --- | --- |
| `### Category percentile and average` | `### Category percentile values` |
| `### Scatter plot of count` | `### Count scatter` |
| `### Scatter plot of sum` | `### Sum scatter` |

Anchor headings `## Analysis Types`, `## Variable Selector (How to Operate)`, `## Data Filter`, `## Exclude Blanks`, `## Sort the Results`, `## Search Categories`, `## Drill Down to Raw Data`, `## Export and Copy` are unchanged.

### Verified changes
- All nine type names now match the Analysis menu (`DataAnalysisForm.resx`: `Category count`, `Category sum`, `Category percentile values`, `Category distribution count`, `Category distribution count %`, `Category distribution sum`, `Category distribution sum %`, `Count scatter`, `Sum scatter`).
- Variable selector labels: `A047 "Y-axis column:"`, `A082 "X-axis column:"`, `A103 "Sum column:"`, `A104 "Value column:"`, `A107 "Category column:"`, `A108 "Distribution column:"` (`ChartVariableSelector.cs:394-473`).
- Date grouping: the combo is labelled **Group by:** with items **Day / Week / Month / Quarter / Year** (`AnalysisForm\VariableSelector.resx`), where index 0 (`Day`) maps to no grouping (`Docs\data-analysis-summary.md:340`). The baseline's `None` item does not exist.
- Excluded-columns `❢` button (`VariableSelector.resx` `infoButton.Text = [❢]`) and the exact exclusion reasons (`A049`, `A050`, `A051`, `A052`, `A053`, `A113`).
- Selector visibility per type (`Docs\data-analysis-summary.md:318-323`).
- Data filter: `View > Data filter`; tree checkbox behaviour; date-column commands **Add Date Range** / **Change Date Range**, plus **Filter to a specific value**, **Remove**, **Re-load all values**, **Reset filter values** (`OctofyLib\Common\FilterPanel.resx`); the apply button is labelled **Apply data filter** (`FilterPanel.resx`) and turns green/aquamarine when values change (`FilterPanel.cs:203, 306, 527`); `(Blanks)`/`(Null)` are explicit choices (`Docs\data-analysis-summary.md:349`).
- Exclude blanks: toolbar button text is **Exclude blanks of Y-axis** (`DataAnalysisForm.resx`), enabled only when blanks exist (`Docs\data-analysis-summary.md:126`).
- Sort: chart-data column headers, the **Large to small** toggle for single-value results, the sort drop-down for multi-column results (`Docs\data-analysis-summary.md:126`, `:179`).
- Search: more than 10 chart-data rows and non-scatter; Enter/↓/F3 next, ↑ previous, Esc clears, `No match found!` (`A032`) when nothing matches. The baseline's claim of `F3` was kept; **a `Shift+F3` claim was removed** because neither `DataAnalysisForm.cs:2677-2686` nor `ColumnFrequencyForm.cs:350-371` handles Shift.
- Drill-down, Show all raw data, and export/copy wording: export formats verified from the `SaveFileDialog` filter literal `"Excel Workbook (*.xlsx)|*.xlsx|CSV files(*.csv)|*.csv"` (`DataAnalysisForm.cs:3011`).

### Unverifiable
- `Tools > Percentils` keeps the product's spelling (sic); no evidence it is intended to be "Percentiles".

---

## 6. data-preview-window.md — status: UPDATED

### Heading/anchor changes
- `## Ask AI (Chat with the Previewed Data)` → `## Discuss with AI (Chat with the Previewed Data)`, to match the visible toolbar label. No anchor references this heading (`toc.json` has no section entry for this page).

### Verified changes
- Toolbar: `PreviewDataForm.Designer.cs:115` → `Close`, `Preview:` + combo, `Save`, `Chart View`, **`Discuss with AI`**, `csv options`. The visible label is `Discuss with AI` (`PreviewDataForm.resx` `askAiToolStripButton.Text = [Discuss with AI]`, tooltip `Discuss the previewed data with AI`); "Ask AI" exists only in code identifiers.
- Preview size values `Top 1000` / `Top 10000` / `All` (`PreviewDataForm.resx` combo Items; mapping `PreviewDataForm.cs:689-696`).
- **Corrected a baseline error**: the preview selector is no longer SQL Server only. It is shown for table previews and for single-statement queries without an existing row limit, and the row-limit clause is added per DBMS (`PreviewDataForm.cs:967-998`, `HasExistingRowLimit` `:702-719`). Controls are hidden for multi-statement batches and for queries that already limit rows.
- **Corrected the Chart View condition**: the button is shown when there is more than one visible column, the number of visible columns does not exceed the configured max category limit, and at least one visible column is numeric (`PreviewDataForm.cs:468-493`). The baseline's "every visible column except the first is numeric" was wrong.
- Column menu: `PreviewDataForm.Designer.cs:260` → `Value Frequency`, `Hide Current Column`, `Show All Columns`, **`Select Display Columns`** (new); context menu `:302` → `Value Frequency`, `Hide Current Column`, `Select Display Columns`.
- `Value Frequency` visibility rule: `PreviewDataForm.cs:561-563` (grid has more than two rows and `EnableValueFrequency`).
- Window title: `PreviewDataForm.cs:972` (`A042 "Preview Data - {0}"`) and `:981` (`A136 "(Query data)"`); the frequency grid opened from this window is titled `A149 "Frequency of values  for column {0} in the dataset"` (`:1184`).
- Status bar: single label, `A043 "Rows: {0}"` (`:927`) or the grid data-error message (`:459`); `Results:` label above the grid (`PreviewDataForm.resx` `label3.Text`).
- Chat section: renamed to the visible label; context limits from `Docs\DATA_CHAT_CONTROL.md:110-120` (100 rows, 40 000 chars, 120-char values, 30 columns, binary skipped, hidden columns excluded); markdown/streaming/Stop/per-reply Copy/Enter+Shift+Enter from `DATA_CHAT_CONTROL.md:46-88`.
- **Corrected the consent/privacy description**: there is no privacy banner in the current build (`DataChatControl.Designer.cs:162` `_privacyBanner.Visible = false` and no text/visibility assignment anywhere in `DataChatControl.cs`). Clicking the button when consent is off shows the Yes/No consent prompt `A245` and only opens the panel after "Yes", persisting the choice (`PreviewDataForm.cs:250-292`). The setting lives in the **AI Data Analysis** group of the **AI Provider Settings** dialog as **Allowing AI to analyze real data** (`AI\AISettingsForm.resx`).
- Provider-not-configured path: message box `Status.NotConfigured` = `No LLM provider is configured. Open Tools → AI Provider Settings first.` (`PreviewDataForm.cs:253-261`).
- Streaming limitation note kept, with the exact product sentence `Streaming chat is not supported for this endpoint type.` (`AI\DataChatControl.resx` `Error.EndpointUnsupported`).

### Unverifiable
- The WebView2-missing status line: `AI\DataChatControl.cs:808-818` uses `SR("Error.WebView2", "WebView2 failed to initialize: {0}")`, but the key is **absent** from `AI\DataChatControl.resx`, so the English fallback is what a user sees. The manual only says the panel is disabled and the reason is shown.
- `PreviewDataForm.cs:960` shows `Properties.Resources.A147` — whose text is **"ODBC DSN"** — as the SQL-parse-failure message, although the inline comment claims a parse-error sentence. Not documented (product defect, out of scope for a user manual).

---

## 7. column-values-frequency-window.md — status: UPDATED

### Verified changes
- Toolbar wording from `AnalysisForm\ColumnFrequencyForm.resx`: `Close`, `Graph view` (tooltip `View results in the graph chart`), `Data view` (tooltip `View results in the data grid`), `Sort` (tooltip `Sort by counts of category from large to small`), **`Blanks`** (tooltip toggles `Exclude blanks` ⇄ `Include blanks`, resources `A037`/`A038`, `ColumnFrequencyForm.cs:397-410`), `Group by:`, `Search for:`, `0/0`, next (`Next`), previous (`Previous`).
- **Corrected the Group by options**: `Day`, `Week`, `Month`, `Quarter`, `Year` (`ColumnFrequencyForm.resx` `groupByToolStripComboBox.Items..Items4`); the baseline's `Calendar Year` is wrong. `Day` is no grouping (`ColumnFrequencyForm.cs:696-722`).
- Blanks button enabled only when the column has blanks (`ColumnFrequencyForm.cs:1107`); when blanks are excluded the message label shows `A024 "{0} blanks excluded"` (`:826`).
- Grid columns: the category column, `A027 "Count"`, `A028 "Percent"` (`:100-102`); percent is `"N2" + "%"` (`:124`); column 2 sorting disabled (`:733`); blanks/null shown as `A001 "(Blanks)"` / `A150 "(Null)"` (`:23-24`).
- Status bar: message (`A039 "Calculating..."` `:689`, `A040 "Populating the chart..."` `:816`, blank count `:826`), `Table/View name`, `Column name` (`:1022-1023`), `A025 "Categories: {0}"` (`:739`), `"Rn: {0}"` (`:549`).
- Search box visibility: more than 10 categories or truncated category names (`:820-822`); Enter searches / searches next, Escape clears (`:883-941`); F3 moves to the next match (`:350-371`) — **no Shift+F3**.
- More than 50 000 categories: the chart is not drawn and a message is placed in the chart area (`:741-745`).
- Value frequency is computed server-side with a grouped count query (`Docs\data-analysis-summary.md:358`).
- Window title: `ColumnFrequencyForm.resx` `$this.Text = [Column Values Frequency ]` (trailing space in the resource).

### Heading/anchor changes
None.

### Unverifiable
- The exact text shown in the chart area above 50 000 categories is `A029 "Please wait while calculating..."`, which reads oddly for that state. The manual describes the behaviour without quoting the string; flagged here as a likely product wording defect.

---

## 8. windows-and-elements.md — status: UPDATED (minor)

### Verified changes
- Every pre-existing link verified to resolve to a file that exists in `C:\Users\sherl\source\repos\public_html\docs\octofy-pro\content\manual\`: `main-window.md`, `visual-query-builder-window.md`, `data-analysis-window.md`, `data-preview-window.md`, `column-values-frequency-window.md`, `ai-agent-sql-builder.md`, `how-to-use-ai-assistant.md`, `create-build-in-ai-agent.md`, `ai-settings.md`, `application-options-dialog.md`. No link changes were required.
- Added a `## Reference` section linking `octofy-ai-agent-backend-api.md`, which exists in the manual folder and is listed under **Windows and Elements** in `toc.json:17` but was unreachable from this landing page.

### Heading/anchor changes
- New `## Reference` section added (no anchors depend on this page).

### Unverifiable
None.

---

## Cross-cutting validation performed

- All `![...](images/....png)` lines in the eight files are byte-identical to the baseline (compared line by line): 1, 3, 1, 1, 8, 1, 1 and 0 image lines respectively.
- All 20 required anchors verified present by slug comparison against `toc.json` (`analysis-types`, `variable-selector-how-to-operate`, `data-filter`, `exclude-blanks`, `sort-the-results`, `search-categories`, `drill-down-to-raw-data`, `export-and-copy`, `ways-to-generate-a-query-statement`, `add-tables-or-views`, `select-columns`, `alias-an-object`, `method-2-build-in-the-visual-editor`, `method-3-manually-edit-the-sql-statement`, `method-4-generate-sql-with-ai-agent-if-set`, `parse-the-statement`, `preview-query-data`, `perform-data-analysis`, `preview-object-data`, `check-column-value-frequency`).
- Every `](*.md)` link in the eight files resolves to an existing manual page.
- No file other than the eight owned pages was written; `toc.json` and `user-manual.md` were only read.

## Remaining unverifiable items (all files)

1. "Visual query builder is not available in Octofy Express edition." (kept from the baseline; no edition-gating evidence in this repository).
2. The exact WebView2-missing status text (resource key `Error.WebView2` is absent from `AI\DataChatControl.resx`; only the English fallback exists in code).
3. The drag-and-drop handoff from the object explorer into the visual editor was verified only by `AllowDrop = true`, the `OnAddObject` event, and the visual editor's own documentation, not by tracing the drop handler.
4. Product wording defects found but not documented: `Tools > Percentils` (spelling), the 50 000-category chart message (`A029`), and the preview parse-failure message showing `A147 "ODBC DSN"`.
