# Learn from Past Projects

**Learn from Past Projects** reads a folder of legacy scripts (SQL and other data-project sources) and turns what they do into knowledge the built-in agent can reuse. It is available from the [Schema Library Form](schema-library-form.md): **File > Learn from Past Project** (the singular wording is the menu's own).

Ingestion works in two tiers:

- **Tier 1 — learn from a folder.** Every run reads the folder and writes reviewable knowledge: business rules, a quarantine ledger, a canonical vocabulary, a run manifest and a resumable run state. By default the same run also feeds the generator's knowledge channels (few-shots, the value index, precomputed Q&A, the semantic model and skills). If you tick **Stage as knowledge wiki (distil later)** it records what it learned as wiki pages instead of feeding the generator.
- **Tier 2 — distill.** **Distill knowledge** reconciles everything that was staged into the generator's channels. Staging exists because one project's data is often produced by another project: a report that only reads an intermediate table cannot know the database column or the calculation behind it. Distilling is what links the two.

## How to use it

1. **Select the scripts folder** — click **Browse...** and pick the folder containing the legacy scripts. The folder picker is titled **Select legacy scripts folder**.
2. Optionally clear **Include sub-folders** (checked by default) to scan only the top level of the folder.
3. Optionally tick **Stage as knowledge wiki (distil later)** — see [Staging a run](#staging-a-run) below.
4. Optionally enter **LLM instructions** (up to 1000 characters, for example `e.g. All currency values are in CAD.`) to guide how the scripts are interpreted. The text is appended to every prompt the run issues.
5. Click **Start**. The status line moves through **Status: Running...**, **Status: Completed**, **Status: Cancelled** or **Status: Error**, and the **Log** tab shows a per-file progress trail. **Cancel** stops the run.

## Requirements

- A schema library folder must be loaded — without one the dialog reports **Schema library folder is unavailable.** and the run stops.
- The LLM provider must be configured in [AI Settings](ai-settings.md); otherwise the dialog reports **LLM provider settings are not configured.** Extraction is done by AI, so no run happens without a provider.

## What gets learned

- **Files** — `.sql`, `.sas`, `.r`, `.py`, `.java`, `.c` and `.cs` scripts are read (`.sqlproj` project files are expanded into the `.sql` files they reference).
- **Units** — extraction runs per unit, not per whole file: SQL is split at `GO` batch boundaries, SAS at `DATA`/`PROC`/`%macro` steps (macro bodies run to `%mend`), and R at top-level function definitions and `##` banners. Other files stay a single whole-file unit. A unit whose extractor returned nothing is dispatched once more, and a file contributes at most a configured number of units (the excess is reported).
- **Business rules** — each rule is stored as a statement, a kind, a target, an expression, the evidence it came from (file, line range, verbatim quote) and its applicability (valid period, data scope, environment, whether it is ad hoc). A rule that carries neither a line range nor a verbatim quote is quarantined rather than saved, so every saved rule can be traced back to a line of the source.
- **Few-shot examples** — question/SQL examples for in-context learning.
- **Value mappings** — real data values found in the scripts, so a term used in conversation can be matched to the value actually stored.
- **Precomputed Q&A** — approved question/SQL pairs for the data groups.
- **Skill files** — a markdown skill document per domain, regenerated once per run.
- **Semantic models** — measures, dimensions, joins and governance predicates extracted from the scripts, merged into the data source's existing model rather than replacing it (see [Semantic Models](semantic-models.md)).
- **Canonical vocabulary** — the run first collects the names the data source already uses (the saved semantic model, previously accepted rules, the data-group index and explicit `metric:`/`dimension:` comment headers) and supplies them to every prompt, so a term in use is reused instead of being reinvented. Names the run introduces are reported for review.

## Reviewing what a run produced

When a run finishes, the summary line reports the counts, for example:

> Done. Q&A: *n* | Few-shot: *n* | Values: *n* | Skills: *n* | Semantic: *n* model(s), *n* items | Rules: *n* kept, *n* quarantined, *n* generic, *n* conflicts, evidence *n*%

The dialog keeps the result reviewable in three places:

- **Log** tab — the per-file progress trail, including the stage and file each line came from.
- **Business rules** tab — every accepted rule with its **Statement**, **Kind**, **Target**, **Recurrence**, **Confidence**, **Status** and **Evidence**. Select a row and use **Approve** or **Reject** to record your review; the decision is written back to the stored rule, so it survives later runs. Double-click a row to open the file the rule was extracted from (or to be told that the source file was not found).
- **Quarantined** tab — everything the run refused, with **Kind**, **Reason**, **Detail** and **Source file**. The tab title carries the count, for example **Quarantined (12)**. Double-click a row to open the source file. Reason codes include a missing evidence locator, generic boilerplate, over the per-domain cap, a conflict with an existing definition, an object the schema does not know, and a substantial file that yielded no rules at all.

**Open run manifest** opens the manifest of the last run — what was produced, what was cut and at which gate, why files were skipped, unit coverage and the artifact counts. If the file has been moved the dialog reports **The run manifest is no longer available.** **Open folder** opens the schema library folder so you can inspect everything the run wrote directly.

## What a run drops, and how it is reported

Nothing is dropped silently. A refused item goes to the quarantine ledger with a reason code and is listed in the **Quarantined** tab, and the manifest counts the same drops. The summary line accounts for the rules that were quarantined and for generic rules, and reports the evidence coverage — the share of saved rules that carry both a line range and a verbatim quote. Skipped files are counted by reason in the manifest, and the units that produced nothing are listed in its "Units not covered or flagged" table.

## Staging a run

Tick **Stage as knowledge wiki (distil later)** before clicking **Start** to record what the folder teaches as wiki pages under the library's knowledge wiki instead of feeding the generator now. Staging is the right choice when the data a project reads was built somewhere else: run it over each historical project, then distill once.

A staging run still writes the business rules, the quarantine ledger, the canonical vocabulary, the run state and the run manifest — those are the review surface for what it learned, and they are what makes a staging run auditable. Only the channels that feed generation are held back, and the run says so in the log:

> Staged *n* wiki page(s); *n* generator channel(s) deferred until you run Distill knowledge.

The wiki library holds one page per dataset and per analysis step, plus a page per staging run recording the folder it read, what it contributed and why files were skipped. A project index lists the pages and flags the ones whose upstream dataset has no page yet, so an incomplete project set is visible rather than implied.

## Distilling staged knowledge

Click **Distill knowledge** to reconcile everything staged in the knowledge wiki into the generator. The pass traces each metric back to the database column it came from, re-points dimensions at the raw table and column, re-ranks rules by how many projects rely on them, escalates conflicts instead of overwriting definitions, and records proven synonyms as glossary aliases. It is deterministic and calls no provider, so it is free to repeat. While it runs the status line shows **Status: Distilling...**, and **Cancel** is available.

On completion the summary reports:

> Distilled *n* page(s) from *n* project(s): *n* rule(s) kept, *n* refused, *n* metric(s) traced back to the database, *n* new alias(es), *n* conflict(s).

Two follow-up messages can appear in the log:

- **Nothing has been staged yet. Tick "Stage as knowledge wiki" and run Start over the historical projects first.** — shown when the distillation found no pages.
- *n* **upstream dataset(s) have no page yet. Stage the projects that build them, then run Distill knowledge again.** — unresolved lineage is a work item, not a failure: stage the producing projects and distill again.

## Re-running a folder

Runs are idempotent and resumable:

- Units already completed by a previous run of the same folder are skipped, so a long project can be finished across several sittings. The saved state is discarded automatically when the model, the instructions, the gates or the unit cap change, and for an individual file when its content changes — so an edited script is always re-read.
- Examples and value mappings are stored under a deterministic content key and checked before any embedding request, so re-running a folder adds no duplicate rows and makes no embedding calls for rows it already has. A deliberate replay of the same folder therefore costs only the units whose files changed.
- A new run merges into the data source's existing semantic model under the same model id. Items whose definitions conflict are escalated — every candidate and the file that stated it are kept for review — and only the affected item is blocked; the run counts the conflict and quarantines it.
- Reviewer decisions (approved or rejected rules) survive re-runs because rules are merged by a deterministic key rather than appended.

## If the extracted model is not used

If the semantic layer is off for the data source, the run still saves the extracted model but adds a notice to the log:

> The semantic layer is off for this data source, so the extracted model is not used for generation. Enable it in the agent settings.

Enable it for the agent in [AI Agent Manager Window](ai-agent-manager-window.md), or see [Semantic Models](semantic-models.md) for the layer's options.

## Related topics

- [Schema Library Form](schema-library-form.md)
- [Data Groups and Precomputed Q&As](data-groups-and-precomputed-qas.md)
- [Semantic Models](semantic-models.md)
- [AI Settings](ai-settings.md)

[Back to Create Build-in AI Agent](create-build-in-ai-agent.md)
