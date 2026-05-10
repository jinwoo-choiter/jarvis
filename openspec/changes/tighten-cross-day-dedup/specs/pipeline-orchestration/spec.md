## ADDED Requirements

### Requirement: Brief archival on successful delivery

`run.sh` SHALL copy the delivered briefing artifact to `state/briefings/<YYYY-MM-DD>.md` after a successful Slack delivery, using today's date in the user's local timezone for the filename. The archival MUST run before mark-delivered so that the brief is durably preserved even if mark-delivered fails. If the archive directory does not exist, `run.sh` MUST create it. If a file with today's date already exists (e.g., manual re-run on the same day), `run.sh` MUST overwrite it.

#### Scenario: First successful run on a given day

- **GIVEN** `state/briefings/` does not yet exist
- **WHEN** `run.sh` completes a successful delivery on 2026-05-11
- **THEN** the directory is created and `state/briefings/2026-05-11.md` exists with byte-identical content to `/tmp/briefing.md`

#### Scenario: Manual re-run on the same day

- **GIVEN** `state/briefings/2026-05-11.md` already exists from an earlier run on the same day
- **WHEN** `run.sh` completes a second successful delivery on 2026-05-11
- **THEN** the file is overwritten with the second brief's content

#### Scenario: Archive directory is gitignored

- **WHEN** any reviewer inspects `.gitignore`
- **THEN** `state/briefings/` is listed and `git status` does not show files inside it after a pipeline run

### Requirement: Synthesis context staging

`run.sh` SHALL stage two cross-day context inputs into `/tmp/raw/` before invoking `claude -p`:

- `/tmp/raw/seen_recent.txt` — produced by `python -m jarvis.state export-seen-recent --days <dedup.recent_days> --out /tmp/raw/seen_recent.txt`.
- `/tmp/raw/recent_briefs/` — populated by copying the most recent `dedup.recent_briefs_count` files from `state/briefings/` into the staging directory.

If `state/briefings/` is empty (first ever run), `/tmp/raw/recent_briefs/` MAY be absent or empty; the synthesis call MUST still succeed.

#### Scenario: Staging on day one

- **GIVEN** the system has just been deployed and `state/briefings/` is empty
- **WHEN** `run.sh` invokes the synthesis stage
- **THEN** `/tmp/raw/seen_recent.txt` exists (possibly empty), `/tmp/raw/recent_briefs/` exists (empty), and `claude -p` runs without error

#### Scenario: Staging after several days

- **GIVEN** `state/briefings/` contains 21 dated briefings and `dedup.recent_briefs_count = 14`
- **WHEN** `run.sh` invokes the synthesis stage
- **THEN** `/tmp/raw/recent_briefs/` contains exactly the 14 most recent briefings by date, copied from `state/briefings/`

## MODIFIED Requirements

### Requirement: Step ordering and intermediate artifacts on disk

`run.sh` SHALL execute the following steps in order:

1. Run each configured fetcher and write its JSON output to `/tmp/raw/<source>.json`.
2. Run dedupe over the combined fetcher output to produce `/tmp/raw/new.json`.
3. Stage cross-day context: export the seen-URL deny-list to `/tmp/raw/seen_recent.txt` and copy the most recent archived briefings to `/tmp/raw/recent_briefs/`.
4. Invoke `claude -p` with the prompt body and `--add-dir /tmp/raw`, redirecting stdout to `/tmp/briefing.md`.
5. Invoke the delivery module against `/tmp/briefing.md`.
6. On delivery success only: archive the brief to `state/briefings/<YYYY-MM-DD>.md`.
7. On delivery success only: invoke `mark-delivered` against `/tmp/raw/new.json` and `/tmp/briefing.md`.

#### Scenario: Intermediate artifacts are inspectable

- **WHEN** any step in `run.sh` completes
- **THEN** its output file under `/tmp/raw/` (including `seen_recent.txt` and `recent_briefs/`) or `/tmp/briefing.md` exists on disk and can be inspected

#### Scenario: Steps run in the documented order

- **WHEN** any reviewer reads `run.sh`
- **THEN** the seven steps appear in the order specified above

#### Scenario: A failed delivery skips both archive and mark-delivered

- **WHEN** the delivery step exits non-zero
- **THEN** neither the brief archive nor `mark-delivered` runs, and `state/briefings/` and `state/seen.sqlite` are unchanged for the failed run
