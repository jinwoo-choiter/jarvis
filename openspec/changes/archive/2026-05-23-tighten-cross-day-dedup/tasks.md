## 1. State module changes

- [x] 1.1 Widen `mark_delivered` in `jarvis/state.py`: in addition to the existing fetcher-matching loop, extract every URL from the briefing text and insert each non-matching URL into the seen store with `category = "web"`. Reuse `url_hash` so the canonicalisation matches the fetcher path. Keep the (matched, newly_recorded, dropped) return tuple semantics; add a fourth element for the count of `web`-category rows recorded, and update the CLI status line accordingly.
- [x] 1.2 Add `export_seen_recent` to `jarvis/state.py`: query the seen store for `first_seen >= now - days`, emit each URL on its own line to a path supplied via `--out`, sorted, no header. Reverse-map URL hash → URL by storing the URL text on insert (extend the schema), or by re-deriving from the brief — pick one approach and document it in the design rationale.
- [x] 1.3 Add the `export-seen-recent` subcommand to `jarvis/state.py` argparse: `--days INT` (defaults to `dedup.recent_days` from `config.yaml`, falling back to 14), `--out PATH` (required).
- [x] 1.4 Update the module docstring at the top of `jarvis/state.py` to list the new subcommand and the `web` category sentinel.

## 2. Schema migration for URL recovery

- [x] 2.1 Decide and document: store the original URL alongside `url_hash` in the seen store (extend schema) versus re-derive at export time (parse the most-recent N briefings and back-fill from there). Default: extend the schema with a `url TEXT NOT NULL` column.
- [x] 2.2 If the schema is extended, write a small inline migration in `init_db`: check if the `url` column exists; if not, `ALTER TABLE seen ADD COLUMN url TEXT NOT NULL DEFAULT ''`. Existing 96 rows will have empty `url` strings — acceptable, the export operation just skips empty-url rows.
- [x] 2.3 Update `mark_seen` (called by `mark_delivered`) to populate `url` on insert.

## 3. Config block

- [x] 3.1 Add a `dedup` block to `config.yaml` with `recent_days: 14` and `recent_briefs_count: 14`, and inline comments explaining the role of each.

## 4. Synthesis prompt updates

- [x] 4.1 Update `prompts/daily_brief.md` §0 (Read first) to enumerate two new inputs from `--add-dir`: `seen_recent.txt` (URL deny-list) and `recent_briefs/*.md` (cross-day duplicate-detection context). Add an explicit note that `recent_briefs/` content MUST NOT be re-surfaced as fresh items.
- [x] 4.2 Update §3 (Consolidate duplicates) with the two cross-day clauses: drop on URL-match against `seen_recent.txt`; drop on event-match against `recent_briefs/` unless there is a date / price / status change, in which case surface as `[update]`-prefixed follow-up.
- [x] 4.3 Update §4 (Prioritize) to add a third cap: at most five plain (no-marker) items per brief, total ceiling eleven.

## 5. Orchestrator updates

- [x] 5.1 In `run.sh`, after dedupe and before synthesis, add a "stage cross-day context" step: run `jarvis.state export-seen-recent` to write `/tmp/raw/seen_recent.txt`; create `/tmp/raw/recent_briefs/` and copy the most recent `dedup.recent_briefs_count` files from `state/briefings/` into it (handle the empty-archive case gracefully).
- [x] 5.2 In `run.sh`, after `STEP delivery done` and *before* `STEP mark-seen start`, add a "STEP archive-brief" step: `mkdir -p state/briefings && cp /tmp/briefing.md state/briefings/$(date '+%Y-%m-%d').md`. Log success and failure; failure to archive MUST NOT block mark-delivered.
- [x] 5.3 Read `dedup.recent_days` and `dedup.recent_briefs_count` from `config.yaml` at the top of `run.sh` (small Python one-liner via `.venv/bin/python -c "import yaml..."` is fine) and pass them as arguments where needed.

## 6. Gitignore

- [x] 6.1 Add `state/briefings/` to `.gitignore`.

## 7. README

- [x] 7.1 Add a short "Brief archive" subsection under "How it works" describing `state/briefings/` (one file per day, gitignored, plain markdown) and the `dedup` config block.

## 8. Smoke test

- [x] 8.1 Manually run `bash run.sh` once after the implementation lands. Verify (a) `/tmp/raw/seen_recent.txt` is populated, (b) `state/briefings/<today>.md` is created and matches `/tmp/briefing.md`, (c) `seen.sqlite` gains rows with `category = "web"` for any web-source URL in the brief, (d) the brief opens with 🎩 and ends with the closer, and (e) the brief contains no more than eleven items in total.
- [x] 8.2 On the *next* day's cron run, inspect the brief for cross-day repetition. Compare against the previous day's archive in `state/briefings/`. Expect zero exact-URL repetition. Note any same-event-different-source cases that slipped through; if more than one per week, the prompt's §3 wording is the first lever to tighten.
