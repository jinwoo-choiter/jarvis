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

YOUTUBE_PLAYLIST_ITEMS_URL = "https://www.googleapis.com/youtube/v3/playlistItems"
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
    snippet = entry.get("snippet") or {}
    content_details = entry.get("contentDetails") or {}

    video_id = content_details.get("videoId") or (
        snippet.get("resourceId") or {}
    ).get("videoId")
    if not video_id:
        return None

    # contentDetails.videoPublishedAt is the actual upload time. snippet.publishedAt
    # on a playlistItems response is when the item joined the playlist — for the
    # uploads playlist these are usually identical, but prefer the former.
    published_at = content_details.get("videoPublishedAt") or snippet.get(
        "publishedAt"
    )
    if not published_at:
        return None

    return {
        "id": f"youtube:{video_id}",
        "title": (snippet.get("title") or "").strip(),
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "published_at": published_at,
        "summary_raw": (snippet.get("description") or "").strip(),
        "metadata": {
            "channel_id": snippet.get("videoOwnerChannelId")
            or snippet.get("channelId"),
            "channel_title": snippet.get("videoOwnerChannelTitle")
            or snippet.get("channelTitle"),
        },
    }


def _fetch_channel(
    channel_id: str, api_key: str, window_start: dt.datetime
) -> list[dict[str, Any]]:
    # YouTube exposes each channel's uploads as a playlist whose ID is the
    # channel ID with the leading "UC" swapped to "UU". Fetching that playlist
    # is ~100x cheaper than search.list and avoids a known indexing quirk where
    # search.list + publishedAfter returns stale/empty results.
    if not channel_id.startswith("UC"):
        return []
    uploads_playlist_id = "UU" + channel_id[2:]
    params = {
        "key": api_key,
        "part": "snippet,contentDetails",
        "playlistId": uploads_playlist_id,
        "maxResults": MAX_RESULTS_PER_CHANNEL,
    }
    response = httpx.get(
        YOUTUBE_PLAYLIST_ITEMS_URL, params=params, timeout=HTTP_TIMEOUT
    )
    response.raise_for_status()
    payload = response.json()

    items: list[dict[str, Any]] = []
    for entry in payload.get("items", []):
        item = _entry_to_item(entry)
        if item is None:
            continue
        published_at = dt.datetime.fromisoformat(
            item["published_at"].replace("Z", "+00:00")
        )
        if published_at < window_start:
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
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                # Empty/no-uploads channels return 404 on the uploads playlist.
                continue
            print(
                f"[youtube] HTTP {exc.response.status_code} for channel={channel_id}",
                file=sys.stderr,
            )
        except (httpx.HTTPError, ValueError) as exc:
            # Strip URL from the error to avoid leaking the API key into logs.
            print(
                f"[youtube] transient failure for channel={channel_id}: "
                f"{type(exc).__name__}",
                file=sys.stderr,
            )

    json.dump(_build_envelope(items), sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
