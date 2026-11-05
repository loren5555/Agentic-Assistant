# Changelog

## Unreleased

- Reorganized component contracts and plugin implementations into coordination,
  execution, recommendations and data. Existing commands, configuration keys,
  workflow/action identities and business behavior are retained.
- Split discovery, primary reading, editorial decisions and Feed storage into their
  owning roles. Source snapshots and processor operations now share data.sources.
- Replaced the captures module boundary with execution.briefer; publication helpers
  and receipts now belong to data.publisher. DirectionProposer continues to use the
  TaskWorker contract as an execution specialization.
- Historical DBOS model paths are resolved only at the pickle decoding boundary.
  No runtime rows, Notion schema/records or workflow version checks are changed.
- Updated the code map and role documentation. The business diagram is unchanged
  by this code-only reorganization.

## 0.2.4 — 2026-11-05

- Discovery Pool presents Chinese quick-skim titles, summaries, topics and possible
  connections while preserving original titles, canonical identity and source links.
  Research Feed reading reports remain in English.
- Added publication/author provenance, concrete novelty and methodological concerns
  to discovery and reading results. Pool Venue and Quality Notes expose what is known
  and what still needs verification; selected reports explain credibility and novelty.
- Shared editorial policy favors verified top venues and relevant author track records,
  retains novel preprints and foundational cross-disciplinary work, and de-emphasizes
  incremental score-heavy claims with unclear evaluation support.
- Ranking metadata, years, publication stages and uncertainty are explicitly separated;
  author or venue prestige does not certify an individual paper's claims.
- Existing pool presentations can be localized without changing feedback, selection,
  original source identity or discovery dates. Updated the Dashboard pool view and diagram.

### Updating

- Setup adds Venue and Quality Notes to the pool. Existing records remain readable.
  Already verified Feed records are not rewritten or reclassified automatically.
- Incompatible unfinished DBOS work retains the existing explicit version checks;
  this release does not clear workflow state.

## 0.2.3 — 2026-11-05

- Added the Assistant-owned Discovery Pool: broad recent public research, including
  papers, findings, methods, tools and datasets, with canonical upserts, visible
  metadata, optional feedback and bounded cache retention.
- Daily recommendations now rank the accumulated pool before selective source
  reading and publication of a smaller Research Feed edition (five by default).
- Added setup topics and automatic preference context from explicit likes. Initial
  preferences are independent of formal Research Interests and Workbench approval.
- Actual publication history balances core/broader/neighboring/cross-disciplinary
  exploration toward 40/30/20/10 over time. Silence remains neutral.
- Interested marks no longer generate proposals. Papers and Research Feed expose
  Follow Up for explicit task requests through process-signals. Publication consumes
  the checkbox; a new check reopens the source with a new version. Preference and
  queue changes remain outside the semantic task identity.
- Updated Drawio, setup/help/configuration, README, report fields and edition IDs.

### Updating

- Configure the pool data source or Assistant parent page and run setup. Initial
  topics can be configured or supplied with repeated --recommendation-topic options.
- Legacy pre-pool recommendation reports are retained and use a different identity.
  No unrelated workflow records are cleared or migrated.

## 0.2.2 — 2026-11-05

- Added subscription-backed Codex live discovery and primary-source reading for
  daily recommendations. Search uses active Research Interests and Interested
  Papers, a configurable recent window and a bounded candidate list. Relevant
  foundational papers remain eligible; no preferences means no search.
- Search and reading are asynchronous DBOS checkpoints. Reports preserve search
  notes, source excerpts, reader-generated synopses, access limitations, CLI events
  and token usage, including rejected sources and failed invocations.
- Local PydanticAI assessment evaluates the supplied evidence. Qualified, unseen
  recommendations publish directly to Research Feed within category caps. DOI,
  arXiv and canonical URL identities prevent repeat publication; Frontier Radar
  requires a date inside the requested search window.
- Selected excerpts remain partial evidence and cannot qualify as Mainline Deep
  Read. Feed reports separate original excerpts, reader synopses and assessment;
  publication readback checks its identity marker rather than exact Markdown.
- Added a shared isolated Codex web invocation with strict structured schemas,
  result-file validation, timeout/cancellation cleanup and failure telemetry.
- Updated the editable information-flow diagram, configuration, command help and
  usage documentation. The diagram shows Recommender publishing directly to Feed;
  the existing storage component remains an implementation responsibility.

### Updating

- Set providers.discovery and providers.evidence to codex, and recommender to local.
  The example configuration includes independent search/reading models, effort,
  deadlines, discovery_max_candidates and discovery_recent_days. Demo providers
  remain available for offline operation.
- Run setup if Research Feed lacks its Stable ID property. No new Notion database
  properties are required. Existing production records are not rewritten.
- Runtime databases remain under v2. Existing incompatible unfinished workflows
  require explicit handling; no automatic state deletion or migration is performed.

## 0.2.1 — 2026-11-05

- Router selects an action before proposal publication and returns only the
  selected identifier. Workbench displays the capability name and scope and
  records Selected Action. Approval executes the stored choice without rerouting.
- Added the plan action and a tool-free local Planner with independently
  configurable model, effort and timeout. Plans contain concrete operations,
  inputs, parameters, resources, budget bounds, stopping conditions and acceptance
  criteria for human review.
- Qualified plans return to the original source as typed accepted-plan history.
  The planning task finishes and a fresh execution proposal is prepared. Execution
  waits for its own approval and receives the confirmed plan and limits.
- Executors can report focused questions through Needs Input. Human answers
  continue through the shared feedback-to-source path; ask_user is removed from
  the routing catalogue.
- Selected capability and human authorization are checked before execution.
  Reading-brief execution receives human instructions and any confirmed plan.
- Updated the editable diagram, usage documentation, command help and example
  configuration. Existing subscription-backed model providers remain available.

### Updating

- Run setup to add the Selected Action rich-text property to Workbench.
- Existing proposals without a saved pre-approval capability require revision and
  resubmission before execution. Existing completed results remain reviewable.
- Runtime databases remain under v2. Incompatible unfinished workflows still
  require explicit handling; the release does not delete or migrate their state.

## 0.2.0 — 2026-11-04

This release connects source intake, human-reviewed proposals, execution and
accepted knowledge publication through a shared workflow for personal research.

### Changes

- Independent processors read Inbox, elevated TODO, Notero, SimpRead, interested
  Papers and Research Feed entries, and pending Research Interests.
- Shared Information Organizer and Proposer prepare grounded execution proposals
  or focused clarification proposals. Clarifications appear as Needs Input in
  Workbench, with instructions for submitting an answer.
- Reconciler returns answers, revisions and unqualified-result feedback to the
  original source. A new source version enters normal intake and requires fresh
  approval; previous work is retained as Superseded or Deprecated.
- Approved work routes to Task Worker, Investigator, reading-brief generation or
  research-direction proposal. Qualified results produce typed Papers, Knowledge,
  Ideas or Research Interests outputs; trivial results can finish without an archive.
- Runtime clarification uses the same human-input path as Proposer clarification.
  Earlier questions, answers, proposals and results accompany subsequent planning.
- Notion link previews that the API cannot render are represented by their URL or
  an explicit unavailable-preview notice, allowing surrounding text to be processed.
- Updated command help, usage documentation and the editable information-flow
  diagram describe the shared source and feedback paths.
- Source and wheel packages exclude the local configuration file and ship the
  sanitized configuration template.

### Setup and runtime state

- Version 0.2 uses `runtime.directory/v2/` for DBOS state and the business index.
  Version 0.1 state remains at its original location and is not automatically migrated.
- Run `uv run python -m assistant setup` to add required source fields and Workbench
  states, including Needs Input. Setup extends existing databases.
- Source acknowledgement records successful proposal submission. Accepted paper
  publication separately records Agent In Papers on Notero.

### Known limitations

- Discovery and evidence providers currently use demo fixtures by default. Demo
  recommendations remain local reports and are not published to Research Feed.
- DBOS startup can recover unfinished workflows alongside a manually selected job.
  The `--page` option scopes the newly submitted job; historical recovery may run
  concurrently. Command-specific recovery controls are deferred.
- Published output pages are assumed to remain in their destination databases;
  independent deletion or relocation is not automatically reconciled.
- Incompatible unfinished DBOS versions require explicit handling.
- Proposal drafting and execution are model-driven. Internal fixture checks cover
  lifecycle behavior; real-model proposal and clarification quality continues to
  be assessed during use.

## 0.1

Initial personal research assistant baseline, preserved at tag `v0.1`.
