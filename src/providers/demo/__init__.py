"""Offline fixtures, never production research sources."""

from providers.demo.discovery import DemoDiscovery, DemoEvidenceReader, DemoRecommender

Discovery = DemoDiscovery
EvidenceReader = DemoEvidenceReader
Recommender = DemoRecommender

__all__ = ["Discovery", "EvidenceReader", "Recommender", "DemoDiscovery", "DemoEvidenceReader", "DemoRecommender"]
