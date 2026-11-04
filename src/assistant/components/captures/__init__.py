"""Provide evidence-aware reading briefs used during approved execution.

Input origin:
    An approved paper/article task and its original source material.
Output destination:
    CaptureBriefer returns a reading product for Workbench acceptance.
    The specialized Papers writer is used internally by Information Publisher.
Responsibility:
    Preserve original abstracts, useful reading metadata and evidence scope.
    Source extraction belongs to processors; intake no longer publishes final briefs.
"""
