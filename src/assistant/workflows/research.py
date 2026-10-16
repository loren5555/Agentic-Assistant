"""Checkpoint research discovery and publication independently from providers."""

import hashlib
import json
from pathlib import Path

from dbos import DBOS, DBOSConfiguredInstance

from assistant.schemas.recommendation import (
    CATEGORIES, PaperCandidate, PaperEvidence, Recommendation,
    RecommendationAssessment, RecommendationRun, ResearchInterest,
)
from assistant.services import Services
from assistant.workflows.index import WorkIndex
from providers.demo import DemoRecommender


def candidate_identity(candidate: PaperCandidate) -> str:
    """Normalize bibliographic identity for cross-day duplicate prevention.

    Args:
        candidate: Discovery metadata and optional DOI.

    Returns:
        Normalized DOI, or the provider identity when no DOI is available.
    """
    doi = candidate.doi.strip().lower()
    doi = doi.removeprefix("https://doi.org/").removeprefix("http://doi.org/")
    doi = doi.removeprefix("doi:").strip()
    identity = f"doi:{doi}" if doi else candidate.id
    return identity


@DBOS.dbos_class()
class ResearchWorkflows(DBOSConfiguredInstance):
    """Own daily evidence gates, publications, and Interested follow-ups.

    Attributes:
        services: Replaceable discovery, reading, assessment, and storage services.
        index: Application-owned mappings, not DBOS's system tables.
        directory: Local report directory.
        maxima: Upper bounds for each recommendation category.
        demo: Whether to prohibit production publication and use offline assessment.
    """

    def __init__(self, services: Services, index: WorkIndex, directory: Path,
                 maxima: dict[str, int]) -> None:
        """Bind capabilities without starting discovery or accessing Notion.

        Args:
            services: Lazy provider implementations.
            index: Local source/publication index.
            directory: Parent directory for readable run reports.
            maxima: Configurable daily upper bounds; unspecified categories use one.
        """
        super().__init__("research")
        self.services = services
        self.index = index
        self.directory = directory
        self.maxima = {category: 1 for category in CATEGORIES}
        self.maxima.update(maxima)
        self.demo = services.config.providers.discovery == "demo"

    @DBOS.step()
    def read_interests(self) -> list[ResearchInterest]:
        """Read current human priorities without modifying them.

        Returns:
            Read-only active priorities from the configured feed capability.
        """
        interests = self.services.feed.read_active_interests()
        return interests

    @DBOS.step()
    def discover(self, interests: list[ResearchInterest]) -> list[PaperCandidate]:
        """Checkpoint candidate search separately from subsequent evidence reads.

        Args:
            interests: Current human priorities.

        Returns:
            Provider-discovered candidates, without quality endorsement.
        """
        candidates = self.services.discovery.discover(interests)
        return candidates

    @DBOS.step()
    def read(self, candidate: PaperCandidate) -> PaperEvidence:
        """Checkpoint one primary-source retrieval.

        Args:
            candidate: Source identity to retrieve.

        Returns:
            Actual source content, completeness, and any known retrieval failure.
        """
        evidence = self.services.evidence.read(candidate)
        return evidence

    @DBOS.step()
    async def assess(self, candidate: PaperCandidate, evidence: PaperEvidence,
                     interests: list[ResearchInterest]) -> RecommendationAssessment:
        """Checkpoint a model response so publication retries do not reassess.

        Args:
            candidate: Bibliographic metadata.
            evidence: Material actually retrieved.
            interests: Read-only human priorities.

        Returns:
            Evidence-grounded decision with separate epistemic layers.
        """
        if self.demo or candidate.demo:
            assessor = DemoRecommender()
        else:
            assessor = self.services.recommender
        assessment = await assessor.assess(candidate, evidence, interests)
        return assessment

    @DBOS.step()
    def find_duplicate(self, candidate: PaperCandidate) -> str | None:
        """Check local publication state and targeted historical feed identities.

        Args:
            candidate: Candidate to test before evidence and model expense.

        Returns:
            Existing destination identity or None.
        """
        key = f"recommendation:{candidate_identity(candidate)}"
        previous = self.index.get(key)
        if previous is not None:
            return previous["page_id"]
        url = self.services.feed.find_existing(candidate)
        return url

    @DBOS.step()
    async def publish(self, recommendation: Recommendation, day: str,
                report: RecommendationRun) -> str:
        """Publish with a stable key and save the mapping only after readback.

        Args:
            recommendation: Real source passing all evidence and quota gates.
            day: Current recommendation day for a failure report.
            report: Current progress to preserve when publication fails.

        Returns:
            Verified feed URL.
        """
        identity = candidate_identity(recommendation.candidate)
        key = hashlib.sha256(f"research-feed:{identity}".encode()).hexdigest()
        try:
            url = self.services.feed.publish(recommendation, key)
        except Exception as error:
            report.pending_recovery[recommendation.candidate.id] = f"{type(error).__name__}: {error}"
            # Record failure inside the incomplete step: replay keeps the same step order.
            await self._record_report(day, report)
            raise
        self.index.save(f"recommendation:{identity}", key, DBOS.workflow_id, url, "Published")
        return url

    @DBOS.step()
    async def save_report(self, day: str, report: RecommendationRun) -> None:
        """Persist current report as a DBOS event and a readable local file.

        Args:
            day: Shanghai calendar day supplied by the caller.
            report: Current actual publication and exclusion outcomes.
        """
        await self._record_report(day, report)

    async def _record_report(self, day: str, report: RecommendationRun) -> None:
        """Write a report from a checkpoint or incomplete publication step.

        Args:
            day: Intended Shanghai date.
            report: Latest selection and publication state.
        """
        data = report.model_dump(mode="json")
        await DBOS.set_event_async("report", data)
        reports = self.directory / "recommendations"
        reports.mkdir(parents=True, exist_ok=True)
        # The digest avoids trusting date/job strings as arbitrary file paths.
        identity = hashlib.sha256(DBOS.workflow_id.encode()).hexdigest()
        path = reports / f"{identity}.json"
        payload = {"day": day, "workflow_id": DBOS.workflow_id, **data,
                   "publication_count": len(report.published), "short_term_interest_changes": []}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @DBOS.workflow()
    async def recommendations(self, day: str) -> RecommendationRun:
        """Run one day's bounded recommendations with resumable provider calls.

        Args:
            day: Shanghai date; callers use one deterministic workflow ID per day.

        Returns:
            Report of actual publications, failures, exclusions, and selected fixtures.
        """
        report = RecommendationRun(demo=self.demo)
        interests = [] if self.demo else self.read_interests()
        candidates = self.discover(interests)
        counts = {category: 0 for category in CATEGORIES}
        seen = set()

        for candidate in candidates:
            identity = candidate_identity(candidate)
            if identity in seen:
                report.rejected[candidate.id] = "Duplicate source identity in this run"
                continue
            seen.add(identity)
            if not self.demo and not candidate.demo and self.find_duplicate(candidate):
                report.rejected[candidate.id] = "Previously published recommendation"
                continue

            try:
                evidence = self.read(candidate)
            except Exception as error:
                # A failed individual source is recorded, not replaced by invented evidence.
                report.source_failures[candidate.id] = f"{type(error).__name__}: {error}"
                report.rejected[candidate.id] = "Primary evidence retrieval failed"
                continue
            if evidence.failure:
                report.source_failures[candidate.id] = evidence.failure
            if not evidence.primary_source or not evidence.text.strip():
                report.rejected[candidate.id] = "Accessible primary evidence required"
                continue

            assessment = await self.assess(candidate, evidence, interests)
            category = assessment.category
            if not assessment.qualified or category is None:
                report.rejected[candidate.id] = assessment.reason
                continue
            if category == "Mainline Deep Read" and not evidence.full_text:
                report.rejected[candidate.id] = "Mainline Deep Read requires complete primary text"
                continue
            if counts[category] >= self.maxima[category]:
                report.rejected[candidate.id] = f"Daily maximum reached for {category}"
                continue

            counts[category] += 1
            recommendation = Recommendation(candidate=candidate, evidence=evidence,
                                             assessment=assessment)
            report.selected.append(recommendation)
            if self.demo or candidate.demo:
                report.demo = True
                continue

            url = await self.publish(recommendation, day, report)
            report.published.append(url)

        await self.save_report(day, report)
        return report

    @DBOS.step()
    def list_interested(self) -> list[dict[str, str]]:
        """Read human feedback without changing it.

        Returns:
            Feed identities approved for one Inbox follow-up.
        """
        records = self.services.feed.list_interested()
        return records

    @DBOS.step()
    def create_follow_up(self, feed_page_id: str) -> str:
        """Publish one verified Inbox follow-up, never a Papers record.

        Args:
            feed_page_id: Interested recommendation identity.

        Returns:
            Verified Inbox URL, or empty string for withdrawn or previously handled feedback.
        """
        key = f"research-follow-up:{feed_page_id}"
        previous = self.index.get(key)
        if previous is not None:
            return ""
        url = self.services.feed.create_follow_up(feed_page_id)
        if url:
            self.index.save(key, feed_page_id, DBOS.workflow_id, url, "Handled")
        return url

    @DBOS.workflow()
    async def followups(self) -> list[str]:
        """Turn Interested reviews into Inbox entries with checkpointed writes.

        Returns:
            Verified newly handled Inbox links.
        """
        urls = []
        for record in self.list_interested():
            url = self.create_follow_up(record["id"])
            if url:
                urls.append(url)
        await DBOS.set_event_async("followups", urls)
        return urls
