## ADDED Requirements

### Requirement: Recent-URL export for downstream consumers

The seen store SHALL provide an export operation that writes a plain-text list of URLs marked seen within the last `dedup.recent_days` days (default 14, read from `config.yaml`) to a path supplied on the command line. The output MUST contain one URL per line, sorted, with no header. The orchestrator SHALL invoke this export to stage `/tmp/raw/seen_recent.txt` before each synthesis call so the synthesis prompt can read it as a deny-list for `web_search` results.

#### Scenario: Export emits one URL per line

- **WHEN** the user runs `python -m jarvis.state export-seen-recent --days 14 --out /tmp/raw/seen_recent.txt`
- **THEN** the output file contains every URL whose `first_seen` timestamp falls within the last 14 days, one URL per line, sorted, with no JSON envelope or header

#### Scenario: Export honours the recent_days window

- **GIVEN** the seen store contains URLs first seen 1, 7, 14, and 21 days ago
- **WHEN** the export runs with `--days 14`
- **THEN** the output contains the URLs from 1, 7, and 14 days ago and excludes the URL from 21 days ago

#### Scenario: Export is invoked before each synthesis run

- **WHEN** the orchestrator runs the daily pipeline
- **THEN** `/tmp/raw/seen_recent.txt` exists before `claude -p` is invoked, with the directory exposed via `--add-dir`

## MODIFIED Requirements

### Requirement: Mark-seen runs only after successful delivery

The system SHALL record URL hashes in the seen store only after the Slack delivery step has completed successfully. The set of URLs to record on a successful delivery MUST be the set of every URL extracted from the delivered briefing text, not only URLs that came through the dedupe envelope. URLs whose hash matches an item in the dedupe envelope SHALL be recorded with that item's category (`arxiv`, `youtube`, etc.); URLs in the brief that do not match any envelope item SHALL be recorded with category `web`.

If delivery fails or is skipped, the seen store MUST remain unchanged so the next run can retry the same items.

#### Scenario: Delivery succeeds with mixed-source brief

- **GIVEN** the delivered briefing contains five URLs: two whose hashes match arXiv items in `new.json`, and three discovered by `web_search` whose hashes do not match any envelope item
- **WHEN** the orchestrator invokes mark-delivered with the new envelope and the briefing text
- **THEN** the seen store contains five new rows: two with `category = "arxiv"`, three with `category = "web"`, all with the current timestamp

#### Scenario: Delivery fails

- **WHEN** Slack delivery returns a non-success exit code
- **THEN** the orchestrator does not invoke mark-delivered, and the seen store contains no records for items in the failed run

#### Scenario: Retry on next run delivers the same items

- **GIVEN** a previous run failed before mark-delivered executed
- **WHEN** the next run executes
- **THEN** dedupe still considers the previously-undelivered fetcher items as new, the deny-list does not yet include the previously-undelivered web_search URLs, and both paths re-include those items in synthesis input
