## Purpose

Interactive `init` script that captures secrets into `.env` and verifies them against the live services where feasible, replacing manual template-copy steps with a single scripted entry point.

## Requirements

### Requirement: Init script entry point

The repository SHALL ship an executable bash script at `scripts/init.sh` that captures the project's secrets into a fresh `.env` file. The script MUST be invocable as `bash scripts/init.sh` from the repository root without prior installation of any project dependency (no `.venv`, no `pip install`).

#### Scenario: Init runs on a fresh clone

- **WHEN** a user clones the repository and runs `bash scripts/init.sh` before any other setup step
- **THEN** the script executes without ImportError, ModuleNotFoundError, or missing-binary errors and proceeds into its prompt sequence

### Requirement: Variable discovery from `.env.example`

The init script SHALL determine the set of variables to prompt for by parsing `.env.example`. For each `KEY=` line in `.env.example`, the script SHALL prompt the user for the value of that key. Comment lines (lines beginning with `#`) immediately preceding a `KEY=` line SHALL be displayed as the prompt's help text. The script MUST NOT hardcode the variable list.

#### Scenario: Adding a new variable requires only an `.env.example` edit

- **GIVEN** `.env.example` lists `SLACK_WEBHOOK_URL` and `YOUTUBE_API_KEY`
- **WHEN** a future contributor appends a new `# description` and `NEW_KEY=` line to `.env.example` and runs the init script
- **THEN** the script prompts for `NEW_KEY` with the new comment as help text, without any modification to `scripts/init.sh`

#### Scenario: Malformed `.env.example` aborts cleanly

- **WHEN** `.env.example` contains a non-blank, non-comment line that is not a `KEY=` assignment
- **THEN** the script exits non-zero with a diagnostic naming the offending line and writes nothing to `.env`

### Requirement: Refusal to overwrite existing `.env`

The init script SHALL detect when an `.env` file already exists at the repository root and SHALL NOT silently overwrite it. The script MUST prompt the user to confirm the destructive action before proceeding, and MUST exit zero without modification if the user declines.

#### Scenario: Existing `.env` blocks silent overwrite

- **GIVEN** `.env` already exists with values from a previous setup
- **WHEN** the user runs `bash scripts/init.sh`
- **THEN** the script prints a warning that includes the path to the existing file and asks for explicit confirmation before any prompt or write

#### Scenario: User declines confirmation

- **GIVEN** `.env` already exists and the user has been prompted to confirm overwrite
- **WHEN** the user enters anything other than an explicit affirmative
- **THEN** the script exits zero and the existing `.env` is unchanged

### Requirement: Secure file permissions on `.env`

After writing `.env`, the init script SHALL apply mode `0600` to the file so that read and write access is restricted to the file's owner.

#### Scenario: Permissions are tightened on write

- **WHEN** the init script completes successfully and `.env` is created
- **THEN** `stat` reports the permission bits of `.env` as `-rw-------`

### Requirement: Optional Slack webhook smoke test

After the user provides values, the init script SHALL offer a single confirmation prompt to post a labeled setup notice to Slack via the webhook URL just entered. The prompt MUST default to "yes". If the user accepts, the script MUST POST a message clearly identifying itself (e.g., prefixed with `[JARVIS init]`) and MUST surface any non-2xx response as an error before exiting. Declining the smoke test MUST NOT cause a non-zero exit.

#### Scenario: Smoke test confirms a valid webhook

- **GIVEN** the user has just entered a valid `SLACK_WEBHOOK_URL`
- **WHEN** the user accepts the smoke-test prompt
- **THEN** the script posts a single labeled message to that webhook, prints a success line on stdout, and exits zero

#### Scenario: Smoke test surfaces a typo

- **GIVEN** the user entered a `SLACK_WEBHOOK_URL` that points to a revoked or non-existent webhook
- **WHEN** the user accepts the smoke-test prompt
- **THEN** the script prints the HTTP status and response body to stderr and exits non-zero so the user notices at setup time rather than at the next scheduled run

#### Scenario: User declines the smoke test

- **GIVEN** the user has just entered values
- **WHEN** the user declines the smoke-test prompt
- **THEN** the script writes `.env`, sets its permissions, prints a confirmation line, and exits zero
