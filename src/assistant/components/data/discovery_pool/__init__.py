"""Maintain a broad discovery pool from public-source searches.

Input origin:
    Discovery supplies papers, findings, methods, tools and datasets with source
    links, topics and brief descriptions. Humans optionally mark preferences.
Output destination:
    The visible Discovery Pool database supports browsing; Recommender reads the
    same entries to prepare the smaller selected Research Feed edition.
Responsibility:
    Merge duplicate sources, preserve explicit feedback and bound recent cache
    records. Selection and preference changes do not create Workbench proposals.
"""
