"""Storage implementations for the discovery-pool component.

Input origin:
    Recommendation workflows supply lightweight public discoveries.
Output destination:
    The Notion implementation maintains Discovery Pool under Assistant and
    returns candidates and human feedback to the recommendation workflow.
Responsibility:
    Own cache persistence, source deduplication and bounded retention.
"""
