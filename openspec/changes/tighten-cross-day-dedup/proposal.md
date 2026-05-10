## Why

Five days of cron-driven briefings have surfaced two concrete dedup gaps that produce visible cross-day repetition. (1) `mark-delivered` only records URLs from items that came through the deterministic fetcher path — every URL surfaced via the synthesis prompt's `web_search` branch is silently *not* recorded, so the same `web_search`-found URL is freshly rediscovered on subsequent days and re-included. (2) Even when the URL itself is recorded, there is no event-level identity, so an article from a different source covering the same event (e.g., the Walt Disney World "Mandalorian / Grogu mission, May 22" item appearing on 5/6 from `disneyparksblog.com` and again on 5/10 from `thepointsguy.com`) passes URL-keyed dedup and re-appears.

Fixing both gaps without introducing a fragile event-identity scheme: extend `mark-delivered` to record every URL in the briefing (not just the fetcher subset), feed the recently-seen URL set back into the synthesis prompt as a deny-list, and additionally hand the model the last fourteen days of delivered briefings as context so it can recognise same-event-different-source duplication the way a human would. Tighten the priority caps slightly so the daily output length is more stable.

## What Changes

- **BREAKING (data)**: `mark-delivered` records every URL extracted from the delivered brief, not just URLs whose item appears in the dedupe envelope. The `seen.sqlite` `category` column gains a sentinel value `"web"` for URLs that were not in any fetcher envelope.
- Add a per-run pre-synthesis export step: `jarvis.state` emits `/tmp/raw/seen_recent.txt`, a plain-text list of all URLs marked seen within the last `dedup.recent_days` days (default 14). The synthesis prompt reads it via `--add-dir` and treats it as a deny-list for `web_search` results.
- Add a per-run brief-archival step: on a successful delivery, `run.sh` copies `/tmp/briefing.md` to `state/briefings/<YYYY-MM-DD>.md`. The directory is gitignored.
- Add a per-run pre-synthesis brief-context step: `run.sh` copies the most recent `dedup.recent_briefs_count` archived briefings (default 14) into `/tmp/raw/recent_briefs/`. The synthesis prompt reads them via `--add-dir` and uses them to recognise same-event-different-source duplication.
- Update `prompts/daily_brief.md` §0 (Read first) to enumerate the two new inputs (`seen_recent.txt`, `recent_briefs/`) and §3 (Consolidate duplicates) to apply both as cross-day filters: drop any `web_search` result whose URL appears in `seen_recent.txt`; for results whose URL does not appear there, drop or downgrade them when `recent_briefs/` already covers the same underlying event.
- Tighten priority caps in §4: cap *plain* (no-marker) items at five per brief in addition to the existing 🔥 (one) and 📌 (five) caps. Total ceiling per brief: eleven items.
- Add a small `dedup` block to `config.yaml` for the two tunables (`recent_days`, `recent_briefs_count`).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `seen-tracking`: `mark-delivered` widens its scope to every URL in the brief and gains an explicit `web` category for non-fetcher items; a new operation exports a recent-URL list for downstream consumers.
- `briefing-synthesis`: prompt now reads two additional inputs (`seen_recent.txt`, `recent_briefs/`) and applies both as cross-day dedup filters; priority caps add a plain-item ceiling.
- `pipeline-orchestration`: `run.sh` archives the brief and stages the recent-briefs context window before each synthesis call.

## Impact

- **Code**: `jarvis/state.py` (mark_delivered widening, new `export-seen-recent` subcommand). `jarvis/_config.py` no change (new `dedup` block is read implicitly by callers). `prompts/daily_brief.md` §0/§3/§4. `run.sh` (archive + recent_briefs staging). `config.yaml` (new `dedup` block). `.gitignore` (`state/briefings/`).
- **Data**: existing `seen.sqlite` migrates forward in place — `web` category writes are additive, no schema change. Existing rows untouched.
- **Storage**: `state/briefings/` accumulates one ~2–4 KB markdown per day. At one year that is ~1 MB; bounded growth, gitignored, no concern.
- **Token cost**: synthesis prompt now reads up to fourteen days of past briefs (~50 KB) plus a deny-list (~5–10 KB) into context. Marginal cost remains within Claude Max free-tier headroom; cron-run latency unchanged in practice.
- **Forker experience**: no manual setup change. `state/briefings/` is created on first successful run; `seen_recent.txt` is regenerated each run.
- **Observable change**: the cross-day repetitions visible 5/5 → 5/10 (Soarin', MM Falcon, WDW seven-attractions wave) stop showing up under different URLs after this lands. Brief length stabilises around six to eleven items per day.
