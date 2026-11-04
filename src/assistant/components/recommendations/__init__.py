"""Discover and assess papers for autonomous daily recommendations.

Input origin:
    Active Research Interests and external discovery/evidence services.
Output destination:
    Qualified real recommendations publish directly to Research Feed.
    Interested signals are independently read by FeedProcessor into shared intake.
Responsibility:
    Apply evidence gates and maxima without requiring Workbench approval for the
    daily feed. Demo selections never become real publications. Interest feedback
    does not itself authorize research tasks or modify source preferences.
"""
