# Agentic Assistant

A personal research assistant with Notion inputs, human-reviewed work and reusable
knowledge outputs. The editable architecture is in [information-flow.drawio](information-flow.drawio).

## Releases and runtime state

The current release is **v0.3.0**, following the shared-intake diagram. See
[CHANGELOG.md](CHANGELOG.md) for changes, setup instructions and known limitations.
The pre-refactor implementation is preserved at Git tag **v0.1** (commit `ce8669e`).

Current runtime files live under **`runtime.directory/v2/`**. With the default configuration,
this is `data/assistant/v2/`. The v0.1 databases under `data/assistant/` are not migrated,
deleted or replayed. This also means old Workbench rows are not silently adopted by the
new workflow index. The runtime lock remains in the configured parent directory. One serve process
owns DBOS execution; CLI clients can submit and inspect tasks concurrently.

Setup adds unchecked source-consumption flags. Existing Notero entries are not
automatically imported from v0.1's local handled index: mark Agent Processed for old
sources you have already handled. Intake processes pending versions.

DBOS application-version checks remain enabled. Incompatible unfinished workflows
require explicit handling; the assistant does not silently clear them.

## Business flow

Each source has its own Processor. They produce the same SourceMaterial contract:

```text
Inbox / TODO / Notero / SimpRead / Papers / Feed / Interests
                         |
                  Source Processor
                         |
                Information Organizer ── reusable material → Curator → Writer → Publisher → Papers / Knowledge
                         |
                      Proposer
                         |
                  Router: select action
                         |
                     Workbench
                         |
                  Human approval
                         |
    Planner / Task Worker / Investigator / Writer / Direction Proposer
                         |
                Workbench result acceptance
                         |
                Curator → Writer → Publisher
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
organization and review contracts are shared with Inbox. For each source version,
Organizer decides independently whether material merits an archive and whether it raises
outstanding work. Curator identifies the specific work, its destination, reader and scope.
Writer receives the original source, any existing target page and the approved task or
accepted result when available. Papers follow a common reading structure. Knowledge retains
the explanations, examples and reference material needed to use the page independently.
Publisher integrates each manuscript and preserves separate research discussions.
When both archival and a proposal apply, publication happens first. Proposer
receives the original material plus the verified archive link, summary and evidence level.
The source is acknowledged after all selected steps finish. Materials with no follow-up
can enter the library directly. Rejecting a follow-up leaves its source brief available.

A completed result can contain multiple typed artifacts. Explicit accepted products
are retained as submitted; otherwise Curator assesses whether reusable content exists.

Proposer and Curator can search Workbench and the configured research collections by
title or summary, then read a matching page. When another LaTeX clip arrives, Proposer
can refer to the earlier cheat-sheet proposal and identify what the new clip adds.
Curator can compare an accepted result with the published note before deciding what
to retain. Each source keeps its own approval history.

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
remain optional alternatives. Acquisition uses a weekly Codex Collector and a daily local Collector for OpenReview and optional AMiner Daily Paper (rec5).
The offline demo remains available.

Prepare the assistant-owned schema explicitly:

```bash
uv run python -m assistant setup
```

Setup adds required fields/options but does not delete databases, process inputs,
approve proposals or execute jobs. Stop serve before setup. Setup does not launch
DBOS or recover tasks; it holds the runtime lock only while initializing schema.

## Commands and daily use

Start the executor in one terminal (or under your IDE debugger):

```bash
uv run python -m assistant serve
```

Keep it running. Submit jobs from another terminal using the same `--config`:

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
| propose-tasks | Pending Inbox; elevated TODO | Inbox reading briefs where useful, Workbench proposals for follow-up |
| brainstorm-material | A new Papers, Knowledge or Idea research note | Exploration report and individually reviewable proposals |
| brainstorm-idea | A question in an active Idea | Exploration report with evidence, possible next steps and Workbench links |
| organize-papers | Pending Notero records | Papers reading briefs and optional Workbench follow-up |
| organize-articles | Pending SimpRead clips | Knowledge or Papers briefs and optional Workbench follow-up |
| process-signals | Papers/Feed/Discovery Pool with Follow Up checked; explicitly pending Interests | Workbench proposals on the original records |
| reconcile-feedback | Revisions, unqualified results, rejections | Reopened source versions; closed old work |
| process-workbench | Approvals and qualified results | Executed results; accepted outputs |
| recommend-papers | Notion Recommendation Tags, optional likes and Discovery Pool | Broad discovery cache and selected Research Feed edition |

Every command and job has detailed `--help`. `--page PAGE_ID` on either organization
job reads one source without forcing duplicate publication.

### Workbench review cycle

Each managed row represents one proposal version. Read **Status** first. The
assistant maintains it. Use **Human Review** to decide what may be done and
**Result Review** to assess what was delivered.

| Status and deliverable | Your decision | What happens on the next pass |
| --- | --- | --- |
| Open · execution proposal | Read the proposed action. Add reminders in Human Instruction and select Approved. | The executor delivers a result. Status becomes Executed and Result Review starts at Pending. |
| Open · retention proposal | Review the proposed text and destination, then select Approved. | Curator passes the approved work to Writer for reuse and Publisher for archival. |
| Open · scope or route needs changing | Describe the change in Human Instruction and select Revision Requested. | Feedback returns to the source. The old row becomes Superseded. The next intake proposes a new version. |
| Open or Needs Input · abandon this proposal | Select Rejected in Human Review. | The row becomes Deprecated. This decision creates no new source version. |
| Needs Input · clarification | Answer in Human Instruction and select Revision Requested. | The next intake uses your answer to draft a fresh proposal. |
| Executed · ordinary result | Read Execution result. Select Qualified, or explain the shortcoming in Result Feedback and select Unqualified. | Qualified closes the row as Archived when an artifact is retained, otherwise Finished. Unqualified returns the result and feedback to the source for a fresh proposal. |
| Executed · plan | Read Plan for review and select Qualified when the plan is ready. | The plan row becomes Finished. A new execution proposal presents the confirmed plan for separate approval. |

An Executed row with Human Review = Approved and Result Review = Pending is
waiting for **your verdict on the result**. Further passes leave it waiting.
For a report delivered by another agent, see [Submitting work completed elsewhere](#submitting-work-completed-elsewhere).

The scheduled or manual `process-workbench` pass first reconciles feedback, then
handles approved proposals and qualified results. To advance it manually, run
`uv run python -m assistant run process-workbench`. After a revision, the original
input job picks up the new source version. Standalone `reconcile-feedback` runs
only the feedback stage.

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

### Submitting work completed elsewhere

You can deliver an existing report to an **Open** Workbench proposal for an experiment,
public or literature investigation, material organization, research-direction analysis or
general task. This also works for a report you prepared yourself.

1. On the execution proposal, paste the report and its evidence links under the level-two
   heading **External report** at the end of the page. For an older proposal, add this
   heading yourself. Include the main findings and limitations so the report can be
   reviewed without access to the other computer.
2. Set **Human Review** to **Submit External Result** and run
   `uv run python -m assistant run process-workbench`. Workbench records the supplied
   report as **Executed**, with **Result Review** pending. Submission uses no executor.
3. Review the saved result, set **Result Review** to **Qualified**, and run the same
   command to curate reusable findings. For a correction, use **Unqualified** and
   **Result Feedback** through the usual revision cycle.

For planning, the Planner produces the structured plan required for later execution.
Direct retention and daily recommendation keep their own publication workflows.

### Running an approved experiment

Request an experiment in Inbox or TODO. Review the Planner's protocol, mark the plan result
Qualified, then approve the execution proposal showing `run_experiment`. The signed-in
Codex CLI runs the approved protocol with its shell and file tools. Each approval has a
persistent working directory under `<runtime.directory>/v2/experiments/`; its path and
report are returned to Workbench for review. The Codex options `experiment_model`,
`experiment_effort` and `experiment_timeout_seconds` control this executor.

## Explore research connections with BrainStorm

Run setup with the service stopped to prepare the Sparks output collection. Start
serve again, then choose one of the commands below to select a starting point automatically.
To choose a specific page, append `--page` followed by its actual Notion page ID.
For a paper, copy the link to the individual page in Papers and use the final
32 hexadecimal digits of the page path, before any query string.

```bash
uv run python -m assistant run brainstorm-material
uv run python -m assistant run brainstorm-idea
```

To revisit a specific Idea with the latest library and web evidence, copy its Notion page ID and run
`uv run python -m assistant run brainstorm-idea --page "$IDEA_PAGE_ID" --refresh`.
Each new submission starts a new round. Reusing the printed request ID retries that same round.
Both BrainStorm commands support this option. Scheduled runs continue to skip explored revisions.

BrainStorm gives Codex the selected research note and a bounded selection of
library history, with web search available for public evidence. The report keeps
findings, evidence, candidate items and limitations. Proposer reads it once and
can group related findings, leave observations in the report, or submit separate
decisions. The CLI returns the report even when there are no proposals. A run
from the maintenance panel also appears in execution history.

In Workbench, approve a specific retention proposal to keep a research lead in
Sparks, adopt a project in Ideas, or add a finding to the named Idea. Run
`process-workbench` to apply the decision through Curator, Writer and Publisher. An
investigation or experiment proposal follows its own execution and result review.
A revision reopens that proposal's underlying candidate. Run `propose-tasks` to
draft its next version.

Omit `--page` to let the workflow select an eligible seed. The two jobs can be
scheduled independently in the maintenance panel. Each mode records which seed
revision has completed, including explorations that produced only a report.
Each scan checks recent edits first, then resumes a bounded window of older
pages. Pass a page ID to inspect a specific item outside this window.

For Idea mode, put the question in an `Open Questions` or `Research Question`
text property or Markdown section (also `待解问题` or `研究问题`), or write a
question ending in `?` or `？` in the page. When the project has a status column,
mark it active, for example `Active`, `In progress` or `进行中`. Material mode
also recognizes `Research Log`, `Research Notes`, `Findings` and `Experiment Log`
properties or sections (including `研究日志`, `研究记录`, `研究发现` and `实验记录`).
Publisher's most recent appended research finding can serve as the next seed.

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
| Interested | Optional reading preference; creates no proposal work |
| Follow Up | Explicit request for a Paper or Feed item to enter proposal intake |
| Agent Pending | Explicit research-interest request for normal intake |

| Source | Selection and acknowledgement |
| --- | --- |
| Inbox | Status != Archived; acknowledge as Archived |
| TODO | Status = elevated; acknowledge as handled |
| SimpRead | Agent Archived unchecked; check after intake completes |
| Notero | Agent Processed unchecked; check after intake completes |
| Papers | Follow Up checked |
| Research Feed | Follow Up checked |
| Discovery Pool | Follow Up checked, independently of preference Feedback |
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

Papers retains these fields for source briefs and accepted reading results:

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

## Research newspaper: coverage-driven collection and selected recommendations

Collector plans acquisition from interests, current Pool stock and a rolling 90-day
breadth-by-publication-age table. Weekly Codex exploration uses public web search and
read-only OpenReview tools, saving concrete directions for six daily local API scans.
Recommender reads shortlisted primary evidence and public reviews, then publishes only
qualified selections directly to Research Feed. Optional likes personalize the newspaper;
only explicit Follow Up requests enter the proposal/Workbench path.

```bash
# Start serve first, then submit from another terminal.
uv run python -m assistant run recommend-papers-deep --detach
uv run python -m assistant run recommend-papers-light --detach
uv run python -m assistant status WORKFLOW_ID --result
```

Sunday 07:00 deep and Monday-Saturday 07:00 light schedules collect before selecting
one shared daily edition. Successful collection is reused within its ISO week/day.
Quality remains a gate; the default five-item edition is a maximum, not a quota.
Discovery Pool remains a Chinese quick-skim cache; selected Feed reports stay English.
Public reviews preserve reviewer/author roles, raw scales, reply links and limitations.

See [collection policy, OpenReview account setup and costs](docs/research-collection.md),
the [newspaper sequence diagram](docs/newspaper-sequence.md), and editable
[information-flow.drawio](information-flow.drawio). Collector cadence does not cap the
separate configured model costs of ranking, assessment or non-OpenReview evidence reading.

## Schedules, inspection and recovery

Start `uv run python -m assistant serve`, then open **http://127.0.0.1:8765/**
for the maintenance console: schedule daily jobs online, submit a single run,
browse saved results/steps, resume/cancel work, and preview execution-record cleanup.
Agent-call history links recorded provider traces to their originating business steps. See the
[console guide](docs/maintenance-console.md). See [local service](docs/local-service.md)
for remote access and maintenance scope.

```yaml
runtime:
  directory: data/assistant
  batch_size: 20
  schedules:
    propose-tasks: "0 0 7 * * *"
    organize-articles: "0 15 7 * * *"
    process-signals: "0 30 7 * * *"
    process-workbench: "0 */15 * * * *"
    recommend-papers-deep: "0 0 7 * * 0"
    recommend-papers-light: "0 0 7 * * 1-6"
```

```bash
uv run python -m assistant serve
uv run python -m assistant status
uv run python -m assistant resume WORKFLOW_ID
```

Cron has six fields (seconds through weekday), using Asia/Shanghai by default.
Online plans can specify another time zone and persist their enabled state. Serve
removes Assistant-owned schedules removed from configuration; accepted runs remain.
Only serve launches DBOS and recovers compatible unfinished work. Manual jobs and
scheduled dispatch use the same serial business queue; schedule callbacks have a
separate trigger queue. run/status/resume are HTTP clients and work while serve is
running. Setup remains exclusive and requires stopping serve first.

See [Local service operation](docs/local-service.md) and the
[service sequence diagrams](docs/service-sequences.md). The business information-flow
Drawio remains a separate view of source/component/output responsibilities.

Collection identities use the ISO week or day. Daily edition identities include the
day and editorial policy/topic selection, and are shared across deep/light triggers.
Use resume for failed work after correcting its cause.

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

The directory tree follows role ownership. Coordination returns interpretations and
judgments, execution completes delegated work, recommendations prepares the independent
newspaper, and data interfaces own source access and verified writes. Existing workflows
still own ordering, approvals and DBOS checkpoints.

```text
src/assistant/
  commands/                    serve/setup owners; run/status/resume HTTP clients
  workflows/tasks/             named business jobs matching run JOB
  workflows/steps/             shared intake and proposal checkpoints
  components/
    coordination/
      organizer/               interpret source material
      proposer/                draft reviewable proposals
      router/                  select pre-approval actions
      reconciler/              transform feedback into source revisions
      curator/                 select reusable accepted outcomes
    execution/
      planner/                 concrete plans and limits for review
      investigator/            public-source investigation
      task_worker/             approved execution and typed task results
      writer/                  reader-facing manuscripts and destination standards
    recommendations/
      collector/               acquisition briefs, saved directions and breadth-by-age policy
      discovery/               source candidates, quality provenance and identity
      evidence_reader/         accessible primary material and reading scope
      recommender/             rankings, assessments and edition reports
    data/
      sources/                 source snapshots, extraction and feedback queues
      workbench/               proposals, human decisions and results
      discovery_pool/          broad cached discoveries and optional feedback
      research_feed/           selected editions and reading preferences
      publisher/               verified destination writes and publication receipts
  runtime/
    services.py                lazy role-to-provider wiring
    serialization.py           read historical model paths at the DBOS boundary
    service/
      server.py                loopback API and state/result/step queries
      client.py                CLI submission and result polling
      submissions.py           shared durable dispatch and recovery requests
      models.py                request contract and runtime identity
      presentation.py          saved business report formatting
    application.py             compose durable workflow instances
    recovery.py                existing recovery/version rules
    index.py                   local business mappings and editorial counts
src/plugins/
  coordination/                matching role, then provider (local, codex, ...)
  execution/                   matching capability, then provider
    direction_proposer/        TaskWorker specialization using its shared contract
    tools/                     registered atomic tool implementations
  recommendations/             collector, public source tools, evidence_reader and recommender providers
    _shared/                   editorial policy shared within the newspaper
  data/                        sources, workbench, pool, Feed and publication providers
    publisher/notion/          accepted artifact and reading-brief writers
  _shared/                     provider SDK/configuration and transport helpers
src/logger/                    shared readable logging
```

A component's `models.py` owns its exchanged data and `protocol.py` defines its callable
contract. Other roles import that contract rather than defining a second version. Package
docstrings identify the input origin, output destination and responsibility.

Plugin paths mirror these role groups. For example, `coordination.router` with provider
`local` resolves to `plugins.coordination.router.local`. Existing YAML provider selections,
model options, action IDs and command names retain their meanings. The `calculator.local`
toolset selection now resolves below `plugins.execution.tools`.

Historical DBOS snapshots retain their original bytes. The serialization boundary maps
old component model paths to current owners and writes new snapshots using current paths,
with the same `py_pickle` format. Existing unfinished-work version checks still apply;
the reorganization neither migrates database rows nor clears workflow state.

### AMiner Daily Paper and Deep Research

Set `aminer.api_key` in your local `config.yaml` and restart `assistant serve`. The local light Collector requests up to ten rec5 papers
for its highest-priority search direction during `run recommend-papers-light`.
The existing candidate limit, Pool classification, Codex evidence reading and Feed
selection still apply. A rec5 failure appears in the source failures for the run.

With this credential the proposal router can also select **学术文献调研 · AMiner 沉思**.
Review the proposed route in Workbench, approve it and run `process-workbench`
to receive the hosted research report. The general public-source investigation
action continues to use its configured provider.

## Local agent memory

Write ordinary feedback in Workbench. Submit proposal comments in **Human Instruction**
with the approval, revision or rejection decision. Submit result comments in **Result
Feedback** with the acceptance decision. The next Workbench processing or relevant
feedback reconciliation queues a separate memory review. A decision without written
feedback needs no model call. Existing finished work is not replayed.

The reviewer uses the manually maintained project instructions
[`revise-role-memory`](src/assistant/instructions/revise-role-memory.md), the
current task and comment, up to twelve earlier observations from other pages and
both complete notebooks. It can leave both unchanged, revise one or both, or
withdraw a preference. The background review uses the local proposer model by
default. Its execution record explains the decision and links to the Workbench
page. A failed model review can be retried independently of the original task.

Personal experience lives in `<runtime.directory>/v2/memory/organizer.md` and
`proposer.md`. Each decision reads its role's complete note plus the shared,
manually maintained [project instructions](src/assistant/instructions/project-agent.md).
DBOS checkpoints those instructions before the call, including for BrainStorm
proposal assessment. A new decision picks up revisions automatically. Each newly
written note is limited to 4,000 characters during revision; recall preserves its
entire text. Empty notebooks are valid. You can inspect the notes without editing
them. Existing active per-entry memories are consolidated into a role notebook on first use.

### Writing guidance for reader-facing outputs

Edit the [project writing instructions](src/assistant/instructions/researcher-style-writing.md)
to change how agents explain findings in Chinese and English. Writer, Investigator,
BrainStorm, Curator and Research Feed assessment receive the full guide. Pool
translations, proposal drafts, execution plans and worker deliverables receive
its opening section plus an instruction about the reader's task. Each component
continues to own the output language, evidence requirements and structured fields.
Restart the service after editing the guide so all agent instances load the revision.
