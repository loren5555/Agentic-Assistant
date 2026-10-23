"""Answer delegated questions using attributable evidence.

Responsibility:
    Investigate facts beyond the supplied material and distinguish supported
    findings from missing information, inaccessible sources, and uncertainty.

Inputs:
    InvestigationRequest containing the question and relevant context.

Outputs:
    InvestigationReport containing an answer, SourceEvidence links and findings,
    limitations, and optional provider execution events and token usage.

Participants:
    Research/investigation agent, its implementation's retrieval tools, and the
    process_reviews dispatcher selecting investigate_question for approved work.
    The workflow presents the returned report for human acceptance.

Boundaries:
    Investigation itself does not change external workflow records or create a
    paper-library entry. Publishing and acceptance are separate responsibilities.
"""
