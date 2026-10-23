"""Organize business processes as complete tasks and reusable durable operations.

Responsibility:
    Connect component capabilities in the required order while keeping human
    review boundaries, external writes, and local DBOS progress explicit.

Inputs and outputs:
    Commands or schedules select a task and supply scope such as date/page ID.
    Tasks return confirmed destination links or recommendation reports; their
    intermediate model results and workflow state are checkpointed separately.

Structure:
    tasks/ contains the five complete user-facing processes. steps/ contains
    genuinely shared submission/capture operations, including child workflows
    when an operation has several independently checkpointed phases. A file's
    folder does not imply that every function is a single DBOS step.

Participants and boundaries:
    Commands trigger work; tasks own business sequencing; components define
    capabilities; plugins implement them. runtime/application.py binds registered
    DBOS instances, and runtime/recovery.py manages reuse and recovery. Importing
    this package alone does not launch DBOS or perform external operations.
"""
