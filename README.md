# Agentic Assistant

A personal research assistant with Notion inputs, human-reviewed work and reusable
knowledge outputs. The editable architecture is in [information-flow.drawio](information-flow.drawio).

## Releases and runtime state

The current release is **v0.2.2**, following the shared-intake diagram. See
[CHANGELOG.md](CHANGELOG.md) for changes, setup instructions and known limitations.
The pre-refactor implementation is preserved at Git tag **v0.1** (commit `ce8669e`).

Current runtime files live under **`runtime.directory/v2/`**. With the default configuration,
this is `data/assistant/v2/`. The v0.1 databases under `data/assistant/` are not migrated,
deleted or replayed. This also means old Workbench rows are not silently adopted by the
new workflow index. The runtime lock remains in the configured parent directory to
prevent two processes from writing the same Notion workspace concurrently.

Setup adds unchecked source-consumption flags. Existing Notero entries are not
automatically imported from v0.1's local handled index: mark Agent Processed for old
sources you do not want to propose again. Even pending papers first create proposals;
they are not silently rewritten in Papers.

DBOS application-version checks remain enabled. Incompatible unfinished workflows
require explicit handling; the assistant does not silently clear them.

## Business flow

Each source has its own Processor. They produce the same SourceMaterial contract:

```text
Inbox / TODO / Notero / SimpRead / Papers / Feed / Interests
                         |
                  Source Processor
                         |
                Information Organizer
                         |
                      Proposer
                         |
                  Router: select action
                         |
                     Workbench
                         |
                  Human approval
                         |
    Planner / Task Worker / Investigator / Direction Proposer
                         |
                Workbench result acceptance
                         |
                Curator → Information Publisher
                         |
          Papers / Knowledge / Ideas / Research Interests
```

Organizer understands input and possible outcomes; Proposer proposes execution or
clarification. Router selects one capability before an execution proposal is published.
Workbench displays the saved capability, scope and expected result for approval.
After approval, the dispatcher uses that saved choice. Router returns only an action
identifier; each selected component prepares its own parameters and output.
Clarification proposals explain the missing user-owned information and ask focused
questions in Workbench with Status = Needs Input.
Neither executes it. Workers consume one complete approved source snapshot containing
original content, supplements and prior work. They do not interpret Revision/Reject
statuses or select the next workflow.

Paper and article intake remain separate commands and separate processors. Their
organization, proposal, review and publication contracts are shared. Intake creates
proposals, not final reading-library entries.

A completed result can contain multiple typed artifacts. Explicit accepted products
are retained as submitted; otherwise Curator assesses whether reusable content exists.
Trivial calculations can finish without producing knowledge.

## Install and configure

```bash
uv sync
cp src/assistant/config.example.yaml src/assistant/config.yaml
```

Fill the local YAML with source/data-source IDs and model configuration. Credentials
are read from this file; it is ignored by Git. Use a Notion integration with access
to the relevant databases.

The provider selections are capability-based. Assistant code uses protocols; plugins
implement them. `local` reasoning uses PydanticAI. Codex router/investigator plugins
remain optional alternatives. Discovery/evidence currently have an offline demo,
not a connected AMiner integration.

Prepare the assistant-owned schema explicitly:

```bash
uv run python -m assistant setup
```

Setup adds required fields/options but does not delete databases, process inputs,
approve proposals or execute jobs. Like other runtime commands, it launches the
configured DBOS runtime; previously started v2 work can recover.

## Commands and daily use

```bash
uv run python -m assistant run propose-tasks
uv run python -m assistant run organize-papers
uv run python -m assistant run organize-articles
uv run python -m assistant run process-signals
uv run python -m assistant run reconcile-feedback
uv run python -m assistant run process-workbench
uv run python -m assistant run recommend-papers
```

| Job | Input | Output |
| --- | --- | --- |
| propose-tasks | Pending Inbox; elevated TODO | Workbench proposals |
| organize-papers | Pending Notero records | Paper-processing proposals |
| organize-articles | Pending SimpRead clips | Organization/action proposals |
| process-signals | Interested Papers/Feed; explicitly pending Interests | Workbench proposals on the original records |
| reconcile-feedback | Revisions, unqualified results, rejections | Reopened source versions; closed old work |
| process-workbench | Approvals and qualified results | Executed results; accepted outputs |
| recommend-papers | Research interests and external candidates | Direct Research Feed recommendations |

Every command and job has detailed `--help`. `--page PAGE_ID` on either organization
job reads one source without forcing duplicate publication.

A normal manual cycle is:

1. Submit sources with their input job.
2. In Workbench, read the proposal and its Proposed workflow, then set Human Review
   to Approved. Request Revision when the selected workflow does not match your intent.
3. Run process-workbench. Inspect the Executed result.
4. Set Result Review to Qualified, then run process-workbench to retain outputs.
5. For changes, provide Human Instruction or Result Feedback and choose Revision
   Requested or Unqualified. Reconciliation reopens the source; run its input job
   again and review the fresh proposal before another execution.

`process-workbench` runs feedback reconciliation first. `reconcile-feedback`
is also available independently and does not invoke a model or worker.

When a proposal has Status = Needs Input, read its questions and answer in
Human Instruction. Set Human Review to Revision Requested to submit the answer;
Approved with a nonempty answer is also accepted. Run reconcile-feedback (or
process-workbench), then run the original source job. The answer and prior proposal
return to the source as a new version; the old Workbench item becomes Superseded.
The new proposal waits for fresh approval. An unanswered clarification stays waiting,
and repeating intake does not generate another proposal for the same source version.

Proposer asks for essential goals, private material or consequential personal choices.
Public facts and technical uncertainty belong to investigation; minor preferences
use stated defaults. Follow-up drafting receives earlier questions and answers in
source history. A new question should explain the new blocker it resolves. Executors
can return focused questions through the same Needs Input and feedback path.
Run setup after schema changes to add Needs Input and the Selected Action property.

## Plan, review and execute

The plan action selects Planner when a concrete design should be reviewed before
the operations it describes. Approving this proposal authorizes planning. Planner
returns steps, inputs, parameters, resources, budget, stopping conditions and acceptance
criteria to Workbench as an Executed result, with Result Review = Pending.

Set Result Review to Qualified and run process-workbench. The confirmed plan is
recorded in the original source history as a new source version; the planning item
becomes Finished. The command then drafts and routes a separate execution proposal.
That proposal displays the confirmed plan and waits for fresh approval. It receives
an execution capability, rather than selecting plan again. Workers receive the
accepted plan with its parameters and limits. Actual execution remains bounded by
the tools and resources available to the selected component.

For plan changes, set Result Review to Unqualified and provide Result Feedback;
the normal feedback path prepares a revised source for another proposal. A rejected
planning proposal is Deprecated without calling Planner.

If new-proposal drafting fails after plan acceptance, the source remains pending.
Run its normal input job to recover the saved intake operation. Existing v0.2.0
proposals without a pre-reviewed route require Revision Requested and resubmission
before execution. Completed results retain their normal acceptance path.

## Source fields and queue ownership

Processors preserve original page bodies and plugin-owned metadata. Shared fields:

| Field | Meaning |
| --- | --- |
| Agent Version | Semantic source version, default 1 |
| Agent Feedback | Human supplements accumulated through reconciliation |
| Agent History | Structured feedback identities, previous work links and results |
| Agent Processed | This source version has been submitted successfully |
| Agent Archived | SimpRead's visible intake acknowledgement |
| Agent In Papers | Notero has successfully produced a Papers output |
| Interested | Papers preference signal, independent of reading progress |
| Agent Pending | Explicit research-interest request for normal intake |

| Source | Selection and acknowledgement |
| --- | --- |
| Inbox | Status != Archived; acknowledge as Archived |
| TODO | Status = elevated; acknowledge as handled |
| SimpRead | Agent Archived unchecked; check after verified proposal submission |
| Notero | Agent Processed unchecked; check after proposal submission |
| Papers | Interested checked and Agent Processed unchecked |
| Research Feed | Human Feedback = Interested and Agent Processed unchecked |
| Research Interests | Agent Pending checked; clear after proposal submission |

Reopening Inbox/TODO/SimpRead's native queue after it was consumed creates a new
source version. This is not discarded merely because a prior version was processed.
For Notero or preference inputs, explicitly advance Agent Version and clear Agent
Processed to request a new manual pass, or use Workbench feedback.

A successful source acknowledgement means intake finished, not that the proposal
was approved or that all downstream work is finished.

## Feedback is new input

Task Reconciler interprets feedback mechanically; it does not replan or dispatch workers.

| Human decision | Source effect | Old Workbench task |
| --- | --- | --- |
| Answer submitted on Needs Input | Append answer and prior proposal; version +1; reopen | Superseded |
| Qualified planning result | Record accepted plan; version +1; submit a new execution proposal | Finished |
| Revision Requested | Append supplements/history; version +1; reopen | Superseded |
| Unqualified | Append feedback and prior result; version +1; reopen | Superseded |
| Rejected | No new input version | Deprecated |
| Qualified | Curate and publish useful accepted outputs | Archived, or Finished when nothing is retained |

The original text remains intact. A stable feedback identity is stored with the
history in the same property update as version/queue changes. Retrying a lost response
does not apply the same feedback twice. New source versions generate new Workbench
proposals; previous reports remain available as history.

Source and live human authorization are checked before result writes and publication.
An old approval does not authorize a changed source.

## Papers and article knowledge

Notero remains the authoritative bibliographic source. SimpRead remains the original
clipping library; its Name, URL, Origin, Tags, Note, Summary, Created and Last edited
time belong to the clipping/user workflow.

After accepted paper organization, Papers retains:

| Attributes | Purpose |
| --- | --- |
| Title, Original Title, Authors | Identify reading material |
| Date, Year, Publication | Publication context |
| Abstract | Original supplied abstract |
| Reading Summary | Generated reading summary, honest about evidence scope |
| Tags | Broad research direction, retaining useful source classifications |
| Keywords | Specific research problems, methods and mechanisms |
| Link, Code | Original reading link; explicitly supplied implementation |
| Related Papers | Evidence-supported relationships, not automatic tag similarity |
| Source Type, Source Page, Zotero URI, DOI | Provenance and duplicate matching |
| Brief Status, Publication Key, Last edited time | Publication bookkeeping |

Reading properties fill empty fields and preserve human values. Paper publication
updates only the assistant-owned body section. Administrative tags such as
`notion` and `ai-processed` are excluded. Unknown dates, venues, abstracts and code
links stay empty. Attachment links and abstracts never imply verified full-text reading.

Detailed citations, attachment paths and reference management remain in Notero.
Papers does not duplicate reading Status or reading progress. Legacy empty bibliography
columns were removed from the live Papers library in the earlier cleanup.

The current system assumes published output databases are not independently deleted
or moved. It does not automatically reconcile missing output pages.

## Daily recommendations

Recommendations are autonomous. They do not need a Workbench approval for each daily
publication. The pipeline discovers candidates, reads primary evidence, assesses them
against active Research Interests, and publishes qualified entries directly to Research
Feed. A report distinguishes actual publication from demo selections, source failures,
rejections and pending recovery.

Interested Feed entries enter process-signals on their original source, without
creating a duplicate Inbox item. Interested Papers are also available as information
signals. Expressed interest is not itself approval to run a research experiment.

Use the existing Codex subscription login for live search and source reading:

```yaml
providers:
  discovery: codex
  evidence: codex
  recommender: local

codex:
  discovery_model: gpt-5.6-luna
  discovery_effort: low
  discovery_timeout_seconds: 300
  discovery_max_candidates: 10
  discovery_recent_days: 7
  evidence_model: gpt-5.6-luna
  evidence_effort: low
  evidence_timeout_seconds: 180
```

The Codex CLI must be installed and logged in with your ChatGPT account. Search uses
live web access in an isolated directory; no extra search API key or MCP server is
needed. Search and reading settings fall back to `investigator_model` and
`investigator_effort` when their own model/effort fields are omitted. Local assessment
uses `local.recommendation_model`. Run `setup` to prepare Research Feed properties,
maintain active Research Interests or mark Papers as Interested, then run:

```bash
uv run python -m assistant run recommend-papers
```

Each day searches at most ten candidates by default, prioritizing the last seven days
while allowing relevant foundational work. No interests or liked papers means no search.
The workflow checks historical Feed identities before reading and assessing each paper.
Per-category maxima are caps rather than quotas; zero recommendations is valid.
The final Feed report separates source excerpts, the reader's generated synopsis,
assessment, reading scope and missing evidence. Codex reading currently preserves
selected excerpts, so it cannot qualify a source for **Mainline Deep Read**, which
requires independently retrieved complete primary text. Other categories remain available.

The daily local report retains search notes, per-candidate evidence, CLI events and token
usage, including rejected sources. The CLI prints business results without the raw event
stream. Same-day runs reuse the durable result; publication retries retain successful
search, reading and assessment checkpoints. Demo mode remains available by setting both
`discovery: demo` and `evidence: demo`: it reads no live interests, invokes no real model
and publishes nothing to Feed. Interested feedback continues through `process-signals`.

## Schedules, inspection and recovery

```yaml
runtime:
  directory: data/assistant
  batch_size: 20
  schedules:
    propose-tasks: "0 0 7 * * *"
    organize-articles: "0 15 7 * * *"
    process-signals: "0 30 7 * * *"
    process-workbench: "0 */15 * * * *"
    recommend-papers: "0 0 8 * * *"
```

```bash
uv run python -m assistant serve
uv run python -m assistant status
uv run python -m assistant resume WORKFLOW_ID
```

Cron has six fields (seconds through weekday), in Asia/Shanghai time. Enabled schedules
persist in DBOS. Serve pauses assistant-owned schedules removed from configuration.
Manual commands do not dispatch recurring schedules, but launch can recover unfinished
work. Run one process per configured runtime; the lock prevents overlapping launches.

Daily recommendation identities include the day. Repeated same-day runs reuse the
saved result; use resume for failed work, not a new model run with another arbitrary ID.

## Logs and testing

The shared logger prints workflow, step and component roles with readable item titles.
Business actions log their start and completion. Severity determines the record count;
`-v` adds diagnostic IDs, query fields and full tracebacks without changing that count.

```bash
uv run python -m assistant run process-workbench -v
```

Logger thresholds are configured in `src/logger/base_config.py`. Runtime traces and
recommendation reports live in the v2 runtime directory. Provider-reported token usage
is logged; cached input tokens are a subset of input tokens.

Agent verification scripts and their running instructions live under `.agents/`.
User acceptance follows the commands and observable Notion transitions above.

## Code map

```text
src/assistant/
  commands/                    run, serve, setup, status, resume
  workflows/tasks/             named business jobs matching run JOB
  workflows/steps/              shared intake and proposal checkpoints
  components/
    processors/                source extraction and feedback storage contracts
    organizer/                 grounded information interpretation
    proposer/                  reviewable task planning
    planner/                   concrete plans and limits for separate review
    reconciler/                deterministic feedback-to-source transformation
    router/                    pre-approval action selection
    task_worker/               stateless execution inputs and typed outputs
    investigator/              evidence-backed investigation
    curator/                   accepted result retention
    publisher/                 typed destination publication
    workbench/                 human review and results
    captures/                  specialized reading briefs
    recommendations/           independent daily recommendation capabilities
  runtime/                     DBOS composition, recovery and local business index
src/plugins/                   implementations grouped by capability then provider
src/logger/                    shared readable logging
```
