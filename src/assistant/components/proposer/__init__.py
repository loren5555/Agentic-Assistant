"""Turn supplied material into a proposal a human can review.

Responsibility:
    Interpret the source, explain why work is useful, and define a concrete
    action, plan, expected deliverable, and criteria for judging the result.

Inputs:
    SourceMaterial and, for revision, a previous WorkbenchItem with its proposal
    and human feedback.

Outputs:
    A Proposal with understanding, purpose, rationale, action, plan, expected
    result, source fingerprint, version, and optional execution telemetry.

Participants:
    Proposal-drafting agent, submit_proposal steps, and the human approver who
    reads the report published by the Workbench storage component.

Boundaries:
    Drafting does not publish, approve, or execute the proposal. The workflow
    controls source checks, storage writes, checkpoints, and revision cycles.
"""
