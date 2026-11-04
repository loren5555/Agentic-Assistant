"""Locate shared durable operations beneath the named business jobs.

Input origin:
    Source workflows select roles and call intake_sources.
Output destination:
    Source snapshots pass through Organizer, Proposer and action selection into Workbench; verified
    submission acknowledges the same source version.
Responsibilities:
    intake_sources.py handles bounded extraction and source-version deduplication.
    submit_proposal.py checkpoints organization, drafting, publication and source
    acknowledgement separately so retries retain successful model work.
    select_action.py checkpoints the capability presented for approval.
    advance_plan.py returns qualified plans to their source for fresh proposals.
    Approved execution and feedback reconciliation live in their own task modules.
"""
