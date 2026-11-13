# Agentic Assistant

A personal research assistant with Notion inputs, human-reviewed work and reusable
knowledge outputs. The editable architecture is in [information-flow.drawio](information-flow.drawio).

## Releases and runtime state

The current release is **v0.2.4**, following the shared-intake diagram. See
[CHANGELOG.md](CHANGELOG.md) for changes, setup instructions and known limitations.
The pre-refactor implementation is preserved at Git tag **v0.1** (commit `ce8669e`).

Current runtime files live under **`runtime.directory/v2/`**. With the default configuration,
this is `data/assistant/v2/`. The v0.1 databases under `data/assistant/` are not migrated,
deleted or replayed. This also means old Workbench rows are not silently adopted by the
new workflow index. The runtime lock remains in the configured parent directory. One serve process
owns DBOS execution; CLI clients can submit and inspect tasks concurrently.

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
remain optional alternatives. Acquisition uses a weekly Codex Collector and a daily local OpenReview Collector.
The offline demo remains available; AMiner is not connected.

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
| propose-tasks | Pending Inbox; elevated TODO | Workbench proposals |
| organize-papers | Pending Notero records | Paper-processing proposals |
| organize-articles | Pending SimpRead clips | Organization/action proposals |
| process-signals | Papers/Feed with Follow Up checked; explicitly pending Interests | Workbench proposals on the original records |
| reconcile-feedback | Revisions, unqualified results, rejections | Reopened source versions; closed old work |
| process-workbench | Approvals and qualified results | Executed results; accepted outputs |
| recommend-papers | Initial topics, optional likes and Discovery Pool | Broad discovery cache and selected Research Feed edition |

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
| Interested | Optional reading preference; creates no proposal work |
| Follow Up | Explicit request for a Paper or Feed item to enter proposal intake |
| Agent Pending | Explicit research-interest request for normal intake |

| Source | Selection and acknowledgement |
| --- | --- |
| Inbox | Status != Archived; acknowledge as Archived |
| TODO | Status = elevated; acknowledge as handled |
| SimpRead | Agent Archived unchecked; check after verified proposal submission |
| Notero | Agent Processed unchecked; check after proposal submission |
| Papers | Follow Up checked |
| Research Feed | Follow Up checked |
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

Cron has six fields (seconds through weekday), in Asia/Shanghai time. Enabled schedules
persist in DBOS. Serve pauses assistant-owned schedules removed from configuration.
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
      briefer/                 evidence-aware reading material and briefs
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
