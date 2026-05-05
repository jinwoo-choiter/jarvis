## ADDED Requirements

### Requirement: run.sh is the single entry point

The repository SHALL provide an executable `run.sh` at the root that performs the entire daily pipeline. Cron and manual debugging SHALL both invoke it the same way: `bash run.sh` (or by absolute path). The script MUST be self-contained: no arguments are required for the default daily run.

#### Scenario: Manual end-to-end run

- **WHEN** a user runs `bash run.sh` from the repository root with `.env` and `*.local.*` configured
- **THEN** the pipeline executes fetchers, dedupe, synthesis, delivery, and mark-seen, and a Slack message arrives in the configured channel

#### Scenario: Cron run uses the same entry point

- **WHEN** the user's crontab invokes `run.sh` by absolute path
- **THEN** the pipeline executes identically to a manual run, with no special-case branches in the script

### Requirement: Step ordering and intermediate artifacts on disk

`run.sh` SHALL execute the following steps in order: (1) run each configured fetcher and write its JSON output to `/tmp/raw/<source>.json`; (2) run dedupe over the combined fetcher output to produce `/tmp/raw/new.json`; (3) invoke `claude -p` with the prompt body and `--add-dir /tmp/raw`, redirecting stdout to `/tmp/briefing.md`; (4) invoke the delivery module against `/tmp/briefing.md`; (5) on delivery success only, invoke mark-seen with the items present in `/tmp/raw/new.json`.

#### Scenario: Intermediate artifacts are inspectable

- **WHEN** any step in `run.sh` completes
- **THEN** its output file under `/tmp/raw/` or `/tmp/briefing.md` exists on disk and can be inspected by the user

#### Scenario: Steps run in the documented order

- **WHEN** any reviewer reads `run.sh`
- **THEN** the five steps appear in the order specified above

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
