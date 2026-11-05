"""Organize workflow capabilities by responsibility and contract ownership.

Input origin:
    Commands trigger workflows; those workflows supply source material, approved
    tasks, human feedback and newspaper preferences to component contracts.
Output destination:
    Results return to workflows or data interfaces for Workbench review, accepted
    publication or autonomous Discovery Pool/Research Feed updates.
Responsibility:
    coordination contains interpretation and lifecycle decisions; execution holds
    delegated work; recommendations owns the newspaper's search/reading/editorial
    roles; data defines source, review-space, cache and publication operations.
Participants:
    Workflows use each role's models/protocol. plugins follows the same categories
    and provides local, Codex or Notion implementations. Data types have one owning
    component and are imported by their consumers.
Boundaries:
    Components do not replace workflow orchestration. DBOS registration, ordering,
    checkpoints and human authorization remain in workflows/runtime. Importing
    this package neither constructs plugins nor starts work.
"""
