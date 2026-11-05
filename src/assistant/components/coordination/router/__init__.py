"""Select the capability shown to the human before proposal approval.

Input origin:
    Shared intake supplies the draft proposal, effective source context and the
    available action catalogue after Proposer finishes its interpretation.
Output destination:
    The action selection is checkpointed and stored on the proposal. Workbench
    displays its name and scope for approval; execution uses this saved choice.
Responsibility:
    Return only a selected action identifier. Selected components prepare their
    own parameters and output. Clarification proposals already target the human
    and bypass routing.
"""
