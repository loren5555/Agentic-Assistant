"""Business capabilities offered when interpreting an Inbox item.

These descriptions define the current selection catalogue, not executable
handlers. The workflow presents this catalogue before any downstream work.
"""

from assistant.schemas.routing import ActionCandidate


INBOX_CANDIDATES = [
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
            "Explain, analyze, or investigate the user's question and produce "
            "an evidence-backed answer, researching unknown facts as needed."
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
