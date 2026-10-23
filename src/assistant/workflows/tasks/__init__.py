"""Locate complete workflows by the business action requested by the user.

Responsibility:
    Provide the processes selected by run.dispatch and reused by scheduled jobs.
    Each task advances work to its next human boundary or completes one bounded
    processing pass; it is not a permanently running agent.

Task map:
    intake -> process_inputs.py: read Inbox/TODO and publish proposals.
    reviews -> process_reviews.py: apply human decisions, execute, and curate.
    papers -> organize_papers.py: organize existing raw Notero records.
    articles -> organize_articles.py: organize existing SimpRead captures.
    recommendations -> recommend_papers.py: discover and assess new candidates.

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
