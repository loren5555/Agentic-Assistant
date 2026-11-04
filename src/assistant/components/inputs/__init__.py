"""Define immutable effective input for all information sources.

Input origin:
    Independent processors read original content, source metadata, current human
    supplements and feedback history from registered source databases.
Output destination:
    Organizer, Proposer and approved workers consume the same SourceMaterial
    snapshot. Reconciler appends feedback on its original source.
Responsibility:
    Separate semantic input identity from Notion timestamps and queue flags.
    SourceHistory retains previous work without rewriting original source text.
"""
