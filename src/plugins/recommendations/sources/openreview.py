"""Query OpenReview API v2 for public papers and attributed public discussions.

Input origin: concrete Collector queries, venue IDs and forum IDs.
Output destination: canonical paper candidates or separately labeled review notes.
Only notes explicitly readable by everyone are returned, including when the host
account can access private submissions. API credentials never enter model prompts.
"""

from collections.abc import Mapping
from datetime import datetime, timezone
import asyncio
import os

import httpx
from pydantic import BaseModel, ConfigDict, Field

from assistant.components.recommendations.collector.models import SearchDirection
from assistant.components.recommendations.collector.policy import age_bounds
from assistant.components.recommendations.discovery.models import (
    PaperCandidate,
    SourceQuality,
)
from assistant.components.recommendations.evidence_reader.models import (
    PaperEvidence,
    ReviewDiscussion,
)
from logger import get_logger, trace_call


class OpenReviewHTTPError(RuntimeError):
    """Keep the HTTP status available for explicit legacy-note lookup."""

    def __init__(self, status: int) -> None:
        """Describe a source error without exposing credentials or response bodies."""
        self.status = status
        super().__init__(
            f"OpenReview query returned HTTP {status}; account permissions or rate limits may apply"
        )


class OpenReviewSettings(BaseModel):
    """Bound API traffic and select explicit public venue scopes."""

    model_config = ConfigDict(extra="forbid")
    venues: list[str] = Field(default_factory=list, max_length=20)
    page_size: int = Field(default=50, ge=1, le=100)
    max_pages: int = Field(default=3, ge=1, le=10)
    max_discussions: int = Field(default=40, ge=1, le=200)
    timeout_seconds: float = Field(default=30, gt=0)
    interval_seconds: float = Field(default=1, ge=0)
    username_env: str = "OPENREVIEW_USERNAME"
    password_env: str = "OPENREVIEW_PASSWORD"


def public(note: dict) -> bool:
    """Accept only explicitly public notes, independently of account privileges."""
    return "everyone" in note.get("readers", [])


def content(note: dict) -> dict:
    """Unwrap API v2 values without assuming one conference's review form."""
    return {
        key: value.get("value") if isinstance(value, dict) else value
        for key, value in note.get("content", {}).items()
    }


def timestamp(value) -> str:
    """Convert a known API millisecond timestamp without inventing missing dates."""
    return (
        datetime.fromtimestamp(value / 1000, timezone.utc).isoformat() if value else ""
    )


def candidate_from_note(
    note: dict, direction: SearchDirection
) -> PaperCandidate | None:
    """Translate one public submission, preserving exact source metadata."""
    item = content(note)
    if not public(note) or not item.get("title") or not item.get("abstract"):
        return None
    forum = note.get("forum") or note["id"]
    url = f"https://openreview.net/forum?id={forum}"
    venue = str(item.get("venue", ""))
    # A submission's target conference alone is not proof of acceptance.
    accepted = (
        bool(item.get("venueid"))
        and "submission" not in str(item["venueid"]).lower()
        and "reject" not in str(item["venueid"]).lower()
        and "withdraw" not in str(item["venueid"]).lower()
    )
    authors = []
    for author in item.get("authors") or []:
        name = author.get("fullname") if isinstance(author, dict) else author
        if isinstance(name, str) and name.strip():
            authors.append(name.strip())
    published = timestamp(note.get("odate") or note.get("cdate"))[:10]
    return PaperCandidate(
        id=f"openreview:{forum}",
        title=str(item["title"]),
        url=url,
        doi=str(item.get("doi") or ""),
        published_date=published,
        summary=str(item["abstract"]),
        topics=list(item.get("keywords") or []),
        breadth=direction.breadth,
        discovery_reason=direction.reason or direction.query,
        discovery_sources=["openreview"],
        openreview_forum=forum,
        quality=SourceQuality(
            venue=venue,
            status="Accepted" if accepted else "Unknown",
            authors=authors,
            sources=[url],
        ),
    )


class OpenReviewSource:
    """Own bounded API requests, optional login and public-data normalization."""

    def __init__(self, options: Mapping[str, object]) -> None:
        """Validate source settings without making requests."""
        self.settings = OpenReviewSettings.model_validate(options)
        self.logger = get_logger("plugins.recommendations.sources.openreview")

    async def _login(self, client: httpx.AsyncClient) -> None:
        """Use host environment credentials when configured; allow public access otherwise."""
        username = os.getenv(self.settings.username_env)
        password = os.getenv(self.settings.password_env)
        if bool(username) != bool(password):
            raise ValueError(
                "Configure both OpenReview username and password environment variables"
            )
        if username:
            response = await client.post(
                "/login", json={"id": username, "password": password}
            )
            if response.is_error:
                raise RuntimeError(
                    f"OpenReview login returned HTTP {response.status_code}"
                )
            token = response.json().get("token")
            if token:
                client.headers["Authorization"] = f"Bearer {token}"

    async def _pages(
        self, path: str, params: dict, *, version: int = 2
    ) -> tuple[list[dict], bool]:
        """Paginate within the configured budget and honor bounded 429 retries."""
        base_url = (
            "https://api2.openreview.net"
            if version == 2
            else "https://api.openreview.net"
        )
        async with httpx.AsyncClient(
            base_url=base_url, timeout=self.settings.timeout_seconds
        ) as client:
            await self._login(client)
            rows = []
            for page in range(self.settings.max_pages):
                await asyncio.sleep(self.settings.interval_seconds)
                arguments = {
                    **params,
                    "limit": self.settings.page_size,
                    "offset": page * self.settings.page_size,
                }
                response = await client.get(path, params=arguments)
                if response.status_code == 429:
                    try:
                        pause = min(
                            30, max(1, float(response.headers.get("Retry-After", "2")))
                        )
                    except ValueError:
                        pause = 2
                    await asyncio.sleep(pause)
                    response = await client.get(path, params=arguments)
                if response.is_error:
                    self.logger.warning(
                        "OpenReview request failed: HTTP %d. Check account access or source rate limits.",
                        response.status_code,
                        extra={"details": {"endpoint": path}},
                    )
                    raise OpenReviewHTTPError(response.status_code)
                document = response.json()
                batch = document.get("notes", [])
                rows.extend(batch)
                total = document.get("count")
                if (
                    not batch
                    or len(batch) < self.settings.page_size
                    or (total is not None and len(rows) >= total)
                ):
                    return rows, False
            return rows, True

    @trace_call("tool", "openreview.search")
    async def search(
        self, direction: SearchDirection, day: str, limit: int
    ) -> tuple[list[PaperCandidate], list[str]]:
        """Retrieve public, relevant submissions in an explicit publication interval."""
        self.logger.info(
            "kind=script provider=openreview Search started: query=%r breadth=%s age=%s.",
            direction.query,
            direction.breadth,
            direction.age,
        )
        start, end = age_bounds(day, direction.age)
        params = {
            "term": direction.query,
            "type": "terms",
            "content": "all",
            "sort": "cdate:asc" if direction.age == "older" else "cdate:desc",
        }
        notes, truncated = await self._pages("/notes/search", params)
        results = []
        for note in notes:
            item = candidate_from_note(note, direction)
            fields = content(note)
            if item is None or not start <= item.published_date <= end:
                continue
            if (
                self.settings.venues
                and fields.get("venueid") not in self.settings.venues
                and not any(
                    str(invitation).startswith(venue + "/")
                    for venue in self.settings.venues
                    for invitation in note.get("invitations", [])
                )
            ):
                continue
            results.append(item)
            if len(results) >= limit:
                break
        limitations = (
            [
                "OpenReview search pagination budget reached; date filtering is local and coverage is partial"
            ]
            if truncated
            else []
        )
        self.logger.info(
            "kind=script provider=openreview Search completed: examined=%d candidates=%d partial=%s.",
            len(notes),
            len(results),
            truncated,
        )
        return results, limitations

    @trace_call("tool", "openreview.discussion")
    async def read(self, forum: str) -> PaperEvidence:
        """Read public abstract and thread notes without claiming paper full text."""
        self.logger.info(
            "kind=script provider=openreview Discussion read started.",
            extra={"details": {"forum": forum}},
        )
        version = 2
        try:
            rows, _ = await self._pages("/notes", {"id": forum})
        except OpenReviewHTTPError as error:
            if error.status != 404:
                raise
            rows = []
        if not rows:
            version = 1
            self.logger.debug("Looking up an older forum through OpenReview API v1.")
            rows, _ = await self._pages("/notes", {"id": forum}, version=version)
        submission = next(
            (row for row in rows if row["id"] == forum and public(row)), None
        )
        if submission is None:
            raise ValueError(
                "OpenReview submission is unavailable or not explicitly public"
            )
        rows, truncated = await self._pages(
            "/notes", {"forum": forum, "sort": "cdate:asc"}, version=version
        )
        discussions = []
        for note in rows:
            if note["id"] == forum or not public(note):
                continue
            invitations = " ".join(
                note.get("invitations", []) or [note.get("invitation", "")]
            )
            role = next(
                (
                    role
                    for role in (
                        "Official_Review",
                        "Meta_Review",
                        "Decision",
                        "Rebuttal",
                        "Official_Comment",
                    )
                    if role in invitations
                ),
                "Public_Comment",
            )
            if "Rebuttal" not in invitations and any(
                "Authors" in signature for signature in note.get("signatures", [])
            ):
                role = "Author_Response"
            discussions.append(
                ReviewDiscussion(
                    id=note["id"],
                    role=role,
                    reply_to=note.get("replyto") or "",
                    url=f"https://openreview.net/forum?id={forum}&noteId={note['id']}",
                    modified=timestamp(note.get("tmdate") or note.get("mdate")),
                    content={key: str(value) for key, value in content(note).items()},
                )
            )
        limited = truncated or len(discussions) > self.settings.max_discussions
        discussions = discussions[: self.settings.max_discussions]
        item = content(submission)
        limitations = (
            [
                "Public discussion snapshot is partial because its retrieval budget was reached"
            ]
            if limited
            else []
        )
        self.logger.info(
            "kind=script provider=openreview Discussion read completed: public_notes=%d partial=%s.",
            len(discussions),
            limited,
        )
        return PaperEvidence(
            primary_source=True,
            full_text=False,
            text=str(item.get("abstract") or ""),
            source_url=f"https://openreview.net/forum?id={forum}",
            reading_scope="original abstract and public review thread; PDF not read",
            discussions=discussions,
            discussion_limitations=limitations,
            limitations=[
                "The original paper PDF has not been retrieved by this API tool"
            ],
        )
