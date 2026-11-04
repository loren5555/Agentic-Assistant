"""Implement the autonomous daily research recommendation capabilities.

Input origin:
    Human-maintained Research Interests and Interested Papers provide preferences.
    Codex discovery produces public candidates; its reader supplies primary excerpts.
Output destination:
    Local assessment returns grounded decisions; the Notion service publishes
    qualified recommendations to Research Feed. Events and usage go to local reports.
Responsibility:
    Keep public research, evidence assessment and Feed storage independently
    configurable. The explicit demo provider exercises the path without live services.
"""
