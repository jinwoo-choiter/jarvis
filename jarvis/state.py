"""SQLite seen-item store.

Schema:
    seen(
        url_hash   TEXT PRIMARY KEY,
        first_seen TEXT NOT NULL,
        category   TEXT,
        url        TEXT NOT NULL DEFAULT ''   -- the original URL, used by export-seen-recent
    )

Categories include `arxiv`, `youtube` (derived from fetcher item ids), and the
sentinel `web` for URLs that appeared in the delivered brief without coming
through any fetcher (i.e., `web_search` results surfaced by the synthesis prompt).

Workflow:
    init_db()                              -- idempotent; forward-migrates legacy DBs
    new_envelope = dedupe(envelopes)       -- emits items absent from the store
    mark_seen(items)                       -- only after delivery succeeds
    mark_delivered(new_envelope, brief)    -- records every URL in the brief; items
                                              not in the envelope are tagged `web`
    export_seen_recent(out, days)          -- flat URL list for the synthesis deny-list

CLI usage (driven by run.sh):
    python -m jarvis.state dedupe <path>...                          > /tmp/raw/new.json
    python -m jarvis.state mark-seen [<path>]                        # reads stdin if no path
    python -m jarvis.state mark-delivered --new <new.json> --briefing <brief.md>
    python -m jarvis.state export-seen-recent --days N --out <path>  # writes deny-list
    python -m jarvis.state init-db                                   # rare; auto-run by other commands
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _db_path() -> Path:
    return _repo_root() / "state" / "seen.sqlite"


def _now_utc_iso() -> str:
    return dt.datetime.now(tz=dt.timezone.utc).isoformat().replace("+00:00", "Z")


def url_hash(url: str) -> str:
    """Stable hash key over the canonical URL.

    Canonicalization is intentionally minimal: lowercase scheme + netloc,
    preserve path/query exactly. The same URL always produces the same hash
    across runs and machines.
    """
    parsed = urlparse(url.strip())
    canonical = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path}"
    if parsed.query:
        canonical += f"?{parsed.query}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _connect() -> sqlite3.Connection:
    db_path = _db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seen (
                url_hash   TEXT PRIMARY KEY,
                first_seen TEXT NOT NULL,
                category   TEXT,
                url        TEXT NOT NULL DEFAULT ''
            )
            """
        )
        # Forward-migrate older databases that predate the `url` column.
        cols = [row[1] for row in conn.execute("PRAGMA table_info(seen)").fetchall()]
        if "url" not in cols:
            conn.execute("ALTER TABLE seen ADD COLUMN url TEXT NOT NULL DEFAULT ''")


def _existing_hashes(conn: sqlite3.Connection, hashes: set[str]) -> set[str]:
    if not hashes:
        return set()
    placeholders = ",".join("?" for _ in hashes)
    rows = conn.execute(
        f"SELECT url_hash FROM seen WHERE url_hash IN ({placeholders})",
        list(hashes),
    ).fetchall()
    return {row[0] for row in rows}


def dedupe(envelopes: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a single envelope of items whose URL hashes are not yet seen.

    Items missing a `url` are dropped (defensive — they cannot be deduped).
    Within a single dedupe call, duplicate URLs across the input collapse
    to the first occurrence.
    """
    init_db()

    candidate_items: list[dict[str, Any]] = []
    candidate_hashes: list[str] = []
    seen_in_input: set[str] = set()

    for envelope in envelopes:
        for item in envelope.get("items", []) or []:
            url = (item.get("url") or "").strip()
            if not url:
                continue
            h = url_hash(url)
            if h in seen_in_input:
                continue
            seen_in_input.add(h)
            candidate_items.append(item)
            candidate_hashes.append(h)

    with _connect() as conn:
        already = _existing_hashes(conn, set(candidate_hashes))

    new_items = [
        item
        for item, h in zip(candidate_items, candidate_hashes)
        if h not in already
    ]

    return {
        "source": "dedupe",
        "fetched_at": _now_utc_iso(),
        "items": new_items,
    }


def mark_seen(envelope: dict[str, Any]) -> int:
    """Insert URL hashes for the items in `envelope` into the seen store.

    Returns the number of newly inserted rows. Items missing a `url` are
    skipped. Duplicate hashes (already-seen items) are silently ignored
    via INSERT OR IGNORE.
    """
    init_db()
    now = _now_utc_iso()
    rows: list[tuple[str, str, str | None, str]] = []
    for item in envelope.get("items", []) or []:
        url = (item.get("url") or "").strip()
        if not url:
            continue
        category = None
        item_id = item.get("id") or ""
        if isinstance(item_id, str) and ":" in item_id:
            category = item_id.split(":", 1)[0]
        rows.append((url_hash(url), now, category, url))

    if not rows:
        return 0

    with _connect() as conn:
        cur = conn.executemany(
            "INSERT OR IGNORE INTO seen(url_hash, first_seen, category, url) VALUES (?, ?, ?, ?)",
            rows,
        )
        conn.commit()
        return cur.rowcount if cur.rowcount is not None else 0


# Match http(s) URLs in markdown / plain text. Stops at whitespace and common
# closing punctuation; trailing soft punctuation is stripped below.
_URL_RE = re.compile(r"https?://[^\s)\]>'\"<]+")
_URL_TRAILING = ".,;:!?'\")]"


def _extract_urls(text: str) -> set[str]:
    urls: set[str] = set()
    for match in _URL_RE.findall(text):
        urls.add(match.rstrip(_URL_TRAILING))
    return urls


def mark_delivered(
    new_envelope: dict[str, Any], briefing_text: str
) -> tuple[int, int, int, int]:
    """Mark seen every URL extracted from the delivered `briefing_text`.

    URLs whose hash matches an item in `new_envelope` are recorded with that
    item's category (`arxiv`, `youtube`, ...). URLs in the brief that do not
    match any envelope item are recorded with category `web` so the synthesis
    deny-list can include `web_search`-sourced URLs on subsequent runs.

    Returns (matched, web, newly_recorded, dropped):
      matched         envelope items whose URL appears in briefing_text
      web             URLs in briefing_text that were NOT in new_envelope
      newly_recorded  rows actually inserted (matched + web, minus already-seen)
      dropped         envelope items NOT in briefing_text (synthesis filtered them)
    """
    init_db()
    delivered_urls = _extract_urls(briefing_text)
    delivered_hashes = {url_hash(u) for u in delivered_urls}

    matched_items: list[dict[str, Any]] = []
    matched_hashes: set[str] = set()
    dropped = 0
    for item in new_envelope.get("items", []) or []:
        url = (item.get("url") or "").strip()
        if not url:
            continue
        h = url_hash(url)
        if h in delivered_hashes:
            matched_items.append(item)
            matched_hashes.add(h)
        else:
            dropped += 1

    # Web items: every brief URL whose hash didn't match an envelope item.
    # Synthesise minimal items so mark_seen records them with category=web.
    web_items: list[dict[str, Any]] = [
        {"id": "web:url", "url": u}
        for u in sorted(delivered_urls)
        if url_hash(u) not in matched_hashes
    ]

    newly_recorded = mark_seen({"items": matched_items + web_items})
    return len(matched_items), len(web_items), newly_recorded, dropped


def export_seen_recent(out_path: str, days: int) -> int:
    """Write a flat list of URLs seen within the last `days` to `out_path`.

    One URL per line, sorted, no header. Rows whose `url` is empty (legacy
    rows recorded before the schema gained the column) are skipped — they
    cannot reach the prompt as a deny-list anyway.

    Returns the number of URLs written.
    """
    init_db()
    cutoff = (
        dt.datetime.now(tz=dt.timezone.utc) - dt.timedelta(days=days)
    ).isoformat().replace("+00:00", "Z")
    with _connect() as conn:
        rows = conn.execute(
            "SELECT url FROM seen WHERE first_seen >= ? AND url != '' ORDER BY url",
            (cutoff,),
        ).fetchall()
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for (u,) in rows:
            f.write(u + "\n")
    return len(rows)


def _load_envelopes_from_paths(paths: list[str]) -> list[dict[str, Any]]:
    envelopes: list[dict[str, Any]] = []
    for path in paths:
        with open(path, "r", encoding="utf-8") as f:
            envelopes.append(json.load(f))
    return envelopes


def _load_envelope_from_path_or_stdin(path: str | None) -> dict[str, Any]:
    if path is None or path == "-":
        return json.load(sys.stdin)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jarvis.state")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init-db", help="Create the seen.sqlite database if missing")

    p_dedupe = sub.add_parser(
        "dedupe",
        help="Read fetcher envelopes; emit a single envelope of new items.",
    )
    p_dedupe.add_argument("paths", nargs="+", help="Fetcher envelope JSON paths")

    p_mark = sub.add_parser(
        "mark-seen",
        help="Record items from an envelope as seen.",
    )
    p_mark.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Envelope JSON path; reads stdin if omitted or '-'.",
    )

    p_delivered = sub.add_parser(
        "mark-delivered",
        help="Mark seen only items in --new whose URL appears in --briefing.",
    )
    p_delivered.add_argument(
        "--new",
        dest="new_path",
        required=True,
        help="Path to the dedupe envelope (typically /tmp/raw/new.json).",
    )
    p_delivered.add_argument(
        "--briefing",
        dest="briefing_path",
        required=True,
        help="Path to the briefing markdown delivered to the user.",
    )

    p_export = sub.add_parser(
        "export-seen-recent",
        help="Write the recently-seen URL deny-list to disk.",
    )
    p_export.add_argument(
        "--days",
        type=int,
        default=14,
        help="Lookback window in days (default 14).",
    )
    p_export.add_argument(
        "--out",
        dest="out_path",
        required=True,
        help="Output path (one URL per line, sorted, no header).",
    )

    args = parser.parse_args(argv)

    if args.cmd == "init-db":
        init_db()
        return 0

    if args.cmd == "dedupe":
        envelopes = _load_envelopes_from_paths(args.paths)
        result = dedupe(envelopes)
        json.dump(result, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    if args.cmd == "mark-seen":
        envelope = _load_envelope_from_path_or_stdin(args.path)
        n = mark_seen(envelope)
        print(f"[state] marked {n} item(s) as seen", file=sys.stderr)
        return 0

    if args.cmd == "mark-delivered":
        with open(args.new_path, "r", encoding="utf-8") as f:
            new_envelope = json.load(f)
        with open(args.briefing_path, "r", encoding="utf-8") as f:
            briefing_text = f.read()
        matched, web, newly, dropped = mark_delivered(new_envelope, briefing_text)
        print(
            f"[state] delivered={matched}+{web}web (newly recorded {newly}), "
            f"dropped={dropped} not-in-briefing",
            file=sys.stderr,
        )
        return 0

    if args.cmd == "export-seen-recent":
        n = export_seen_recent(args.out_path, args.days)
        print(
            f"[state] exported {n} url(s) to {args.out_path} "
            f"(window: last {args.days} days)",
            file=sys.stderr,
        )
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
