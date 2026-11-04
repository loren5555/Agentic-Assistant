"""Normalize paper identities shared by discovery, deduplication and publication."""

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from assistant.components.recommendations.models import PaperCandidate


def candidate_identity(candidate: PaperCandidate) -> str:
    """Use a DOI, version-independent arXiv ID, or canonical source URL.

    Args:
        candidate: Bibliographic metadata from discovery.

    Returns:
        Stable identity shared by the local index and Research Feed.
    """
    doi = candidate.doi.strip().lower()
    doi = doi.removeprefix("https://doi.org/").removeprefix("http://doi.org/")
    doi = doi.removeprefix("doi:").strip()
    parts = urlsplit(candidate.url)
    if not doi and parts.hostname in {"doi.org", "dx.doi.org"}:
        doi = parts.path.lstrip("/").lower()
    if doi:
        return f"doi:{doi}"
    if candidate.demo or parts.scheme not in {"http", "https"}:
        return candidate.id
    if parts.hostname in {"arxiv.org", "www.arxiv.org", "export.arxiv.org"}:
        identifier = re.sub(r"^/(abs|pdf|html)/", "", parts.path).removesuffix(".pdf")
        identifier = re.sub(r"v\d+$", "", identifier)
        return f"arxiv:{identifier}"
    query = urlencode(sorted(
        (key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in {"ref", "source"}
    ))
    canonical = urlunsplit(("https", parts.netloc.lower(), parts.path.rstrip("/"), query, ""))
    return f"url:{canonical}"
