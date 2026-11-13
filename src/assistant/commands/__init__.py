"""Expose one user-facing module for each local service operation.

Input origin:
    assistant.cli parses options; main loads YAML and routes the selected command.
Output destination:
    run/status/resume send loopback HTTP requests and print JSON. Serve owns the
    DBOS queues, providers and execution logs. Setup adds configured Notion schema.
Responsibilities:
    serve starts the single executor and accepts clients. run submits one business
    job and optionally waits. status reads saved state/steps/results. resume asks
    for durable recovery. setup runs exclusively with serve stopped, without DBOS.
Workflow relationship:
    Manual and scheduled requests enqueue workflows/tasks/dispatch.py under the
    stable JobWorkflows.dispatch identity. Existing task/step modules continue to
    own business ordering, human authorization and output destinations.
Runtime boundary:
    Only serve launches DBOS and automatic recovery. CLI observation never creates
    an executor or opens the application database. All accepted work survives
    caller disconnection through DBOS persistence.
"""
