"""Read human-submitted material for proposal intake.

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
    Human submitter, input-source storage plugin, process_inputs task, and the
    proposal submission steps that archive Inbox or mark TODO handled.

Boundaries:
    This is a source-reader role, not a planner. It does not infer intent, draft
    proposals, approve work, or decide when the workflow should run.
"""
