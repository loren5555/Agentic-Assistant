"""Balance source acquisition and reading across breadth and publication age.

Inputs are published-history counts, normalized target weights and existing stock.
Outputs are collection priorities and an interleaved reading order. Quality remains
an independent editorial gate; these weights never require filling a quota.
"""

from calendar import monthrange
from datetime import date, timedelta

from .models import CoverageCell

AGES = ("week", "month", "quarter", "half_year", "year", "three_years", "older")


def months_before(day: date, months: int) -> date:
    """Shift by calendar months, clamping month-end dates consistently."""
    number = day.year * 12 + day.month - 1 - months
    year, month = divmod(number, 12)
    return date(year, month + 1, min(day.day, monthrange(year, month + 1)[1]))


def age_bounds(day: str, bucket: str) -> tuple[str, str]:
    """Return inclusive, disjoint publication-date bounds for an age interval."""
    end = date.fromisoformat(day)
    edges = [
        end,
        end - timedelta(days=7),
        months_before(end, 1),
        months_before(end, 3),
        months_before(end, 6),
        months_before(end, 12),
        months_before(end, 36),
    ]
    position = AGES.index(bucket)
    newer = edges[position] if position == 0 else edges[position] - timedelta(days=1)
    older = edges[position + 1] if position + 1 < len(edges) else date(1, 1, 1)
    return older.isoformat(), newer.isoformat()


def age_bucket(published: str, day: str) -> str:
    """Classify a known date; unknown/future dates stay outside target statistics."""
    try:
        value = date.fromisoformat(published)
    except ValueError:
        return "unknown"
    if value > date.fromisoformat(day):
        return "unknown"
    for bucket in AGES:
        start, end = age_bounds(day, bucket)
        if start <= published <= end:
            return bucket
    return "unknown"


def coverage_table(
    breadths: dict, ages: dict, counts: dict, horizon: int
) -> list[CoverageCell]:
    """Project marginal targets into a table and calculate soft publication gaps."""
    total = sum(counts.values())
    table = []
    for breadth, bw in breadths.items():
        for age, aw in ages.items():
            target = bw / sum(breadths.values()) * aw / sum(ages.values())
            count = counts.get(f"{breadth}:{age}", 0)
            table.append(
                CoverageCell(
                    breadth=breadth,
                    age=age,
                    target=target,
                    published=count,
                    deficit=target * (total + horizon) - count,
                )
            )
    return sorted(table, key=lambda cell: cell.deficit, reverse=True)


def balanced_order(candidates, cells: list[CoverageCell], day: str):
    """Favor undercovered cells while retaining model order within each cell."""
    remaining = list(candidates)
    counts = {(cell.breadth, cell.age): cell.published for cell in cells}
    targets = {(cell.breadth, cell.age): cell.target for cell in cells}
    ordered = []
    while remaining:
        total = sum(counts.values()) + 1

        def priority(candidate):
            key = candidate.breadth, age_bucket(candidate.published_date, day)
            return targets.get(key, 0) * total - counts.get(key, 0)

        best = max(range(len(remaining)), key=lambda i: priority(remaining[i]))
        candidate = remaining.pop(best)
        ordered.append(candidate)
        key = candidate.breadth, age_bucket(candidate.published_date, day)
        counts[key] = counts.get(key, 0) + 1
    return ordered
