"""Define source, review-space and publication interfaces.

Input origin:
    Workflow read/write requests and accepted products.
Output destination:
    Source snapshots, Workbench state, cached discoveries and verified destination receipts.
Responsibility:
    Storage components own persistence operations; coordination and execution roles own interpretation and task behavior.
"""
