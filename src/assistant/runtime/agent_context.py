"""Checkpoint role guidance before decisions and scope it to a single model call."""
from contextlib import contextmanager
from contextvars import ContextVar
from hashlib import sha256
from importlib.resources import files

from dbos import DBOS
from logger import get_logger, trace_call
from assistant.components.data.memory.models import MemoryRole

_current = ContextVar("project_agent_instructions", default=None)


def current_instructions() -> str | None:
    """Return the checkpointed additions for the current decision, if supplied."""
    return _current.get()


@contextmanager
def use_instructions(instructions: str | None):
    token = _current.set(instructions)
    try:
        yield
    finally:
        _current.reset(token)


def skill_text(name: str) -> str:
    raw = files("assistant").joinpath("skills", name, "SKILL.md").read_text(encoding="utf-8")
    if not raw.startswith("---\n"):
        return raw.strip()
    _, delimiter, body = raw[4:].partition("\n---\n")
    if not delimiter:
        raise ValueError(f"Invalid front matter in {name}/SKILL.md")
    return body.strip()


@DBOS.step(name="ProposalWorkflows.recall_memory")
@trace_call("step", "recall_memory")
def recall_memory(self, role: MemoryRole) -> dict:
    skill = skill_text("project-agent")
    note = self.services.memory.recall(role)
    snapshot = {"instructions": "\n\n".join(filter(None, [skill, note.content])),
                "skill_version": sha256(skill.encode()).hexdigest(),
                "memories": {role: note.version} if note.content else {}}
    get_logger("runtime.agent_context").debug("Loaded role notebook for %s: %d characters.", role, len(note.content),
        extra={"details": {"skill_version": snapshot["skill_version"], "memories": snapshot["memories"]}})
    return snapshot
