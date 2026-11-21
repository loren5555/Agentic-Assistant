"""Connect local operators to the one process that owns DBOS execution.

Input origin:
    CLI run/status/resume requests, browser observations/maintenance, and schedule triggers.
Output destination:
    Durable DBOS queues and saved workflow reports, exposed over loopback HTTP.
Responsibility:
    Separate submission and observation from execution. Clients never launch DBOS,
    initialize providers or open the application database. Serve owns recovery,
    queues, HTTP and the static panel; business policy stays in the existing workflows.
"""
