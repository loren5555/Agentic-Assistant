"""Complete one approved task snapshot and return reviewable results.

Input origin:
    Workbench approval authorizes the capability selected before publication.
    TaskRequest includes its source version, original material, supplements,
    prior work, human instructions and any separately confirmed execution plan.
Output destination:
    TaskResult returns to Workbench; typed products wait for acceptance before
    Curator and Information Publisher retain them. Essential missing information
    returns as questions for the human through Needs Input.
Responsibility:
    Execute within approved scope using configured tools. Workers neither interpret
    review statuses nor own feedback loops. Reconciled work enters as a new task.
"""
