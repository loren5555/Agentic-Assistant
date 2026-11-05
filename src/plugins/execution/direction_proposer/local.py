"""Develop research directions as approved work, returning results for review."""

from plugins.execution.task_worker.local import TaskWorker


class DirectionProposer(TaskWorker):
    """Produce direction proposals without editing interests or executing experiments.

    Input:
        An approved task and its complete source snapshot.
    Output:
        Reviewable direction analysis and candidate research_interest/idea artifacts.
    """

    instructions = TaskWorker.instructions + """
Your specialty is proposing research directions. Identify a concrete question,
motivation, existing evidence, unknowns and a feasible next investigation. Distinguish
explicit user interests from speculative suggestions. Do not claim a direction has
been adopted or experiments performed. Return the analysis to Workbench for review.
"""
