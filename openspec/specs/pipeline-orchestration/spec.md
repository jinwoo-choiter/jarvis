## Purpose

How the daily run sequences fetch → dedupe → stage-context → synthesize → deliver → archive → mark-seen, including failure semantics and idempotent re-runs.

## Requirements

### Requirement: run.sh is the single entry point

The repository SHALL provide an executable `run.sh` at the root that performs the entire daily pipeline. Cron and manual debugging SHALL both invoke it the same way: `bash run.sh` (or by absolute path). The script MUST be self-contained: no arguments are required for the default daily run.

#### Scenario: Manual end-to-end run

- **WHEN** a user runs `bash run.sh` from the repository root with `.env` and `*.local.*` configured
- **THEN** the pipeline executes fetchers, dedupe, synthesis, delivery, and mark-seen, and a Slack message arrives in the configured channel

#### Scenario: Cron run uses the same entry point

- **WHEN** the user's crontab invokes `run.sh` by absolute path
- **THEN** the pipeline executes identically to a manual run, with no special-case branches in the script

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

### Requirement: Environment loading

`run.sh` SHALL explicitly source `.env` (or otherwise load it into the process environment) before invoking any step that needs credentials. The script MUST NOT rely on the user's interactive shell environment being inherited.

#### Scenario: Cron has no inherited shell environment

- **WHEN** `run.sh` runs from cron in a minimal environment
- **THEN** it loads `.env` itself, and steps such as YouTube fetching and Slack delivery find their required variables

#### Scenario: Missing .env fails fast with a clear message

- **WHEN** `run.sh` runs without a `.env` file present
- **THEN** the script exits non-zero with a stderr message naming `.env` as the missing prerequisite

### Requirement: Failure isolation between steps

`run.sh` SHALL ensure that a failure in any single step does not silently mark items as seen. In particular, mark-seen MUST be skipped if any of fetchers, dedupe, synthesis, or delivery fails. Logging MUST capture the failure so the user can diagnose it later.

#### Scenario: Synthesis fails

- **WHEN** the synthesis step exits non-zero
- **THEN** delivery is not attempted, mark-seen is skipped, and the failure is recorded in `run.log`

#### Scenario: Delivery fails

- **WHEN** delivery exits non-zero
- **THEN** mark-seen is skipped and the failure is recorded in `run.log`

### Requirement: Operational logging

`run.sh` SHALL append a timestamped log line for each major step start and completion, plus any failure detail, to `run.log` at the repository root. `run.log` MUST be gitignored.

#### Scenario: Log captures a successful run

- **WHEN** `run.sh` completes successfully
- **THEN** `run.log` contains timestamped entries marking the start and completion of fetchers, dedupe, synthesis, delivery, and mark-seen

#### Scenario: Log captures a failure

- **WHEN** any step in `run.sh` fails
- **THEN** `run.log` contains a timestamped entry naming the failed step and a short diagnostic

### Requirement: Cron-registration documentation

The README SHALL document the recommended cron entry (default `0 7 * * *`) and the steps to register it via `crontab -e`. v1 MUST NOT auto-register cron.

#### Scenario: User finds cron instructions in the README

- **WHEN** a user reads the README's "scheduling" section
- **THEN** the section provides a copy-pasteable cron line and a one-line `crontab -e` instruction

#### Scenario: No automatic registration

- **WHEN** any reviewer inspects the repository
- **THEN** no installer, post-install hook, or `run.sh` branch attempts to write to the user's crontab automatically

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
