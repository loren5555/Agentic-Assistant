"""Produce the deliverable requested by an approved proposal.

Input origin:
    reviews supplies TaskRequest after reading Workbench approval and
    routing complete_task/organize_material. The proposal comes from DBOS state;
    original source content and current human instructions are added by the task.

Output destination:
    TaskResult returns to reviews.execute, which checkpoints the result
    before save_result publishes it in Notion Workbench as Executed. Human
    acceptance then determines redo or later curation; the worker writes no row.

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
    Execution agent, any tools made available by its plugin, reviews,
    and the human reviewer who accepts or rejects the published result.

Boundaries:
    Available tools depend on the implementation. The interface does not imply
    filesystem or network access. The worker does not manage approval, write
    Workbench lifecycle state, schedule jobs, or decide archival policy.
"""
