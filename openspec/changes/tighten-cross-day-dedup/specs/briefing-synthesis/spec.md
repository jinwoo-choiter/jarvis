## ADDED Requirements

### Requirement: Cross-day deny-list and brief-context inputs

The prompt SHALL instruct synthesis to read two additional inputs from the directory exposed via `--add-dir`:

- `seen_recent.txt` — a flat list of URLs already delivered within the last `dedup.recent_days` days. Used as a strict deny-list for `web_search` results.
- `recent_briefs/*.md` — the most recent `dedup.recent_briefs_count` archived briefings. Used to recognise same-event-different-source duplication.

The prompt MUST direct synthesis to treat `recent_briefs/` content as context for cross-day duplicate-detection only — items in those briefings are NOT to be surfaced as fresh content.

#### Scenario: URL in deny-list is dropped from web_search results

- **GIVEN** `seen_recent.txt` contains `https://example.com/article-x`
- **WHEN** synthesis runs and `web_search` returns an item with that URL
- **THEN** the briefing does not contain that item

#### Scenario: Same event from different source is dropped or downgraded

- **GIVEN** `recent_briefs/2026-05-06.md` already contains an entry about "Walt Disney World Mandalorian / Grogu mission opening 2026-05-22" sourced from `disneyparksblog.com`
- **WHEN** synthesis runs and `web_search` returns a different article from `thepointsguy.com` covering the same event with no new development
- **THEN** the briefing does not contain that article

#### Scenario: Same event with new development surfaces as follow-up

- **GIVEN** `recent_briefs/` already covers a Disney attraction opening on a specific date
- **WHEN** synthesis runs and `web_search` returns an article reporting that the date has shifted
- **THEN** the briefing surfaces the update as a `[update]`-prefixed entry that cites the new development, not as if the original were never reported

#### Scenario: Recent briefings are not re-surfaced as fresh items

- **WHEN** synthesis reads `recent_briefs/*.md`
- **THEN** items appearing in those files are not re-emitted as new entries in today's briefing

## MODIFIED Requirements

### Requirement: Priority-marker caps

The prompt SHALL cap output volume to keep the daily briefing length predictable: at most one 🔥 (top item) per day, at most five 📌 (notable items) per day, AND at most five plain (no-marker) items per day. The total ceiling is eleven items per briefing.

#### Scenario: Top-item cap is enforced

- **WHEN** synthesis identifies more than one candidate top item
- **THEN** the briefing contains at most one 🔥 marker

#### Scenario: Notable cap is enforced

- **WHEN** synthesis identifies more than five candidate notable items
- **THEN** the briefing contains at most five 📌 markers, and the rest are demoted or omitted

#### Scenario: Plain-item cap is enforced

- **WHEN** synthesis identifies more than five candidate plain items
- **THEN** the briefing contains at most five plain entries, and the rest are omitted

#### Scenario: Total ceiling is respected

- **WHEN** synthesis runs on a day with abundant fetcher and web_search material
- **THEN** the briefing contains no more than eleven items in total across all markers

### Requirement: Duplicate-event consolidation

The prompt SHALL instruct synthesis to suppress duplicates along two axes: (a) within the current run, multiple sources reporting the same underlying event MUST be merged into a single briefing entry citing the most primary source; (b) across recent runs, an item whose URL appears in `seen_recent.txt` MUST be dropped silently, and an item whose underlying event already appears in `recent_briefs/*.md` MUST be dropped unless there is genuinely new development, in which case it surfaces as a `[update]`-prefixed follow-up.

#### Scenario: Same event covered by multiple outlets in one run

- **GIVEN** three news items in today's input cover the same product launch
- **WHEN** synthesis runs
- **THEN** the briefing contains one consolidated entry for that launch, with the most primary source URL

#### Scenario: URL already in deny-list

- **GIVEN** a URL appears in `seen_recent.txt`
- **WHEN** `web_search` returns an item with that URL today
- **THEN** the briefing does not contain that item, with no explanatory note

#### Scenario: Event already covered yesterday from a different source

- **GIVEN** yesterday's briefing in `recent_briefs/` covered an event with one URL
- **WHEN** today's `web_search` finds a different URL covering the same event with no new development
- **THEN** the briefing does not contain today's item

#### Scenario: Event has new development since prior coverage

- **GIVEN** yesterday's briefing covered an event
- **WHEN** today's `web_search` finds an item reporting a date shift, price change, or status change for that event
- **THEN** the briefing contains a `[update]` entry that names the development and cites the new source
