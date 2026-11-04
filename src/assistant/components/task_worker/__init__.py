"""Complete one approved task snapshot and return reviewable results.

Input origin:
    Router selects execution after Workbench approval. TaskRequest includes its
    source version, original material, supplements, prior work and instructions.
Output destination:
    TaskResult returns to Workbench; typed products wait for acceptance before
    Curator and Information Publisher retain them.
Responsibility:
    Execute within approved scope using configured tools. Workers neither interpret
    review statuses nor own feedback loops. Reconciled work enters as a new task.
"""
