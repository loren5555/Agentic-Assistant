"""Executable capabilities offered for an approved task.

The execution service dispatches these identifiers to matching capabilities.
This catalogue describes what each capability produces, not provider details.
"""

from assistant.components.router.models import ActionCandidate

EXECUTION_ACTIONS = [
    ActionCandidate(
        id="complete_task",
        description=(
            "Complete a self-contained calculation, explanation, translation, "
            "or text transformation using the supplied material and return the result."
        ),
    ),
    ActionCandidate(
        id="organize_material",
        description=(
            "Structure existing notes or material into a useful, reviewable "
            "draft that preserves source attribution."
        ),
    ),
    ActionCandidate(
        id="investigate_question",
        description=(
            "Research a question using public sources, verify unknown or current "
            "facts, and produce an evidence-backed answer with supporting links."
        ),
    ),
    ActionCandidate(
        id="ask_user",
        description=(
            "Obtain essential missing information, material, intent, or choices "
            "that only the user can provide through a focused question."
        ),
    ),
]
