"""Capabilities selected before a proposal is presented for approval.

The execution service dispatches these identifiers to matching capabilities.
This catalogue describes what each capability produces, not provider details.
"""

from assistant.components.coordination.router.models import ActionCandidate

CODEX_EXPERIMENT = ActionCandidate(
    id="run_experiment", accepts_external_report=True, name="Execute experiment · Codex",
    description="Run the human-qualified experimental protocol with native Codex tools, "
                "retain programs and measurements, and report observed results against its criteria.",
)

AMINER_RESEARCH = ActionCandidate(
    id="investigate_literature", accepts_external_report=True,
    name="学术文献调研 · AMiner 沉思",
    description="Survey public academic literature across papers and return a research report with references.",
)

EXECUTION_ACTIONS = [
    ActionCandidate(id="plan", name="Develop an execution plan", description=(
        "Design a concrete plan for subsequent work: steps, materials, parameters, "
        "resources, budget, stopping conditions and acceptance criteria. Return the "
        "plan for human review before the planned operations are performed."
    )),
    ActionCandidate(id="propose_direction", accepts_external_report=True, name="Propose research directions", description=(
        "Develop research directions, questions and interest proposals from the supplied material, "
        "returning reviewable reasoning and possible next investigations."
    )),
    ActionCandidate(
        id="complete_task", accepts_external_report=True,
        name="Complete a task",
        description=(
            "Complete a self-contained calculation, explanation, translation, "
            "or text transformation using the supplied material and return the result."
        ),
    ),
    ActionCandidate(
        id="organize_material", accepts_external_report=True,
        name="Organize supplied material",
        description=(
            "Organize supplied papers, articles or notes into evidence-scoped reading "
            "briefs and reusable knowledge products, including useful reading metadata "
            "and source attribution."
        ),
    ),
    ActionCandidate(
        id="investigate_question", accepts_external_report=True,
        name="Investigate public sources",
        description=(
            "Research a question using public sources, verify unknown or current "
            "facts, and produce an evidence-backed answer with supporting links."
        ),
    ),
]


def supports_external_report(action_id: str) -> bool:
    """Use the current capability contract for both new and previously saved proposals."""
    return any(action.id == action_id and action.accepts_external_report
               for action in (*EXECUTION_ACTIONS, CODEX_EXPERIMENT, AMINER_RESEARCH))
