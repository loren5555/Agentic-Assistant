"""Turn supplied material into a proposal a human can review.

Input origin:
    Inbox/TODO records come through InputSource and intake; Notero or
    SimpRead material can arrive through organize_capture. Shared proposal steps
    pass these sources to draft(). Revision feedback comes from Workbench, with
    the previous structured proposal loaded from DBOS state.

Output destination:
    Proposal returns to steps/submit_proposal.draft and is checkpointed by DBOS.
    The calling workflow then invokes Workbench.submit/revise to publish it to
    the Notion Workbench for human approval. Proposer itself accesses no database.

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
