"""Run recommend-papers: select new papers through explicit evidence gates.

Input origin:
    Manual/scheduled recommendations dispatch supplies the day. ResearchFeed
    reads active Notion Research Interests; discovery and evidence plugins
    supply candidate metadata and primary text; feed/local index supply duplicate
    history. Demo mode replaces live discovery/assessment with fixtures.

Output destination:
    Passing real recommendations go through ResearchFeed.publish to Notion
    Research Feed. RecommendationRun goes to DBOS and a local recommendations
    JSON report, then command output. Human Interested feedback later flows
    through reviews to Inbox, not directly to Papers.

Inputs:
    Asia/Shanghai day, configured category maxima, read-only active research
    interests, discovery candidates, and primary material actually retrieved.
    Services, local index, and report directory come from the runtime.

Outputs:
    RecommendationRun separating selections, real Feed publications, duplicates,
    rejections, source failures, and pending recovery. A readable local JSON report
    and DBOS event preserve the outcome independently of the command's display.

Workflow:
    Read interests -> discover -> deduplicate within/across runs -> retrieve
    evidence -> assess relevance/quality -> enforce evidence gates and maxima ->
    publish permitted recommendations -> save the report. Mainline Deep Read
    requires full text; claims, experimental support, and inference stay separate.

Participants and effects:
    Discovery service, evidence reader, assessment agent, Research Feed storage,
    and human reader. run recommend-papers and scheduled dispatch share the same
    per-day operation identity. Real mode may call models and publish Feed rows.

Boundaries:
    Maxima are caps, not quotas; zero publication is valid. Synthetic demo mode
    uses fixed assessment and prohibits real Feed writes. Interests and Human
    Feedback are not modified. Interested follow-up implementations are bound
    here for DBOS registration but live in reviews.py and run with reviews.
"""

from pathlib import Path
import hashlib
import json

from dbos import DBOS, DBOSConfiguredInstance

from assistant.components.recommendations.models import CATEGORIES, PaperCandidate, PaperEvidence, Recommendation, RecommendationAssessment, RecommendationRun, ResearchInterest
from assistant.runtime.index import WorkIndex
from assistant.runtime.services import Services
from assistant.workflows.tasks.process_workbench import list_interested, create_follow_up, process_followups
from logger import get_logger, trace_call


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


@DBOS.dbos_class("ResearchWorkflows")
class RecommendationWorkflows(DBOSConfiguredInstance):
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
        interests = [] if self.demo else self.read_interests()
        candidates = self.discover(interests)
        counts = {category: 0 for category in CATEGORIES}
        seen = set()

        for position, candidate in enumerate(candidates, start=1):
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
                    'Candidate rejected: reason=duplicate within run.',
                    extra={"details": {'id': candidate.id}},
                )
                continue
            seen.add(identity)
            if not self.demo and not candidate.demo and self.find_duplicate(candidate):
                report.rejected[candidate.id] = "Previously published recommendation"
                self.logger.info(
                    'Candidate rejected: reason=previously published.',
                    extra={"details": {'id': candidate.id}},
                )
                continue

            try:
                evidence = self.read(candidate)
            except Exception as error:
                self.logger.warning(
                    'Evidence retrieval failed: error_type=%s; continuing other candidates.',
                    type(error).__name__,
                    extra={"details": {'candidate': candidate.id}},
                )
                # A failed individual source is recorded, not replaced by invented evidence.
                report.source_failures[candidate.id] = f"{type(error).__name__}: {error}"
                report.rejected[candidate.id] = "Primary evidence retrieval failed"
                continue
            if evidence.failure:
                self.logger.warning(
                    'Evidence source reported a failure.',
                    extra={"details": {'candidate': candidate.id, 'detail': evidence.failure[:240]}},
                )
                report.source_failures[candidate.id] = evidence.failure
            if not evidence.primary_source or not evidence.text.strip():
                report.rejected[candidate.id] = "Accessible primary evidence required"
                self.logger.info(
                    'Candidate rejected: reason=accessible primary evidence required.',
                    extra={"details": {'id': candidate.id}},
                )
                continue

            assessment = await self.assess(candidate, evidence, interests)
            category = assessment.category
            if not assessment.qualified or category is None:
                report.rejected[candidate.id] = assessment.reason
                self.logger.info(
                    'Candidate rejected by assessment: reason=%s.',
                    assessment.reason[:240],
                    extra={"details": {'id': candidate.id}},
                )
                continue
            if category == "Mainline Deep Read" and not evidence.full_text:
                report.rejected[candidate.id] = "Mainline Deep Read requires complete primary text"
                self.logger.info(
                    'Candidate rejected: reason=full text required for deep read.',
                    extra={"details": {'id': candidate.id}},
                )
                continue
            if counts[category] >= self.maxima[category]:
                report.rejected[candidate.id] = f"Daily maximum reached for {category}"
                self.logger.info(
                    'Candidate rejected: reason=daily maximum reached category=%s.',
                    category,
                    extra={"details": {'id': candidate.id}},
                )
                continue

            counts[category] += 1
            recommendation = Recommendation(candidate=candidate, evidence=evidence,
                                             assessment=assessment)
            report.selected.append(recommendation)
            self.logger.info(
                'Candidate selected: category=%s count=%d maximum=%d.',
                category,
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

        await self.save_report(day, report)
        self.logger.info("Recommendation run completed: candidates=%d selected=%d published=%d rejected=%d source_failures=%d.",
                         len(candidates), len(report.selected), len(report.published), len(report.rejected), len(report.source_failures))
        return report

    @DBOS.step(name="ResearchWorkflows.read_interests")
    @trace_call("step", "read_interests")
    def read_interests(self) -> list[ResearchInterest]:
        """Read current human priorities without modifying them.

        Returns:
            Read-only active priorities from the configured feed capability.
        """
        self.logger.info("Reading active research interests without changing priorities.")
        interests = self.services.feed.read_active_interests()
        self.logger.info("Read %d active research interests.", len(interests))
        return interests

    @DBOS.step(name="ResearchWorkflows.discover")
    @trace_call("step", "discover")
    def discover(self, interests: list[ResearchInterest]) -> list[PaperCandidate]:
        """Checkpoint candidate search separately from subsequent evidence reads.

        Args:
            interests: Current human priorities.

        Returns:
            Provider-discovered candidates, without quality endorsement.
        """
        self.logger.info("Discovering research candidates: interests=%d demo=%s.", len(interests), self.demo)
        candidates = self.services.discovery.discover(interests)
        self.logger.info("Discovery completed: candidates=%d.", len(candidates))
        return candidates

    @DBOS.step(name="ResearchWorkflows.read")
    @trace_call("step", "read")
    def read(self, candidate: PaperCandidate) -> PaperEvidence:
        """Checkpoint one primary-source retrieval.

        Args:
            candidate: Source identity to retrieve.

        Returns:
            Actual source content, completeness, and any known retrieval failure.
        """
        self.logger.info(
            'Reading candidate evidence: demo=%s.',
            candidate.demo,
            extra={"details": {'candidate': candidate.id}},
        )
        evidence = self.services.evidence.read(candidate)
        self.logger.info(
            'Evidence read: primary=%s full_text=%s characters=%d retrieval_failure=%s.',
            evidence.primary_source,
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
            'Assessing candidate: mode=%s.',
            'fixed demo assessment' if self.demo or candidate.demo else 'configured model',
            extra={"details": {'candidate': candidate.id}},
        )
        assessment = await assessor.assess(candidate, evidence, interests)
        self.logger.info(
            'Assessment completed: qualified=%s category=%s.',
            assessment.qualified,
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
            'Publishing real recommendation: category=%s.',
            recommendation.assessment.category,
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
    list_interested = list_interested
    create_follow_up = create_follow_up
    process_followups = process_followups
