"""Editorial priorities shared by discovery, ranking and close source reading."""




QUALITY_POLICY = """
Prefer credible, substantively useful research. Verified CCF A venues and top-quartile
journals are strong discovery priors. Record the ranking system, year and category;
JCR Q1 and CAS Zone 1 are distinct, and SCI indexing alone is not a quartile.
Verify the exact publication/acceptance status on proceedings or publisher pages.
A workshop, short paper, demo or submission does not inherit a main-conference rank.
Use the current official CCF list and authoritative journal metadata when accessible.
Leave unverified rankings unknown, with links and access limits; never guess a tier.

Give extra attention to authors with verified, relevant contributions or a strong
record in the topic. Explain that record with source links rather than prestige-only
name dropping. Author reputation and venue are priors, not proof of a paper's claims.

A less-established author or venue, including a preprint, can merit selection for a
concrete original mechanism, valuable theory, convincing insight or an unexpected
foundational connection. Name what is new relative to the supplied prior work.
Avoid generic novelty claims. Benchmark scores or large reported gains alone are
weak reasons to select incremental work. Inspect fair/strong baselines, compute and
data budgets, leakage/contamination, ablations, variance across seeds, evaluation
coverage, reproducibility artifacts and limitations when available. Missing details
are uncertainty, not evidence of misconduct. Deprioritize thin novelty plus opaque
score-heavy claims; do not call a paper fraudulent based on scores alone.

Preserve cross-disciplinary exploration. Recognize established venues and seminal
contributions within mathematics, physics, psychology and other source disciplines;
absence from a computer-science ranking is not a rejection reason. A foundational
work can merit reading for conceptual value without being a new score improvement.

For tools, datasets and non-paper discoveries, judge original provenance, practical
contribution and verifiable evidence instead of imposing a conference requirement.
"""


POOL_LANGUAGE = """
The discovery pool is for a fast Chinese skim. Preserve the exact original title in
title, and provide a concise Chinese display_title. Write summary, topics,
discovery_reason and quality commentary in Simplified Chinese. Keep author names,
venue names, identifiers, source links and technical acronyms accurate. Explain the
problem, concrete contribution and possible connection in short plain language.
Separate source claims from conjectured usefulness. Keep unknown venue/author/rank
facts explicitly unverified; translation must not add research facts.
"""
