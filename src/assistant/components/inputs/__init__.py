"""Read human-submitted material for proposal intake.

Input origin:
    Human entries in the configured Notion Inbox and elevated TODO collections.
    Interested Research Feed follow-ups can also enter Inbox. intake and
    shared submission steps call InputSource to fetch these records.

Output destination:
    SourceMaterial returns to intake, then shared submit_proposal passes
    it to Proposer. After Workbench publication and checkpointing, the workflow
    calls close_source to write Archived to Inbox or handled to TODO.

Responsibility:
    Retrieve eligible Inbox and elevated TODO entries, expose their meaningful
    content, and acknowledge them only after successful proposal publication.

Inputs:
    Source collection settings and original source URLs. The current intake
    selects Inbox Status != Archived and TODO Status = elevated.

Outputs:
    SourceMaterial snapshots carrying content, identity, provenance, and revision.
    ContextContent exposes model-facing text without requiring a shared schema.

Participants:
    Human submitter, input-source storage plugin, intake task, and the
    proposal submission steps that archive Inbox or mark TODO handled.

Boundaries:
    This is a source-reader role, not a planner. It does not infer intent, draft
    proposals, approve work, or decide when the workflow should run.
"""
