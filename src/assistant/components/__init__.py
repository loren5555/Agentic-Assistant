"""Describe the capabilities available to the assistant's workflows.

Input origin:
    Commands and task workflows supply material through these contracts. Business
    sources include Inbox/TODO, Workbench human decisions, Notero/SimpRead,
    Research Interests, Research Feed, and retrieved public evidence.

Output destination:
    Capability results return to their calling workflows. Those workflows decide
    the next consumer and persist state in DBOS/indexes or publish to Workbench,
    Papers, Knowledge, Ideas, Research Feed, or Inbox through storage plugins.

Responsibility:
    Give each business component one vocabulary, data contract, and interface.
    Its models.py defines exchanged data; protocol.py defines callable services.
    Read the component's package docstring first to locate its role in a process.

Inputs and outputs:
    Sources become proposals, approved tasks become results, and accepted results
    may become retained knowledge or ideas. Captures and recommendations provide
    separate entry paths for existing reading material and newly discovered work.

Participants:
    Workflow authors use these contracts; plugins/<component>/<source> implements
    them. Human reviewers approve proposals and judge execution results.

Boundaries:
    A component is a capability, not necessarily an agent. Reading, publishing,
    and archiving can be scripts; proposing, routing, and investigating can use
    models. Commands trigger workflows, which own ordering and DBOS checkpoints.
    Importing this package neither constructs plugins nor starts work.
"""
