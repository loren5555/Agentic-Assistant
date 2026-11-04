# Changelog

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
