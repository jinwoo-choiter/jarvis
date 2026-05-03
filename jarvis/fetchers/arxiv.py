"""arXiv RSS fetcher. Emits unified-schema JSON on stdout.

Window: items whose RSS `published` timestamp falls within the last
`window.hours` hours (default 24) relative to invocation, evaluated in UTC.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from typing import Any

import feedparser
import httpx

from jarvis._config import load_config

ARXIV_RSS_URL = "https://rss.arxiv.org/rss/{category}"
SOURCE = "arxiv"
HTTP_TIMEOUT = 30.0


def _now_utc() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def _parse_published(entry: Any) -> dt.datetime | None:
    parsed = getattr(entry, "published_parsed", None) or getattr(
        entry, "updated_parsed", None
    )
    if parsed is None:
        return None
    try:
        return dt.datetime(*parsed[:6], tzinfo=dt.timezone.utc)
    except (TypeError, ValueError):
        return None


def _arxiv_id_from_entry(entry: Any) -> str | None:
    raw_id = getattr(entry, "id", "") or ""
    link = getattr(entry, "link", "") or ""
    candidate = raw_id or link
    if not candidate:
        return None
    tail = candidate.rstrip("/").rsplit("/", 1)[-1]
    if not tail:
        return None
    return tail.split("v")[0] if tail[0].isdigit() else tail


def _entry_to_item(entry: Any) -> dict[str, Any] | None:
    arxiv_id = _arxiv_id_from_entry(entry)
    if not arxiv_id:
        return None

    published = _parse_published(entry)
    if published is None:
        return None

    title = (getattr(entry, "title", "") or "").strip()
    summary = (getattr(entry, "summary", "") or "").strip()
    link = (
        getattr(entry, "link", "") or f"https://arxiv.org/abs/{arxiv_id}"
    ).strip()

    authors = []
    for a in getattr(entry, "authors", []) or []:
        name = a.get("name") if isinstance(a, dict) else getattr(a, "name", None)
        if name:
            authors.append(name)

    categories = []
    for tag in getattr(entry, "tags", []) or []:
        term = tag.get("term") if isinstance(tag, dict) else getattr(tag, "term", None)
        if term:
            categories.append(term)

    return {
        "id": f"arxiv:{arxiv_id}",
        "title": title,
        "url": link,
        "published_at": published.isoformat().replace("+00:00", "Z"),
        "summary_raw": summary,
        "metadata": {
            "authors": authors,
            "categories": categories,
        },
    }


def _fetch_category(category: str, window_start: dt.datetime) -> list[dict[str, Any]]:
    url = ARXIV_RSS_URL.format(category=category)
    response = httpx.get(url, timeout=HTTP_TIMEOUT, follow_redirects=True)
    response.raise_for_status()

    feed = feedparser.parse(response.text)
    if getattr(feed, "bozo", False) and not getattr(feed, "entries", None):
        raise RuntimeError(f"feedparser could not parse {url}: {feed.bozo_exception!r}")

    items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for entry in feed.entries:
        item = _entry_to_item(entry)
        if item is None:
            continue
        published = _parse_published(entry)
        if published is None or published < window_start:
            continue
        if item["id"] in seen_ids:
            continue
        seen_ids.add(item["id"])
        items.append(item)
    return items


def _build_envelope(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "source": SOURCE,
        "fetched_at": _now_utc().isoformat().replace("+00:00", "Z"),
        "items": items,
    }


def main() -> int:
    config = load_config()
    categories: list[str] = list(config.get("arxiv", {}).get("categories", []) or [])
    hours = int(config.get("window", {}).get("hours", 24))
    window_start = _now_utc() - dt.timedelta(hours=hours)

    if not categories:
        print(
            "[arxiv] no categories configured; emitting empty envelope",
            file=sys.stderr,
        )
        json.dump(_build_envelope([]), sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for category in categories:
        try:
            for item in _fetch_category(category, window_start):
                if item["id"] in seen_ids:
                    continue
                seen_ids.add(item["id"])
                items.append(item)
        except (httpx.HTTPError, RuntimeError) as exc:
            print(
                f"[arxiv] transient failure for category={category}: {exc}",
                file=sys.stderr,
            )

    json.dump(_build_envelope(items), sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
