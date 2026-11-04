"""Discover and assess papers for autonomous daily recommendations.

Input origin:
    Active Research Interests and Interested Papers guide public-source discovery.
Output destination:
    Qualified real recommendations publish directly to Research Feed.
    Interested signals are independently read by FeedProcessor into shared intake.
Responsibility:
    Codex Discovery and EvidenceReader search and read public sources; the local
    Recommender assesses the supplied evidence. The workflow checkpoints each call,
    and ResearchFeed publishes selected reports without exposing storage as a task.
    Apply evidence gates and maxima without requiring Workbench approval for the
    daily feed. Demo selections never become real publications. Interest feedback
    does not itself authorize research tasks or modify source preferences.
"""
