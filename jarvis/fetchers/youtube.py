"""YouTube Data API v3 fetcher. Emits unified-schema JSON on stdout.

Window: items whose `snippet.publishedAt` falls within the last `window.hours`
hours (default 24) relative to invocation, evaluated in UTC.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
from typing import Any

import httpx

from jarvis._config import load_config

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
SOURCE = "youtube"
HTTP_TIMEOUT = 30.0
MAX_RESULTS_PER_CHANNEL = 25


def _now_utc() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def _isoformat_z(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _build_envelope(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "source": SOURCE,
        "fetched_at": _isoformat_z(_now_utc()),
        "items": items,
    }


def _entry_to_item(entry: dict[str, Any]) -> dict[str, Any] | None:
    id_block = entry.get("id") or {}
    video_id = id_block.get("videoId")
    if not video_id:
        return None

    snippet = entry.get("snippet") or {}
    published_at = snippet.get("publishedAt")
    if not published_at:
        return None

    return {
        "id": f"youtube:{video_id}",
        "title": (snippet.get("title") or "").strip(),
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "published_at": published_at,
        "summary_raw": (snippet.get("description") or "").strip(),
        "metadata": {
            "channel_id": snippet.get("channelId"),
            "channel_title": snippet.get("channelTitle"),
        },
    }


def _fetch_channel(
    channel_id: str, api_key: str, window_start: dt.datetime
) -> list[dict[str, Any]]:
    params = {
        "key": api_key,
        "part": "snippet",
        "channelId": channel_id,
        "maxResults": MAX_RESULTS_PER_CHANNEL,
        "order": "date",
        "type": "video",
        "publishedAfter": _isoformat_z(window_start),
    }
    response = httpx.get(YOUTUBE_SEARCH_URL, params=params, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    payload = response.json()

    items: list[dict[str, Any]] = []
    for entry in payload.get("items", []):
        item = _entry_to_item(entry)
        if item is None:
            continue
        items.append(item)
    return items


def main() -> int:
    config = load_config()
    channels: list[str] = list(config.get("youtube", {}).get("channels", []) or [])
    hours = int(config.get("window", {}).get("hours", 24))
    window_start = _now_utc() - dt.timedelta(hours=hours)

    if not channels:
        print(
            "[youtube] no channels configured; emitting empty envelope",
            file=sys.stderr,
        )
        json.dump(_build_envelope([]), sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    api_key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not api_key:
        print(
            "[youtube] YOUTUBE_API_KEY is not set; cannot query the API",
            file=sys.stderr,
        )
        return 1

    items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for channel_id in channels:
        try:
            for item in _fetch_channel(channel_id, api_key, window_start):
                if item["id"] in seen_ids:
                    continue
                seen_ids.add(item["id"])
                items.append(item)
        except (httpx.HTTPError, ValueError) as exc:
            print(
                f"[youtube] transient failure for channel={channel_id}: {exc}",
                file=sys.stderr,
            )

    json.dump(_build_envelope(items), sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
