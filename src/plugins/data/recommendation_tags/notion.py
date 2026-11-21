"""Manage the visible Recommendation Tags catalog and aggregate explicit votes.

Setup links the three reading databases to the catalog. Readers assign relations
when publishing. Recommendation runs recount unique liked papers per direction.
"""

from collections import defaultdict
import hashlib
from threading import RLock
from unicodedata import normalize

from notion_client import Client

from assistant.components.recommendations.discovery.identity import candidate_identity
from assistant.components.recommendations.discovery.models import PaperCandidate, ResearchInterest
from assistant.components.recommendations.tags import DirectionTag
from plugins._shared.notion.config import ResearchFeedSettings
from plugins.data.discovery_pool.notion import plain, text
from logger import get_logger

RELATION = "Recommendation Tags"
_lock = RLock()


def pages(client, source, condition=None):
    query = {"data_source_id": source, "page_size": 100}
    if condition:
        query["filter"] = condition
    while True:
        batch = client.data_sources.query(**query)
        yield from batch["results"]
        if not batch["has_more"]:
            return
        query["start_cursor"] = batch["next_cursor"]


def normalized(name):
    return " ".join(normalize("NFKC", name).casefold().split())


def relation(ids):
    return {"relation": [{"id": page_id} for page_id in dict.fromkeys(ids)]}


class RecommendationTags:
    def __init__(self, options):
        self.settings = ResearchFeedSettings.model_validate(options)
        self.source = self.settings.recommendation_tags_data_source_id
        self.logger = get_logger("plugins.data.recommendation_tags")

    def _source(self, client, *, create=False):
        if self.source:
            return self.source
        query = {"block_id": self.settings.assistant_page_id, "page_size": 100}
        if not query["block_id"]:
            raise ValueError("Configure Assistant page or recommendation_tags_data_source_id")
        while True:
            batch = client.blocks.children.list(**query)
            for block in batch["results"]:
                if block.get("child_database", {}).get("title") == RELATION:
                    db = client.databases.retrieve(database_id=block["id"])
                    self.source = db["data_sources"][0]["id"]
                    return self.source
            if not batch["has_more"]:
                break
            query["start_cursor"] = batch["next_cursor"]
        if not create:
            raise ValueError("Recommendation Tags catalog missing. Run assistant setup.")
        schema = {"Name": {"title": {}}, "Definition": {"rich_text": {}},
                  "Aliases": {"multi_select": {}}, "Priority": {"number": {}},
                  "Feedback Weight": {"number": {}}, "Paused": {"checkbox": {}}}
        db = client.databases.create(parent={"type": "page_id", "page_id": query["block_id"]},
                                     title=text(RELATION), initial_data_source={"properties": schema})
        self.source = db["data_sources"][0]["id"]
        return self.source

    def initialize(self, pool_id, seeds):
        self.logger.info("Preparing recommendation directions and reading relations.")
        with Client(auth=self.settings.token) as client:
            target = self._source(client, create=True)
            for source in (pool_id, self.settings.research_feed_data_source_id, self.settings.papers_data_source_id):
                props = client.data_sources.retrieve(data_source_id=source)["properties"]
                if RELATION in props:
                    actual = props[RELATION].get("relation", {}).get("data_source_id", "")
                    if actual.replace("-", "") != target.replace("-", ""):
                        raise ValueError(f"{RELATION} in {source} must relate to catalog {target}")
                else:
                    client.data_sources.update(data_source_id=source, properties={RELATION: {"relation": {
                        "data_source_id": target, "type": "single_property", "single_property": {}}}})
        self.resolve([DirectionTag(name=name, definition="") for name in seeds], initial=True)
        self.logger.info("Recommendation directions ready: initial topics=%d.", len(seeds))

    def _catalog(self, client):
        rows = []
        for page in pages(client, self._source(client)):
            p = page["properties"]
            rows.append(dict(existing_id=page["id"], name=plain(p["Name"]), definition=plain(p["Definition"]),
                             aliases=[v["name"] for v in p["Aliases"]["multi_select"]],
                             paused=p["Paused"]["checkbox"], priority=1 if p["Priority"]["number"] is None else p["Priority"]["number"],
                             feedback=p["Feedback Weight"]["number"] or 0))
        return rows

    def catalog(self):
        with Client(auth=self.settings.token) as client:
            return self._catalog(client)

    def resolve(self, choices, *, initial=False):
        return self.resolve_batch([choices], initial=initial)[0]

    def resolve_batch(self, groups, *, initial=False):
        """Resolve a collection against one catalog snapshot, including new sibling tags."""
        if not any(groups):
            return [[] for _ in groups]
        with _lock, Client(auth=self.settings.token) as client:
            rows = self._catalog(client)
            ids = {row["existing_id"] for row in rows}
            names = {normalized(alias): row["existing_id"] for row in rows
                     for alias in [row["name"], *row["aliases"]]}
            resolved = []
            for choices in groups:
                result = []
                for choice in choices:
                    name = choice.name.strip()
                    if not name:
                        continue
                    key = normalized(name)
                    page_id = choice.existing_id or names.get(key)
                    if choice.existing_id and page_id not in ids:
                        raise ValueError(f"Unknown recommendation direction for {name}")
                    if not page_id:
                        page = client.pages.create(parent={"type": "data_source_id", "data_source_id": self.source},
                            properties={"Name": {"title": text(name)}, "Definition": {"rich_text": text(choice.definition)},
                                        "Priority": {"number": 1 if initial else 0}, "Feedback Weight": {"number": 0}})
                        page_id = names[key] = page["id"]
                        ids.add(page_id)
                        self.logger.info("Created recommendation direction: %s.", name)
                    result.append(page_id)
                resolved.append(list(dict.fromkeys(result)))
            return resolved

    def preferences(self, pool_id):
        """Count an identity once per direction across the three liked-item collections."""
        settings = self.settings
        votes = defaultdict(set)
        avoids = []
        with _lock, Client(auth=settings.token) as client:
            sources = [(pool_id, "Feedback", "select"),
                       (settings.papers_data_source_id, "Interested", "checkbox"),
                       (settings.research_feed_data_source_id, settings.feed_feedback_property, None)]
            for source, field, kind in sources:
                if kind is None:
                    kind = client.data_sources.retrieve(data_source_id=source)["properties"][field]["type"]
                query = {"equals": True} if kind == "checkbox" else {"is_not_empty": True}
                for page in pages(client, source, {"property": field, kind: query}):
                    props = page["properties"]
                    title = plain(next(v for v in props.values() if v["type"] == "title"))
                    mark = "Interested" if kind == "checkbox" else (props[field][kind] or {}).get("name")
                    if mark == "Not Interested":
                        avoids.append(ResearchInterest(id="avoid:" + page["id"], title=title, priority=0))
                    if mark != "Interested":
                        continue
                    if source == settings.research_feed_data_source_id:
                        key = plain(props["Stable ID"]) or page["id"]
                    else:
                        if source == pool_id:
                            paper = PaperCandidate.model_validate_json(plain(props["Candidate Data"]))
                        else:
                            doi = props.get("DOI", {})
                            paper = PaperCandidate(id=page["id"], title=title,
                                                   url=props.get("Link", {}).get("url") or "",
                                                   doi=(doi.get("url") or "") if doi.get("type") == "url" else plain(doi))
                        identity = candidate_identity(paper)
                        key = hashlib.sha256(f"research-feed:{identity}".encode()).hexdigest()
                    for tag in props[RELATION]["relation"]:
                        votes[tag["id"]].add(key)
            preferences = []
            for row in self._catalog(client):
                weight = min(4, len(votes[row["existing_id"]]))
                if weight != row["feedback"]:
                    client.pages.update(page_id=row["existing_id"], properties={"Feedback Weight": {"number": weight}})
                priority = row["priority"] + weight
                if priority > 0 and not row["paused"]:
                    preferences.append(ResearchInterest(id=row["existing_id"], title=row["name"],
                                                       description=row["definition"], priority=priority))
        return preferences + avoids
