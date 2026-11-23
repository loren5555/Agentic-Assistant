"""Extract searchable terms and public-facing metadata from workspace records."""

import re

from plugins.data.sources.notion import plain_text

STOP_WORDS = {"from", "with", "using", "research", "study", "paper", "what", "does", "could", "would", "this", "that",
              "方法", "我们", "研究", "如何", "进行", "问题", "是否", "这个", "中的", "可以"}


def terms(value: str) -> list[str]:
    """Use English words and Chinese bigrams for title lookup and ranking."""
    result = []
    for word in re.findall(r"[a-z][a-z0-9-]+|[\u3400-\u9fff]+", value.casefold()):
        if "\u3400" <= word[0] <= "\u9fff":
            result.extend(word[i:i + 2] for i in range(len(word) - 1))
        elif len(word) >= 3 or word in {"rl", "ai"}:
            result.append(word)
    return list(dict.fromkeys(word for word in result if word not in STOP_WORDS))


def metadata(page: dict) -> tuple[str, dict[str, str]]:
    title = ""
    fields = {}
    for name, prop in page["properties"].items():
        kind = prop["type"]
        if kind == "title":
            title = plain_text(prop)
        elif name.startswith("Agent ") or name.casefold() in {
            "proposal data", "result data", "archive key", "publication key", "verification code"
        }:
            continue
        elif kind == "rich_text":
            fields[name] = plain_text(prop)[:1500]
        elif kind in {"select", "status"}:
            fields[name] = (prop.get(kind) or {}).get("name", "")
        elif kind == "multi_select":
            fields[name] = ", ".join(option["name"] for option in prop[kind])
    return title, {key: value for key, value in fields.items() if value}
