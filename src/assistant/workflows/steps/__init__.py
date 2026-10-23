"""Share durable operations used by more than one complete task.

Responsibility:
    Keep proposal submission and raw-capture organization consistent across
    callers without collecting every low-level function into a common toolbox.

Operation map:
    submit_proposal.py: draft, publish, checkpoint, and acknowledge a proposal.
    organize_capture.py: read, brief, publish/propose, and acknowledge captures.

Inputs and outputs:
    Parent workflows pass source snapshots or collection/page scope. Operations
    return confirmed destinations and persist the model outputs or state needed
    for retries. They can update Notion sources after successful publication.

Participants and boundaries:
    Intake, review/revision, paper, and article tasks call these operations;
    plugins provide the individual capabilities. Some helpers are DBOS steps,
    others are child workflows spanning several steps. Registration and instance
    binding belong to runtime/application.py; schedules remain outside this layer.
"""
