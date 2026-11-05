"""Adapt source databases to the shared intake boundary.

Input origin:
    Inbox, elevated TODO, Notero, SimpRead, Interested Papers/Feed and research interests.
Output destination:
    Immutable SourceMaterial snapshots enter Organizer and Proposer; acknowledgements
    and reconciled feedback go back to the same source record.
Responsibility:
    Each source owns its selection, extraction and simple bookkeeping. Processors do
    not plan work or execute approved proposals.
"""
