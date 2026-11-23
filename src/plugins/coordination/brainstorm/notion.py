"""Read the starting point and relevant history for one BrainStorm exploration.

New material comes from Papers, Knowledge or an Idea's research notes. Idea mode
uses an open question from an active project. Title queries reach older entries
directly. Recent metadata provides additional candidates across collections, then
only selected pages contribute body excerpts to the Codex context.
"""

from collections.abc import Mapping
from contextlib import closing
from pathlib import Path
import re
import sqlite3

from notion_client import Client
from notion_client.errors import APIErrorCode, APIResponseError

from assistant.components.coordination.brainstorm.models import BrainstormContext, BrainstormMode, ResearchNote
from assistant.components.coordination.brainstorm.protocol import VersionLookup
from logger import get_logger, trace_call
from plugins._shared.notion.config import SourceCollectionSettings
from plugins._shared.notion.markdown import page_markdown
from plugins._shared.notion.sparks import resolve_sparks
from plugins._shared.notion.catalog import metadata, terms

SEED_WINDOW = 12
HISTORY_PER_COLLECTION = 6
MAX_HISTORY = 8
SORT_BY_EDIT = [{"timestamp": "last_edited_time", "direction": "descending"}]
QUESTION_FIELDS = ("open question", "open questions", "research question", "research questions", "待解问题", "研究问题")
NOTE_FIELDS = ("research log", "research logs", "research notes", "findings", "experiment log", "研究日志", "研究记录", "实验记录", "研究发现")
ACTIVE_STATES = {"active", "open", "in progress", "ongoing", "doing", "in research", "进行中", "活跃", "研究中"}


def field_or_section(fields: dict[str, str], body: str, names: tuple[str, ...]) -> str:
    for name, value in fields.items():
        if name.casefold() in names:
            return value
    # Select the latest matching section and retain its nested headings.
    lines = body.splitlines()
    for index in range(len(lines) - 1, -1, -1):
        line = lines[index].strip()
        heading = re.match(r"^(#{1,6})\s+", line)
        label = line[heading.end():] if heading else line
        parts = re.split(r"[:：]", label.replace("**", ""), maxsplit=1)
        if parts[0].strip().casefold() not in names:
            continue
        content = parts[1:] if len(parts) > 1 else []
        level = len(heading[1]) if heading else 6
        for following in lines[index + 1:]:
            next_heading = re.match(r"^(#{1,6})\s+", following)
            if next_heading and len(next_heading[1]) <= level:
                break
            content.append(following)
        value = "\n".join(content).strip()
        if value:
            return value
    return ""


def is_active(page: dict) -> bool:
    # An adopted project without a lifecycle column is active until archived.
    if page.get("archived") or page.get("in_trash"):
        return False
    statuses = [prop for name, prop in page["properties"].items()
                if (prop["type"] == "status" or name.casefold() in {"state", "status", "状态"})
                and prop["type"] in {"select", "status"}]
    return all((prop.get(prop["type"]) or {}).get("name", "").casefold() in ACTIVE_STATES
               for prop in statuses)


def excerpt(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    head = limit // 2
    return text[:head] + "\n[… excerpt …]\n" + text[-head:]


class ResearchLibrary:
    def __init__(self, options: Mapping[str, object], *, cursor_path: Path | None = None) -> None:
        self.options = dict(options)
        self.cursor_path = cursor_path
        if cursor_path is not None:
            cursor_path.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(cursor_path)) as db, db:
                db.execute("CREATE TABLE IF NOT EXISTS library_cursors (mode TEXT, source TEXT, cursor TEXT, "
                           "PRIMARY KEY (mode, source))")
        settings = SourceCollectionSettings.model_validate(options)
        self.token = settings.token
        self.collections = {
            name: source for name, source in {
                "paper": settings.papers_data_source_id, "knowledge": settings.knowledge_data_source_id,
                "idea": str(options.get("ideas_data_source_id") or ""),
                "workbench": str(options.get("workbench_data_source_id") or ""),
            }.items() if source
        }
        self.logger = get_logger("plugins.coordination.brainstorm.notion")

    def _note(self, client, collection, page, *, mode=None) -> ResearchNote | None:
        title, fields = metadata(page)
        body = page_markdown(client, page["id"])
        if collection == "idea" and mode:
            if mode == "idea":
                focus = field_or_section(fields, body, QUESTION_FIELDS)
                if not focus:
                    focus = "\n".join(line for line in [title, *body.splitlines()] if re.search(r"[?？]", line))
            else:
                appended = re.findall(
                    r"^## Research finding — (.+?)(?=^## |\Z)", body, re.M | re.S,
                )
                focus = appended[-1].strip() if appended else field_or_section(fields, body, NOTE_FIELDS)
            if not focus:
                return None
        else:
            focus = ""
        details = "\n".join(f"{key}: {value}" for key, value in fields.items())
        if mode == "material" and collection == "idea":
            # A newly appended finding is the event. Earlier project notes can be
            # explored independently through Idea mode.
            content = focus
        else:
            content = "\n\n".join(s for s in (focus[:2500], details[:3000], body) if s)
        return ResearchNote(page_id=page["id"], url=page["url"], title=title, collection=collection,
                            revision=page["last_edited_time"], text=excerpt(content, 14000 if mode else 3200))

    def _cursors(self, mode: str) -> dict[str, str]:
        if self.cursor_path is None:
            return {}
        with closing(sqlite3.connect(self.cursor_path)) as db:
            return dict(db.execute("SELECT source,cursor FROM library_cursors WHERE mode=?", (mode,)))

    def _advance(self, mode: str, cursors: dict[str, str]) -> None:
        if self.cursor_path is not None:
            with closing(sqlite3.connect(self.cursor_path)) as db, db:
                db.executemany("INSERT OR REPLACE INTO library_cursors VALUES (?,?,?)",
                               [(mode, source, cursor) for source, cursor in cursors.items()])

    def _seed_page(self, client, source, cursor=None):
        args = {"data_source_id": source, "sorts": SORT_BY_EDIT, "page_size": SEED_WINDOW}
        if cursor:
            args["start_cursor"] = cursor
        try:
            return client.data_sources.query(**args)
        except APIResponseError as error:
            if not cursor or error.code != APIErrorCode.ValidationError or "cursor" not in str(error).lower():
                raise
            self.logger.warning("Research library cursor expired. Restarting its scan from recent entries.")
            return client.data_sources.query(**{k: v for k, v in args.items() if k != "start_cursor"})

    def _seed(self, client, mode, page_id, lookup_versions) -> ResearchNote | None:
        eligible = ["idea"] if mode == "idea" else ["paper", "knowledge", "idea"]
        collections = {k: v for k, v in self.collections.items() if k in eligible}
        if page_id:
            page = client.pages.retrieve(page_id=page_id)
            parent = page["parent"].get("data_source_id", "").replace("-", "")
            named = next((name for name, source in collections.items() if source.replace("-", "") == parent), "")
            if not named:
                raise ValueError(f"Choose a {', '.join(eligible)} page for {mode} exploration")
            if not (page.get("archived") or page.get("in_trash")) and (mode != "idea" or is_active(page)):
                note = self._note(client, named, page, mode=mode)
                if note:
                    return note
            requirement = ("an active Idea with an open question" if mode == "idea" else
                           "an available paper, knowledge page or Idea with research notes")
            raise ValueError(f"BrainStorm requires {requirement}")

        cursors = self._cursors(mode)
        # Old material remains reachable while a fresh first page keeps new edits visible.
        # Keep the current window until every candidate in it has been considered.
        next_starts = {}
        next_ends = {}
        observed = set()
        for pass_number in range(2):
            pages = []
            for name, source in collections.items():
                start = next_starts.get(source) if pass_number else None
                if pass_number and not start:
                    continue
                batch = self._seed_page(client, source, start)
                end = batch.get("next_cursor") or ""
                if pass_number:
                    next_ends[source] = end
                else:
                    next_starts[source] = cursors.get(source) or end
                rows = batch["results"]
                self.logger.info("Seed query completed: collection=%s pages=%d has_more=%s.",
                                 name, len(rows), batch.get("has_more", False))
                handled = lookup_versions([page["id"] for page in rows]) if lookup_versions else {}
                for page in rows:
                    if (page["id"] in observed or handled.get(page["id"]) == page["last_edited_time"] or
                        page.get("archived") or page.get("in_trash") or (mode == "idea" and not is_active(page))):
                        continue
                    observed.add(page["id"])
                    pages.append((name, page))
            pages.sort(key=lambda entry: (entry[1]["last_edited_time"], entry[1]["id"]), reverse=True)
            for name, page in pages:
                note = self._note(client, name, page, mode=mode)
                if note:
                    if pass_number:
                        self._advance(mode, next_starts)
                    return note
        self._advance(mode, next_ends)
        if any(next_ends.values()):
            self.logger.info("Finished the current library scan window. A later run will continue into older pages.")
        return None

    def _history(self, client, seed) -> list[ResearchNote]:
        collections = self.collections.copy()
        if self.options.get("sparks_data_source_id") or self.options.get("assistant_page_id"):
            collections["spark"] = resolve_sparks(client, self.options)
        keywords = terms(seed.title + " " + seed.text[:1000])[:8]
        matches = {}
        for name, source in collections.items():
            recent = client.data_sources.query(data_source_id=source, sorts=SORT_BY_EDIT,
                                               page_size=HISTORY_PER_COLLECTION)["results"]
            relevant = []
            if keywords:
                schema = client.data_sources.retrieve(data_source_id=source)["properties"]
                title_key = next(key for key, spec in schema.items() if spec["type"] == "title")
                relevant = client.data_sources.query(
                    data_source_id=source, sorts=SORT_BY_EDIT, page_size=HISTORY_PER_COLLECTION,
                    filter={"or": [{"property": title_key, "title": {"contains": word}} for word in keywords]},
                )["results"]
            for page in [*recent, *relevant]:
                if page["id"] == seed.page_id:
                    continue
                title, fields = metadata(page)
                searchable = set(terms(title + " " + " ".join(fields.values())[:1800]))
                score = sum(word in searchable for word in keywords)
                matches[page["id"]] = (score, page["last_edited_time"], name, page)
        ordered = sorted(matches.values(), key=lambda row: (row[0], row[1], row[3]["id"]), reverse=True)
        # Reserve room for a relevant project or Spark even when many newer
        # paper titles match. Use the remaining slots for the strongest matches.
        first_matches = {}
        for row in ordered:
            if row[0]:
                first_matches.setdefault(row[2], row)
        selected = {row[3]["id"]: row for row in first_matches.values()}
        for row in ordered:
            if len(selected) == MAX_HISTORY:
                break
            selected.setdefault(row[3]["id"], row)
        return [self._note(client, name, page) for _, _, name, page in selected.values()]

    @trace_call("component", "research_library.context")
    def context(
        self, mode: BrainstormMode, page_id: str | None = None, *,
        lookup_versions: VersionLookup | None = None,
    ) -> BrainstormContext | None:
        self.logger.info("kind=script provider=notion Reading exploration material: mode=%s explicit=%s.", mode, bool(page_id))
        with Client(auth=self.token) as client:
            seed = self._seed(client, mode, page_id, lookup_versions)
            if seed is None:
                self.logger.info("No eligible starting point in this library window: mode=%s.", mode)
                return None
            self.logger.debug("Finding related research history: title=%r.", seed.title)
            history = self._history(client, seed)
        self.logger.info("Exploration context ready: title=%r related_pages=%d.", seed.title, len(history))
        return BrainstormContext(mode=mode, seed=seed, history=history)
