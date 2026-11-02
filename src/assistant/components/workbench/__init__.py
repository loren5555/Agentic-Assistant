"""Provide the human-facing workspace for proposals, decisions, and results.

Input origin:
    Proposal submission steps supply source/proposal data from InputSource or
    captures. reviews supplies execution results, questions, and lifecycle
    changes. Human approval, acceptance, and feedback originate in Notion Workbench.

Output destination:
    Reports, publication receipts, and requested lifecycle changes are written to
    the Notion Workbench. WorkbenchItem snapshots return to the calling workflow
    for DBOS/index checkpoints and the next review pass; humans read the pages.

Responsibility:
    Store proposal reports, read human feedback, publish revised reports and
    execution results, and apply lifecycle changes requested by workflows.

Inputs:
    SourceMaterial, Proposal, WorkbenchItem, TaskResult, clarification questions,
    and explicit lifecycle updates from intake and review workflows.

Outputs:
    WorkbenchItem snapshots, published reports, current approval/acceptance
    properties, and Publication Key receipts for completed report writes.

Participants:
    Storage plugin, proposal drafter, execution worker, curator, and human
    approver/reviewer. Workflows connect these roles; Workbench is their shared
    review surface, not a separate agent or autonomous workflow.

Boundaries:
    The workflow owns transition policy and DBOS state. The storage component
    preserves human feedback and confirms publication through a property receipt,
    not exact Markdown equality. Humans review the report's substantive quality.
"""
