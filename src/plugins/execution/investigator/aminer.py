"""Submit an approved scholarly question to AMiner and return its attributed report."""

from assistant.components.execution.investigator.models import InvestigationReport, InvestigationRequest, SourceEvidence
from assistant.runtime.records import ExecutionProcess
from logger import get_logger, trace_call
from plugins._shared import aminer

logger = get_logger("plugins.execution.investigator.aminer")


class Investigator:
    """Return the hosted report and its reference list to the approved task."""

    def __init__(self, options=None):
        self.api_key = aminer.configured_key(options or {})
        self.timeout = float((options or {}).get("timeout_seconds", 600))

    @trace_call("component", "investigator.investigate")
    async def investigate(self, request: InvestigationRequest) -> InvestigationReport:
        logger.info("kind=agent provider=aminer Deep research started: question=%r.", request.question[:160])
        message = "\n\n".join(part for part in [request.question, *request.context] if part)
        try:
            data = await aminer.post("paper/deep_research", {"message": message, "type": 1}, api_key=self.api_key, timeout=self.timeout)
            answer = data if isinstance(data, str) else None
            if isinstance(data, dict):
                answer = data.get("report") or data.get("answer") or data.get("content")
            if not isinstance(answer, str) or not answer.strip():
                raise ValueError("AMiner deep research returned no report text")
            references = (data.get("references") or data.get("sources") or []) if isinstance(data, dict) else []
            sources = []
            for reference in references:
                if isinstance(reference, dict) and reference.get("url") and reference.get("title"):
                    sources.append(SourceEvidence(
                        title=reference["title"], url=reference["url"],
                        finding=reference.get("finding") or "沉思报告所列参考来源",
                    ))
            report = InvestigationReport(
                answer=answer, sources=sources, limitations=[],
                process=ExecutionProcess(events=[{
                    "type": "aminer.deep_research.completed",
                    "parts": [{"part_kind": "user-prompt", "content": message}],
                }], usage={"requests": 1}),
            )
        except Exception:
            logger.exception("kind=agent provider=aminer Deep research failed: question=%r.", request.question[:160])
            raise
        logger.info("kind=agent provider=aminer Deep research completed: report_characters=%d.", len(answer))
        return report
