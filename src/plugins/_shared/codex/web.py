"""Run structured public-web research through the subscription-backed Codex CLI.

Input origin:
    A capability supplies its research prompt, output schema and invocation settings.
Output destination:
    The capability receives a validated result and the original CLI event trace.
Responsibility:
    Own subprocess lifetime, isolated files, live search and telemetry collection.
    Discovery and evidence interpretation remain with the calling capability.
"""

from pathlib import Path
from tempfile import TemporaryDirectory
import asyncio
import json
import os

from pydantic import BaseModel

from assistant.runtime.records import ExecutionProcess
from plugins._shared.codex.process import read_process


class CodexResearchError(RuntimeError):
    """Preserve diagnostic events when Codex fails before producing a result."""

    def __init__(self, message: str, process: ExecutionProcess | None = None) -> None:
        """Attach the observed trace without using it to decide CLI success.

        Args:
            message: Exit, schema or result-file failure description.
            process: JSON events emitted before the invocation failed.
        """
        super().__init__(message)
        self.process = process


def research_schema(output_type: type[BaseModel]) -> dict:
    """Make model-default fields explicit in Codex's strict output contract.

    Args:
        output_type: Business model; runtime-only fields are excluded by its schema.

    Returns:
        JSON schema with every object property required. Empty/unknown values
        remain represented by their original types rather than omitted keys.
    """
    schema = output_type.model_json_schema()

    def require_properties(node: object) -> None:
        """Visit nested definitions and make each result object closed."""
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"])
            node.pop("default", None)
            for value in node.values():
                require_properties(value)
        elif isinstance(node, list):
            for value in node:
                require_properties(value)

    require_properties(schema)
    return schema


async def run_web_research[T: BaseModel](
    prompt: str, output_type: type[T], *, executable: str, model: str | None,
    effort: str | None, timeout_seconds: float,
) -> tuple[T, ExecutionProcess]:
    """Run one isolated research turn and validate its result file.

    Args:
        prompt: Capability instructions followed by research material.
        output_type: Pydantic model describing the business result.
        executable: Codex executable name or path.
        model: Explicit model, or the CLI default.
        effort: Explicit reasoning effort, or the model default.
        timeout_seconds: Deadline including tool use and final output.

    Returns:
        Structured business result and optional stdout telemetry.
    """
    environment = os.environ.copy()
    environment.pop("OPENAI_API_KEY", None)
    environment.pop("CODEX_API_KEY", None)

    with TemporaryDirectory(prefix="assistant-research-") as directory:
        workspace = Path(directory)
        schema_path = workspace / "schema.json"
        result_path = workspace / "result.json"
        schema_path.write_text(json.dumps(research_schema(output_type)), encoding="utf-8")
        command = [
            executable, "exec", "--ignore-user-config", "--ignore-rules",
            "--strict-config", "--ephemeral", "--skip-git-repo-check",
            "--sandbox=read-only", "--json", f"--output-schema={schema_path}",
            f"--output-last-message={result_path}",
            "-c", "forced_login_method='chatgpt'",
            "-c", "model_provider='openai'",
            "-c", "web_search='live'", "-c", "project_doc_max_bytes=0",
        ]
        if model:
            command.extend(["--model", model])
        if effort:
            command.extend(["-c", f"model_reasoning_effort={json.dumps(effort)}"])
        # Keep model-default code-mode transport for hosted search, but no local
        # execution, private integrations or unrelated agent capabilities.
        for feature in (
            "shell_tool", "apps", "plugins", "hooks", "browser_use",
            "computer_use", "image_generation", "multi_agent", "view_image",
        ):
            command.extend(["-c", f"features.{feature}=false"])
        command.append("-")

        process = await asyncio.create_subprocess_exec(
            *command, cwd=workspace, env=environment,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        communication = asyncio.create_task(process.communicate(prompt.encode()))
        try:
            stdout, stderr = await asyncio.wait_for(
                asyncio.shield(communication), timeout=timeout_seconds,
            )
        except (TimeoutError, asyncio.CancelledError):
            if process.returncode is None:
                process.terminate()
            try:
                await asyncio.wait_for(asyncio.shield(communication), timeout=5)
            except TimeoutError:
                if process.returncode is None:
                    process.kill()
                await communication
            raise

        telemetry = read_process(stdout.decode(errors="replace"))
        if process.returncode != 0:
            detail = stderr.decode(errors="replace").strip()
            if not detail:
                errors = [event for event in telemetry.events if event.get("type") in {"error", "turn.failed"}]
                detail = json.dumps(errors[-1], ensure_ascii=False) if errors else "No stderr diagnostic; see recorded CLI events"
            raise CodexResearchError(f"Codex exited with code {process.returncode}: {detail}", telemetry)
        try:
            result = output_type.model_validate_json(result_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise CodexResearchError(f"Codex result could not be read: {error}", telemetry) from error
        return result, telemetry
