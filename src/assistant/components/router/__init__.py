"""Interpret work and select one currently available action.

Input origin:
    reviews builds RouterInput from the human-approved proposal, original
    source material, human instructions, and the permitted execution candidates.
    Approval/feedback comes from Workbench; structured task state comes from DBOS.

Output destination:
    RouterDecision returns to reviews. Its dispatcher calls TaskWorker
    or Investigator, or publishes a clarification through Workbench. The selected
    capability later returns the result that the workflow displays in Workbench.

Responsibility:
    Identify the user's intent and choose a next action from the supplied
    candidates, including asking the user when essential information is missing.

Inputs:
    RouterInput containing meaningful text, relevant context, and ActionCandidate
    definitions. Context-bearing sources can be adapted with from_source().

Outputs:
    RouterDecision with content types, intent, reasoning, the selected action,
    a suggested next step, and an optional clarification question.

Participants:
    Decision agent and reviews execution dispatcher. The current workflow
    uses this component after human approval, not to generate intake proposals.

Boundaries:
    A decision is not an execution result. The router does not approve proposals,
    call the selected worker itself, or own storage and workflow state.
"""
