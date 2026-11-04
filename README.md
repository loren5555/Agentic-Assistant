# Agentic Assistant

A personal research assistant with Notion inputs, human-reviewed work and reusable
knowledge outputs. The editable architecture is in [information-flow.drawio](information-flow.drawio).

## Releases and runtime state

The current release is **v0.2.3**, following the shared-intake diagram. See
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

## Research newspaper: discoveries and selected recommendations

Recommendations operate independently of Workbench. **Discovery Pool** is the broad,
browsable cache of recent papers, findings, methods, tools and datasets. **Research
Feed** is the smaller selected edition, normally five items and configurable up to ten.
Search results are merged into the pool before ranking; selected candidates receive
source reading and evidence assessment before Feed publication. A search may return
fewer items than requested; the cache accumulates discoveries across runs.

Choose initial newspaper topics during setup. These preferences require no proposal
approval and are independent of formal Research Interests:

```bash
uv run python -m assistant setup \
  --recommendation-topic "Reinforcement learning" \
  --recommendation-topic "Multi-agent systems" \
  --recommendation-topic "Decision making"
uv run python -m assistant run recommend-papers
```

Setup stores chosen topics in `data/assistant/v2/recommendation-topics.json`. Repeating
the topic options replaces that selection; omitting them preserves it. Alternatively,
configure initial topics in YAML; the setup selection takes precedence when present:

```yaml
runtime:
  recommendations:
    topics: [Reinforcement learning, Decision making, Multi-agent systems]
    pool_size: 100
    selected_count: 5
    reading_budget: 15
    exploration:
      Core: 0.4
      Broader: 0.3
      Neighboring: 0.2
      Cross-disciplinary: 0.1
providers:
  discovery_pool: notion
  discovery: codex
  evidence: codex
  recommender: local
codex:
  discovery_max_candidates: 60
  discovery_recent_days: 7
  discovery_timeout_seconds: 600
notion:
  assistant_page_id: <<assistant-page-id>>
  discovery_pool_data_source_id: <<pool-data-source-id>>
```

Setup can create a missing Discovery Pool under the configured Assistant page. The
existing Codex CLI subscription login supplies live web search; no additional search
API or MCP service is needed. Search/reading models and effort are independently
configurable under `codex`; local assessment uses `local.recommendation_model`.

**Discovery Pool:** `Kind`, `Breadth`, `Summary`, `Topics`, source URL and dates describe
lightweight finds. `State = Selected` records Feed publication. `Feedback = Interested`
strengthens future discovery around the item's topics; `Not Interested` excludes that
item from selection. Unmarked entries are neutral. Preference signals are read afresh
without creating Workbench tasks or modifying formal research directions. Interested
Papers and liked Feed entries also contribute context. Initial topics preserve broad
coverage while specific positive feedback gains higher preference weight and refines
discovery automatically. There is no approval or mandatory feedback step.

The visible cache targets 100 recent items. Refresh preserves feedback and selection,
merges canonical source identities and archives excess old unmarked cache records.
Explicitly marked records are retained, so the total can exceed the cache target.
Selected reports remain available in Research Feed even after an old pool row retires.

**Selected edition:** metadata ranking precedes expensive reading. Confirmed publication
history balances core, broader-field, neighboring and cross-disciplinary coverage over
time, rather than forcing integer quotas into every small issue. Random tie-breaking
is stable for an edition. Exploratory recommendations explain a concrete possible
connection and distinguish it from established source claims. Reading scope, original
short excerpts, generated synopsis and inference are labeled separately. Partial
reading cannot qualify as Mainline Deep Read. Unsupported candidates are omitted;
fewer than five recommendations, including zero, is valid.

**Reading preference versus task request:** marking Interested personalizes the feed.
To request further work, check **Follow Up** on a Paper or Research Feed entry and run
`process-signals`. The checkbox clears after proposal publication; checking it again starts a new source
version. That explicit request enters the ordinary proposal/approval flow;
ideas can also be saved directly through the normal user inputs. Daily reading itself
requires no response or review.

If live discovery fails, the existing pool can still supply the edition; an empty
pool plus a failed search remains an error that can be retried. Search, pool refresh,
ranking, reading, assessment and publication have separate DBOS
checkpoints. Same-day retries reuse the edition; changing configured/setup topics uses
a different edition identity. Existing pre-pool empty reports are not reused. Detailed
search/reading events and usage remain in local recommendation reports. Explicit demo
mode (`discovery: demo`, `evidence: demo`) uses no live preferences, cache or publication.

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

Daily recommendation identities include the day and newspaper policy/topic selection. Repeated same-day runs reuse the
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
    recommendations/           autonomous newspaper discovery and selection
    discovery_pool/            broad cached discoveries and optional feedback
  runtime/                     DBOS composition, recovery and local business index
src/plugins/                   implementations grouped by capability then provider
src/logger/                    shared readable logging
```
