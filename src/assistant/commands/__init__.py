"""Translate user commands into task execution or runtime administration.

Input origin:
    The human CLI is parsed by assistant/cli.py; main.py loads YAML and creates
    Application, whose execute() selects the matching command module. Application
    supplies configured services and the selected local DBOS runtime.

Output destination:
    run/serve hand work to the task dispatcher; resume targets existing DBOS work;
    setup updates configured storage schemas; status reads DBOS administration
    state. Result JSON goes to stdout and operational logs go to shared handlers.
    Each business task owns its eventual Notion destinations.

Responsibility:
    Provide one module for each CLI command: setup, run, serve, status, and resume.
    main.py parses arguments and Application prepares the runtime before calling
    a command's run(application, options) entry point.

Inputs:
    Parsed CLI options, YAML settings, registered workflows, and lazy services
    supplied by Application. Commands do not accept credentials through prompts.

Outputs:
    Run/resume print business results as JSON; status prints saved runtime state.
    Setup reports schema initialization, while serve stays active until stopped.
    Progress and failures use the shared logger rather than the JSON channel.

Workflow relationship:
    run.dispatch maps five user-facing job names to workflows/tasks. serve uses
    runtime/schedules.py to call the same dispatcher. resume addresses an existing
    workflow ID; setup/status administer storage and durability rather than
    implementing a business task. Shared task operations live in workflows/steps.

Participants:
    Human operator, Application runtime, DBOS scheduler/recovery services, and
    business tasks using their configured component implementations.

Runtime effects:
    Application launches DBOS before command dispatch, so unfinished work may be
    recovered even during status/setup. CLI help exits before runtime launch.
    Commands do not grant human approval or bypass workflow authorization checks.
"""
