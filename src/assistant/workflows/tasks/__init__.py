"""Locate complete workflows by the business action requested by the user.

Input origin:
    Manual run JOB or configured schedule -> commands/run.dispatch -> one named
    task below. Services read the corresponding Notion collections, external
    evidence, and prior state from the local runtime.

Output destination:
    propose-tasks -> Workbench; process-workbench -> Workbench plus Knowledge/Ideas
    or Interested follow-ups to Inbox; organize-papers/organize-articles ->
    Papers/Knowledge or Workbench;
    recommend-papers -> Research Feed and a local report. Return values go back
    through the dispatcher to the command/scheduler, with progress kept in DBOS.

Responsibility:
    Provide the processes selected by run.dispatch and reused by scheduled jobs.
    Each task advances work to its next human boundary or completes one bounded
    processing pass; it is not a permanently running agent.

Task map:
    propose-tasks -> propose_tasks.py: read Inbox/TODO and publish proposals.
    process-workbench -> process_workbench.py: apply human decisions, execute, and curate.
    organize-papers -> organize_papers.py: organize existing raw Notero records.
    organize-articles -> organize_articles.py: organize existing SimpRead captures.
    recommend-papers -> recommend_papers.py: discover and assess new candidates.

Inputs and outputs:
    The runtime supplies services, indexes, and configuration. Date or explicit
    page scope comes from the trigger. Outputs are confirmed links or a report
    separating actual publications from selections, failures, and rejections.

Participants:
    Human operator/reviewer, dispatcher, DBOS runtime, and the reading, reasoning,
    execution, and storage capabilities required by the selected task.

Boundaries:
    Shared operations live in ../steps; task-specific phases stay beside their
    task. Scheduling frequency belongs to commands/serve and runtime/schedules,
    not to these workflows. Capability implementations belong to plugins.
"""
