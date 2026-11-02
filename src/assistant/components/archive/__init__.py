"""Store retained knowledge and ideas independently of task execution.

Input origin:
    reviews receives a CurationDecision from Curator after human result
    acceptance. It passes each retained artifact, the originating WorkbenchItem,
    and a stable archive key to ArchiveStore.publish.

Output destination:
    The storage plugin writes Knowledge or Ideas in Notion. ArchiveReceipt returns
    to reviews, which attaches the link to its curation state in DBOS and
    finalizes the Workbench lifecycle after publication succeeds.

Responsibility:
    Publish a selected reusable artifact under a stable identity and recover an
    existing publication on retry instead of creating duplicate destinations.

Inputs:
    A human-accepted WorkbenchItem, one RetainedArtifact selected by the curator,
    and a stable publication key supplied by the workflow.

Outputs:
    ArchiveReceipt identifying the confirmed destination URL and publication key.

Participants:
    Archive storage plugin, curation steps in reviews, and human readers
    of the Knowledge and Ideas collections.

Boundaries:
    This is a publishing role, not an agent deciding what is valuable. It does
    not generate artifacts, approve results, schedule jobs, or close Workbench.
"""
