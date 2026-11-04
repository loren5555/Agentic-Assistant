"""Develop a concrete plan as a separately approved task.

Input origin:
    Workbench supplies a proposal whose saved action is plan, its source context
    and the human's instructions after proposal approval.
Output destination:
    A structured plan returns to Workbench for result review. Once qualified,
    the workflow returns it to the original source and prepares a fresh execution
    proposal. The next executor receives the accepted plan after fresh approval.
Responsibility:
    Specify steps, inputs, parameters, resources, budget, stopping conditions and
    acceptance criteria. Report essential user-owned gaps as questions.
"""
