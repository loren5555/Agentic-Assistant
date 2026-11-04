"""Implement public discovery, preference reads, selection and Feed publication.

Input origin:
    Setup topics and explicit likes provide newspaper preferences. Codex discovers
    public papers, findings, methods, tools and datasets for the discovery cache.
Output destination:
    Local ranking and assessment prepare selected recommendations; the Notion Feed
    service publishes them. A separate DiscoveryPool component owns cache storage.
Responsibility:
    Keep public source work, editorial judgment and storage independently selectable.
    Preference feedback creates no proposal work; explicit Follow Up does.
"""
