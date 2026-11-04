"""Locate complete jobs by the same action names exposed by run JOB.

Input origin:
    Manual commands and explicitly configured schedules.
Output destination:
    Proposals/results in Workbench, accepted typed outputs, or autonomous Feed entries.
Task map:
    propose_tasks: Inbox and elevated TODO -> shared intake -> Workbench.
    organize_papers: Notero Processor -> shared intake -> Workbench.
    organize_articles: SimpRead Processor -> shared intake -> Workbench.
    process_signals: Interested paper/feed and explicit interest requests -> intake.
    reconcile_feedback: Workbench feedback -> new source version or rejection.
    process_workbench: approvals -> execution; acceptance -> curation/publication.
    recommend_papers: interests and external evidence -> Research Feed.
Boundaries:
    Job modules select business responsibilities. Components own capabilities;
    plugins implement storage/model details. Checkpoints live in the v2 runtime,
    isolated from the immutable v0.1 release.
"""
