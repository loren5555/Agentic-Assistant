"""Store retained knowledge and ideas independently of task execution.

Responsibility:
    Publish a selected reusable artifact under a stable identity and recover an
    existing publication on retry instead of creating duplicate destinations.

Inputs:
    A human-accepted WorkbenchItem, one RetainedArtifact selected by the curator,
    and a stable publication key supplied by the workflow.

Outputs:
    ArchiveReceipt identifying the confirmed destination URL and publication key.

Participants:
    Archive storage plugin, curation steps in process_reviews, and human readers
    of the Knowledge and Ideas collections.

Boundaries:
    This is a publishing role, not an agent deciding what is valuable. It does
    not generate artifacts, approve results, schedule jobs, or close Workbench.
"""
