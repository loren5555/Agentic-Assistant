"""Balance a curated newspaper across familiar and exploratory disciplines."""

import random
from assistant.components.recommendations.discovery.models import BREADTHS, PaperCandidate


def exploration_order(candidates: list[PaperCandidate], counts: dict[str, int],
                      weights: dict[str, float], seed: str) -> list[PaperCandidate]:
    """Order ranked candidates by coverage deficit with reproducible tie sampling.

    Args:
        candidates: Model-ranked metadata; order within each breadth is retained.
        counts: Actual historical publication counts, not assumed daily quotas.
        weights: Relative long-term target shares across breadths.
        seed: Edition identity for stable randomness during checkpoint replay.

    Returns:
        Reading order mixing broad exploration with the best core candidates.
    """
    queues = {breadth: [c for c in candidates if c.breadth == breadth] for breadth in BREADTHS}
    working = {breadth: counts.get(breadth, 0) for breadth in BREADTHS}
    total_weight = sum(max(0, weights.get(breadth, 0)) for breadth in BREADTHS)
    if total_weight <= 0:
        raise ValueError("Recommendation exploration weights must include a positive share")
    rng = random.Random(seed)
    result = []
    while any(queues.values()):
        available = [breadth for breadth in BREADTHS if queues[breadth]]
        rng.shuffle(available)
        total = sum(working.values()) + 1
        breadth = max(available, key=lambda b: max(0, weights.get(b, 0)) / total_weight * total - working[b])
        result.append(queues[breadth].pop(0))
        working[breadth] += 1
    return result
