"""Discover and publish daily recommendations independently of Workbench.

Input origin:
    Initial recommendation topics, optional preference feedback, fresh searches
    and the accumulated Discovery Pool; no approved research direction is required.
Output destination:
    Qualified real recommendations go directly to Research Feed and a local report.
    Optional likes personalize discovery; explicit Follow Up requests enter task intake.
Responsibility:
    Refresh a broad visible pool, rank its metadata, inspect promising sources
    and publish a small edition with long-term cross-disciplinary exploration. Zero publication
    is valid. Demo fixtures skip live interest reads, model assessment and Feed writes.
    Provider internals may use multiple evidence steps without exposing that detail
    in the business diagram.
"""

from collections import Counter
from datetime import date, timedelta
from pathlib import Path
import hashlib
import json

from dbos import DBOS, DBOSConfiguredInstance

from assistant.components.recommendations.discovery.identity import candidate_identity
from assistant.components.recommendations.recommender.policy import exploration_order
from assistant.components.data.discovery_pool.models import DiscoveryEntry
from assistant.components.recommendations.recommender.models import CATEGORIES, Recommendation, RecommendationAssessment, RecommendationRun
from assistant.components.recommendations.discovery.models import DiscoveryResult, PaperCandidate, ResearchInterest
from assistant.components.recommendations.evidence_reader.models import PaperEvidence
from assistant.runtime.index import WorkIndex
from assistant.runtime.services import Services
from logger import get_logger, trace_call


@DBOS.dbos_class("ResearchWorkflows")
class RecommendationWorkflows(DBOSConfiguredInstance):
    """Own autonomous daily evidence gates and recommendation publications.

    Attributes:
        services: Replaceable discovery, reading, assessment, and storage services.
        index: Application-owned mappings, not DBOS's system tables.
        directory: Local report directory.
        maxima: Upper bounds for each recommendation category.
        demo: Whether to prohibit production publication and use offline assessment.
        recent_days: Publication window required for Frontier Radar selections.
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
        self.settings = services.config.runtime.recommendations
        self.maxima = {category: self.settings.selected_count for category in CATEGORIES}
        self.maxima.update(maxima)
        self.demo = services.config.providers.discovery == "demo"
        options = services.config.provider_options.get(services.config.providers.discovery, {})
        self.recent_days = int(options.get("discovery_recent_days", 7))
        self.logger = get_logger("workflows.tasks.recommend_papers")

    @DBOS.workflow(name="ResearchWorkflows.recommendations")
    @trace_call("workflow", "recommend_papers")
    async def recommend_papers(self, day: str) -> RecommendationRun:
        """Run one day's bounded recommendations with resumable provider calls.

        Args:
            day: Shanghai date; callers use one deterministic workflow ID per day.

        Returns:
            Report of actual publications, failures, exclusions, and selected fixtures.
        """
        report = RecommendationRun(demo=self.demo)
        self.logger.info(
            'Recommendation run started: day=%s demo=%s maxima=%s.',
            day,
            self.demo,
            self.maxima,
            extra={"details": {'workflow': DBOS.workflow_id}},
        )
        if self.demo:
            self.logger.info("Offline demo: real interest reads, model assessment, and Feed publication are disabled.")
        interests = [] if self.demo else self.read_preferences()
        discovery_error = None
        try:
            discovery = await self.discover(interests, day)
        except Exception as error:
            report.source_failures["discovery"] = f"{type(error).__name__}: {error}"
            if getattr(error, "process", None) is not None:
                report.failed_processes["discovery"] = error.process
            if self.demo:
                raise
            discovery_error = error
            discovery = DiscoveryResult(candidates=[], notes=["Search failed; selecting from the existing discovery cache"])
            self.logger.warning("Search unavailable; trying the accumulated Discovery Pool.")
        report.discovery = discovery
        entries = [] if self.demo else self.refresh_pool(discovery.candidates, day)
        report.pool_count = len(entries)
        if discovery_error is not None and not entries:
            await self._record_report(day, report, record_event=False)
            raise discovery_error
        candidates = discovery.candidates if self.demo else [
            entry.candidate for entry in entries
            if not entry.selected and entry.feedback != "Not Interested"
        ]
        if candidates and not self.demo:
            candidates = await self.rank(candidates, interests, day)
        counts = {category: 0 for category in CATEGORIES}
        seen = set()

        for position, candidate in enumerate(candidates, start=1):
            if len(report.selected) >= self.settings.selected_count:
                break
            self.logger.info(
                'Recommendation candidate %d/%d: title=%r.',
                position,
                len(candidates),
                candidate.title[:120],
                extra={"details": {'id': candidate.id}},
            )
            identity = candidate_identity(candidate)
            if identity in seen:
                report.rejected[candidate.id] = "Duplicate source identity in this run"
                self.logger.info(
                    'Candidate rejected: title=%r reason=duplicate within run.',
                    candidate.title,
                    extra={"details": {'id': candidate.id}},
                )
                continue
            seen.add(identity)
            if not self.demo and not candidate.demo and self.find_duplicate(candidate):
                report.rejected[candidate.id] = "Previously published recommendation"
                self.logger.info(
                    'Candidate rejected: title=%r reason=previously published.',
                    candidate.title,
                    extra={"details": {'id': candidate.id}},
                )
                continue

            try:
                evidence = await self.read(candidate)
            except Exception as error:
                self.logger.warning(
                    'Evidence retrieval failed: title=%r error_type=%s; continuing other candidates.',
                    candidate.title, type(error).__name__,
                    extra={"details": {'candidate': candidate.id}},
                )
                # A failed individual source is recorded, not replaced by invented evidence.
                report.source_failures[candidate.id] = f"{type(error).__name__}: {error}"
                if getattr(error, "process", None) is not None:
                    report.failed_processes[candidate.id] = error.process
                report.rejected[candidate.id] = "Primary evidence retrieval failed"
                continue
            report.evidence[candidate.id] = evidence
            if evidence.failure:
                self.logger.warning(
                    'Evidence source reported a failure: title=%r reason=%s.',
                    candidate.title, evidence.failure[:180],
                    extra={"details": {'candidate': candidate.id, 'detail': evidence.failure[:240]}},
                )
                report.source_failures[candidate.id] = evidence.failure
            if not evidence.primary_source or not evidence.text.strip():
                report.rejected[candidate.id] = "Accessible primary evidence required"
                self.logger.info(
                    'Candidate rejected: title=%r reason=accessible primary evidence required.',
                    candidate.title,
                    extra={"details": {'id': candidate.id}},
                )
                continue

            try:
                assessment_context = [*interests, ResearchInterest(
                    id="edition-policy", title="Edition date and evidence scope",
                    description=f"Recommendation date: {day}. Frontier Radar needs a publication within the previous {self.recent_days} days. Older useful work can be Understanding Daily. Abstract-level evidence is sufficient for a qualified reading lead, but never for Mainline Deep Read.",
                )]
                assessment = await self.assess(candidate, evidence, assessment_context)
            except Exception as error:
                report.pending_recovery[candidate.id] = f"Assessment failed: {type(error).__name__}: {error}"
                await self._record_report(day, report, record_event=False)
                raise
            category = assessment.category
            if not assessment.qualified or category is None:
                report.rejected[candidate.id] = assessment.reason
                self.logger.info(
                    'Candidate rejected by assessment: title=%r reason=%s.',
                    candidate.title, assessment.reason[:240],
                    extra={"details": {'id': candidate.id}},
                )
                continue
            if category == "Frontier Radar":
                try:
                    published = date.fromisoformat(candidate.published_date)
                except ValueError:
                    published = None
                end = date.fromisoformat(day)
                start = end - timedelta(days=self.recent_days - 1)
                if published is None or not start <= published <= end:
                    report.rejected[candidate.id] = "Frontier Radar requires a verified date within the recent search window"
                    self.logger.info("Candidate rejected: title=%r reason=recent publication date required.", candidate.title)
                    continue
            if category == "Mainline Deep Read" and not evidence.full_text:
                report.rejected[candidate.id] = "Mainline Deep Read requires complete primary text"
                self.logger.info(
                    'Candidate rejected: title=%r reason=full text required for deep read.',
                    candidate.title,
                    extra={"details": {'id': candidate.id}},
                )
                continue
            if counts[category] >= self.maxima[category]:
                report.rejected[candidate.id] = f"Daily maximum reached for {category}"
                self.logger.info(
                    'Candidate rejected: title=%r reason=daily maximum reached category=%s.',
                    candidate.title, category,
                    extra={"details": {'id': candidate.id}},
                )
                continue

            counts[category] += 1
            recommendation = Recommendation(candidate=candidate, evidence=evidence,
                                             assessment=assessment, day=day)
            report.selected.append(recommendation)
            self.logger.info(
                'Candidate selected: title=%r category=%s count=%d maximum=%d.',
                candidate.title, category,
                counts[category],
                self.maxima[category],
                extra={"details": {'id': candidate.id}},
            )
            if self.demo or candidate.demo:
                report.demo = True
                self.logger.info(
                    'Synthetic recommendation retained locally only; no Feed write.',
                    extra={"details": {'candidate': candidate.id}},
                )
                continue

            url = await self.publish(recommendation, day, report)
            report.published.append(url)
            if not self.demo:
                entry = next(entry for entry in entries if candidate_identity(entry.candidate) == candidate_identity(candidate))
                self.mark_selected(entry)

        await self.save_report(day, report)
        self.logger.info("Recommendation run completed: candidates=%d selected=%d published=%d rejected=%d source_failures=%d.",
                         len(candidates), len(report.selected), len(report.published), len(report.rejected), len(report.source_failures))
        return report

    @DBOS.step(name="ResearchWorkflows.read_preferences")
    @trace_call("step", "read_preferences")
    def read_preferences(self) -> list[ResearchInterest]:
        """Combine initial newspaper topics with automatically learned preferences.

        Returns:
            Weighted recommendation context, independent of approved research work.
        """
        self.logger.info("Reading newspaper topics and optional preference feedback.")
        topic_file = self.directory / "recommendation-topics.json"
        topics = json.loads(topic_file.read_text()) if topic_file.exists() else self.settings.topics
        interests = [ResearchInterest(id=f"initial:{topic}", title=topic,
                     description="User-selected initial topic; retain broad exploration.") for topic in topics]
        feedback = self.services.discovery_pool.read_feedback()
        topics = Counter(topic for entry in feedback if entry.feedback == "Interested"
                         for topic in entry.candidate.topics)
        interests.extend(ResearchInterest(id=f"learned:{topic}", title=topic,
                         description=f"Positive preference learned from {count} explicitly liked discoveries.", priority=min(5.0, 1.0 + count))
                         for topic, count in topics.most_common(20))
        interests.extend(ResearchInterest(id=f"avoid:{entry.candidate.id}", title=entry.candidate.title,
                         description="Explicitly disliked item; do not infer dislike of the whole discipline.")
                         for entry in feedback if entry.feedback == "Not Interested")
        interests.extend(self.services.feed.read_interested_papers())
        interests.extend(self.services.feed.read_interested_feed())
        self.logger.info("Recommendation preference context ready: entries=%d.", len(interests))
        return interests

    @DBOS.step(name="ResearchWorkflows.refresh_pool")
    @trace_call("step", "refresh_pool")
    def refresh_pool(self, candidates: list[PaperCandidate], day: str) -> list[DiscoveryEntry]:
        """Merge lightweight search results into the visible discovery cache."""
        return self.services.discovery_pool.refresh(candidates, day, self.settings.pool_size)

    @DBOS.step(name="ResearchWorkflows.rank")
    @trace_call("step", "select_from_pool")
    async def rank(self, candidates: list[PaperCandidate], interests: list[ResearchInterest], day: str) -> list[PaperCandidate]:
        """Rank metadata once, then balance actual long-term editorial coverage."""
        ids = await self.services.recommender.rank(candidates, interests)
        known = {candidate.id: candidate for candidate in candidates}
        ordered = []
        for identity in ids:
            if identity in known:
                ordered.append(known.pop(identity))
        ordered.extend(known.values())
        counts = self.index.recommendation_counts()
        balanced = exploration_order(ordered, counts, self.settings.exploration, day)
        self.logger.info("Pool shortlist prepared: available=%d reading_budget=%d selected_limit=%d.",
                         len(candidates), self.settings.reading_budget, self.settings.selected_count)
        return balanced[:self.settings.reading_budget]

    @DBOS.step(name="ResearchWorkflows.mark_selected")
    @trace_call("step", "mark_selected")
    def mark_selected(self, entry: DiscoveryEntry) -> None:
        """Mark a pool entry only after confirmed Feed publication."""
        self.services.discovery_pool.mark_selected(entry)

    @DBOS.step(name="ResearchWorkflows.discover")
    @trace_call("step", "discover")
    async def discover(self, interests: list[ResearchInterest], day: str) -> DiscoveryResult:
        """Checkpoint candidate search separately from subsequent evidence reads.

        Args:
            interests: Current human priorities.
            day: Intended recommendation date, included in the search context.

        Returns:
            Provider-discovered candidates, without quality endorsement.
        """
        self.logger.info("Discovering research candidates: interests=%d demo=%s.", len(interests), self.demo)
        result = await self.services.discovery.discover(interests, day)
        self.logger.info("Discovery completed: candidates=%d.", len(result.candidates))
        return result

    @DBOS.step(name="ResearchWorkflows.read")
    @trace_call("step", "read")
    async def read(self, candidate: PaperCandidate) -> PaperEvidence:
        """Checkpoint one primary-source retrieval.

        Args:
            candidate: Source identity to retrieve.

        Returns:
            Actual source content, completeness, and any known retrieval failure.
        """
        self.logger.info(
            'Reading candidate evidence: title=%r demo=%s.',
            candidate.title, candidate.demo,
            extra={"details": {'candidate': candidate.id}},
        )
        evidence = await self.services.evidence.read(candidate)
        self.logger.info(
            'Evidence read: title=%r primary=%s full_text=%s characters=%d retrieval_failure=%s.',
            candidate.title, evidence.primary_source,
            evidence.full_text,
            len(evidence.text),
            bool(evidence.failure),
            extra={"details": {'candidate': candidate.id}},
        )
        return evidence

    @DBOS.step(name="ResearchWorkflows.assess")
    @trace_call("step", "assess")
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
        assessor = self.services.fixture_recommender if self.demo or candidate.demo else self.services.recommender
        self.logger.info(
            'Assessing candidate: title=%r mode=%s.',
            candidate.title, 'fixed demo assessment' if self.demo or candidate.demo else 'configured model',
            extra={"details": {'candidate': candidate.id}},
        )
        assessment = await assessor.assess(candidate, evidence, interests)
        self.logger.info(
            'Assessment completed: title=%r qualified=%s category=%s.',
            candidate.title, assessment.qualified,
            assessment.category,
            extra={"details": {'candidate': candidate.id}},
        )
        return assessment

    @DBOS.step(name="ResearchWorkflows.find_duplicate")
    @trace_call("step", "find_duplicate")
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
            self.logger.info(
                'Previously published candidate found in local index.',
                extra={"details": {'candidate': candidate.id}},
            )
            return previous["page_id"]
        url = self.services.feed.find_existing(candidate)
        self.logger.info(
            'Historical Feed lookup completed: duplicate=%s.',
            url is not None,
            extra={"details": {'candidate': candidate.id}},
        )
        return url

    @DBOS.step(name="ResearchWorkflows.publish")
    @trace_call("step", "publish")
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
        self.logger.info(
            'Publishing real recommendation: title=%r category=%s.',
            recommendation.candidate.title, recommendation.assessment.category,
            extra={"details": {'candidate': recommendation.candidate.id}},
        )
        try:
            url = self.services.feed.publish(recommendation, key)
        except Exception as error:
            self.logger.exception(
                'Recommendation publication failed; preserving recovery report.',
                extra={"details": {'candidate': recommendation.candidate.id, 'workflow': DBOS.workflow_id}},
            )
            report.pending_recovery[recommendation.candidate.id] = f"{type(error).__name__}: {error}"
            # Record failure inside the incomplete step: replay keeps the same step order.
            await self._record_report(day, report)
            raise
        self.index.save(f"recommendation:{identity}", key, DBOS.workflow_id, url, "Published")
        self.index.record_recommendation(identity, recommendation.candidate.breadth, day)
        self.logger.info(
            'Recommendation publication verified.',
            extra={"details": {'candidate': recommendation.candidate.id, 'url': url}},
        )
        return url

    @DBOS.step(name="ResearchWorkflows.save_report")
    @trace_call("step", "save_report")
    async def save_report(self, day: str, report: RecommendationRun) -> None:
        """Persist current report as a DBOS event and a readable local file.

        Args:
            day: Shanghai calendar day supplied by the caller.
            report: Current actual publication and exclusion outcomes.
        """
        await self._record_report(day, report)

    async def _record_report(self, day: str, report: RecommendationRun, *, record_event: bool = True) -> None:
        """Write a report from a checkpoint or incomplete publication step.

        Args:
            day: Intended Shanghai date.
            report: Latest selection and publication state.
            record_event: Record a DBOS event inside a step; workflow-level failure
                reports write only the file so retry does not shift step numbers.
        """
        data = report.model_dump(mode="json")
        if record_event:
            await DBOS.set_event_async("report", data)
        reports = self.directory / "recommendations"
        reports.mkdir(parents=True, exist_ok=True)
        # The digest avoids trusting date/job strings as arbitrary file paths.
        identity = hashlib.sha256(DBOS.workflow_id.encode()).hexdigest()
        path = reports / f"{identity}.json"
        payload = {"day": day, "workflow_id": DBOS.workflow_id, **data,
                   "publication_count": len(report.published), "short_term_interest_changes": []}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.logger.info(
            'Recommendation report saved: published=%d rejected=%d source_failures=%d pending_recovery=%d.',
            len(report.published),
            len(report.rejected),
            len(report.source_failures),
            len(report.pending_recovery),
            extra={"details": {'path': path}},
        )


    # Persisted feedback workflows retain their registration while their business
    # implementation lives beside the review process that invokes them.
