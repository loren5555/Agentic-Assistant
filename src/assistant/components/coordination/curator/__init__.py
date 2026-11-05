"""Select reusable knowledge and ideas from a human-accepted result.

Input origin:
    process_workbench invokes extract after Result Review = Qualified in Workbench.
    It supplies a WorkbenchItem whose structured proposal/result is loaded from
    DBOS state and whose current acceptance/feedback comes from Notion properties.

Output destination:
    CurationDecision returns to process_workbench.extract. The workflow sends each
    selected artifact to ArtifactPublisher for Knowledge/Ideas publication, saves the
    receipts, and marks Workbench Archived, or Finished when nothing is retained.

Responsibility:
    Decide what remains useful beyond the completed task and extract grounded,
    standalone material. An empty extraction is a valid outcome.

Inputs:
    WorkbenchItem carrying the proposal, completed result, and human acceptance.

Outputs:
    CurationDecision explaining the choice and listing RetainedArtifact entries
    for knowledge or ideas. Publication receipts are attached by the workflow.

Participants:
    Curation agent, process_workbench after Qualified acceptance, ArtifactPublisher,
    and the human who later reads retained material.

Boundaries:
    Extraction does not publish or close the task. The workflow archives the
    selected artifacts and chooses Archived, or Finished when nothing is retained.
"""
