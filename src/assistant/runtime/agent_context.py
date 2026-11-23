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


def load_instructions(name: str) -> str:
    """Read packaged instructions selected by the calling component."""
    return files("assistant").joinpath("instructions", f"{name}.md").read_text(encoding="utf-8").strip()


def writing_guidance(purpose: str, *, brief: bool = False) -> str:
    """Compose project prose guidance with the reader's task for this output."""
    guide = load_instructions("researcher-style-writing")
    if brief:
        guide = guide.split("\n## ", 1)[0].rstrip()
    return f"\n\n{guide}\n\n{purpose}"


@DBOS.step(name="ProposalWorkflows.recall_memory")
@trace_call("step", "recall_memory")
def recall_memory(self, role: MemoryRole) -> dict:
    base_instructions = load_instructions("project-agent")
    note = self.services.memory.recall(role)
    snapshot = {"instructions": "\n\n".join(filter(None, [base_instructions, note.content])),
                "instructions_version": sha256(base_instructions.encode()).hexdigest(),
                "memories": {role: note.version} if note.content else {}}
    get_logger("runtime.agent_context").debug("Loaded role notebook for %s: %d characters.", role, len(note.content),
        extra={"details": {"instructions_version": snapshot["instructions_version"], "memories": snapshot["memories"]}})
    return snapshot
