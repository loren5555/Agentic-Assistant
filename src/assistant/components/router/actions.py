"""Capabilities selected before a proposal is presented for approval.

The execution service dispatches these identifiers to matching capabilities.
This catalogue describes what each capability produces, not provider details.
"""

from assistant.components.router.models import ActionCandidate

EXECUTION_ACTIONS = [
    ActionCandidate(id="plan", name="Develop an execution plan", description=(
        "Design a concrete plan for subsequent work: steps, materials, parameters, "
        "resources, budget, stopping conditions and acceptance criteria. Return the "
        "plan for human review before the planned operations are performed."
    )),
    ActionCandidate(id="propose_direction", name="Propose research directions", description=(
        "Develop research directions, questions and interest proposals from the supplied material, "
        "returning reviewable reasoning and possible next investigations."
    )),
    ActionCandidate(
        id="complete_task",
        name="Complete a task",
        description=(
            "Complete a self-contained calculation, explanation, translation, "
            "or text transformation using the supplied material and return the result."
        ),
    ),
    ActionCandidate(
        id="organize_material",
        name="Organize supplied material",
        description=(
            "Organize supplied papers, articles or notes into evidence-scoped reading "
            "briefs and reusable knowledge products, including useful reading metadata "
            "and source attribution."
        ),
    ),
    ActionCandidate(
        id="investigate_question",
        name="Investigate public sources",
        description=(
            "Research a question using public sources, verify unknown or current "
            "facts, and produce an evidence-backed answer with supporting links."
        ),
    ),
]
