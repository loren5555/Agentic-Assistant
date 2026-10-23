"""Select reusable knowledge and ideas from a human-accepted result.

Responsibility:
    Decide what remains useful beyond the completed task and extract grounded,
    standalone material. An empty extraction is a valid outcome.

Inputs:
    WorkbenchItem carrying the proposal, completed result, and human acceptance.

Outputs:
    CurationDecision explaining the choice and listing RetainedArtifact entries
    for knowledge or ideas. Publication receipts are attached by the workflow.

Participants:
    Curation agent, process_reviews after Qualified acceptance, ArchiveStore,
    and the human who later reads retained material.

Boundaries:
    Extraction does not publish or close the task. The workflow archives the
    selected artifacts and chooses Archived, or Finished when nothing is retained.
"""
