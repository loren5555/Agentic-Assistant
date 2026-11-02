"""Organize existing raw paper and article captures into useful reading outputs.

Input origin:
    Notero contains raw Zotero-synced papers; the independent SimpRead collection
    contains captured articles. papers/articles invoke shared
    organize_capture steps, which pass source snapshots to the briefing capability.

Output destination:
    Raw captures flow to the briefing agent. Its brief flows to the capture
    publisher for Notion Papers/Knowledge, or to submit_proposal and Workbench for
    further work. Receipts return to the workflow for DBOS/index bookkeeping;
    successful acknowledgement updates only SimpRead, never Notero.

Responsibility:
    Separate source reading, evidence-grounded briefing, and output publication
    so workflows can deduplicate, checkpoint, and retry each part independently.

Inputs:
    Notero/SimpRead collection selection, pending page revisions or an explicit
    page ID, followed by RawCapture content and metadata for interpretation.

Outputs:
    CaptureBatch and RawCapture snapshots; CaptureBrief proposing Papers,
    Knowledge, or further work; CaptureReceipt for a published brief. Proposal
    destinations are handed to the proposal/Workbench path by the workflow.

Participants:
    Capture-source storage plugin, briefing agent, capture publisher, and the
    papers/articles tasks sharing organize_capture steps.

Boundaries:
    Notero is the raw input; Papers is organized output. Notero stays read-only;
    successfully handled SimpRead records can be marked archived. Links and
    attachment metadata do not establish that a paper's full text was read.
"""
