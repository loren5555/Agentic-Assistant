"""Produce the deliverable requested by an approved proposal.

Responsibility:
    Complete supplied-material work such as calculations, explanations, and text
    organization; redo an unqualified result using the user's feedback.

Inputs:
    TaskRequest containing the approved Proposal, Workbench URL, human
    instructions, and whether this is a redo.

Outputs:
    TaskResult containing the actual deliverable, selected action identity, and
    optional provider telemetry, rather than another promise or execution plan.

Participants:
    Execution agent, any tools made available by its plugin, process_reviews,
    and the human reviewer who accepts or rejects the published result.

Boundaries:
    Available tools depend on the implementation. The interface does not imply
    filesystem or network access. The worker does not manage approval, write
    Workbench lifecycle state, schedule jobs, or decide archival policy.
"""
