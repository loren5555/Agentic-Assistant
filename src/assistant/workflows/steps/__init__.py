"""Locate shared durable operations beneath the named business jobs.

Input origin:
    Source workflows select roles and call intake_sources.
Output destination:
    Source snapshots pass through Organizer and Proposer into Workbench; verified
    submission acknowledges the same source version.
Responsibilities:
    intake_sources.py handles bounded extraction and source-version deduplication.
    submit_proposal.py checkpoints organization, drafting, publication and source
    acknowledgement separately so retries retain successful model work.
    Approved execution and feedback reconciliation live in their own task modules.
"""
