## ADDED Requirements

### Requirement: Tracked configuration with secrets in environment

The system SHALL keep all non-secret configuration in committed files and SHALL keep secrets in an `.env` file that is gitignored. The committed configuration files MUST be `config.yaml` (data sources, search themes, scheduling, windows) and `profile.yaml` (the user's role, priority keywords, upcoming events, output language). Secrets MUST be limited to credentials that grant external access — at present the Slack incoming-webhook URL and the YouTube Data API key. The repository SHALL ship `.env.example` as a documented manifest of expected environment variables, with one `KEY=` line per variable and a leading `#` comment on each describing its purpose.

#### Scenario: Pipeline reads only the tracked config files

- **WHEN** the pipeline runs in a working tree where `config.local.yaml` and `profile.local.yaml` do not exist
- **THEN** every fetcher and the synthesis prompt operate on `config.yaml` and `profile.yaml` and the run completes successfully

#### Scenario: Secrets are not in any tracked file

- **WHEN** any reviewer inspects every committed file in the repository
- **THEN** no real Slack webhook URL, no real YouTube API key, and no other credential value appears anywhere outside `.env.example`'s placeholder positions

#### Scenario: `.env.example` is well-formed

- **WHEN** any reviewer reads `.env.example`
- **THEN** every line is either blank, a `#`-prefixed comment, or a `KEY=` assignment with an empty or placeholder value

## MODIFIED Requirements

### Requirement: Project directory layout

The repository SHALL contain the following committed top-level structure: a `jarvis/` Python package (with a `fetchers/` subpackage, `state.py`, `deliver.py`), a `prompts/` directory, a `samples/` directory, a `scripts/` directory, a `state/` directory containing only a `.gitkeep`, a `run.sh` entry point, a `pyproject.toml` manifest, a `README.md`, a `LICENSE` file, and the configuration files defined in the tracked-configuration requirement above.

#### Scenario: Fresh clone exposes the layout

- **WHEN** a user clones the repository
- **THEN** the working tree contains `jarvis/__init__.py`, `jarvis/fetchers/__init__.py`, `jarvis/fetchers/arxiv.py`, `jarvis/fetchers/youtube.py`, `jarvis/state.py`, `jarvis/deliver.py`, `prompts/daily_brief.md`, `samples/example_briefing.md`, `scripts/init.sh`, `state/.gitkeep`, `run.sh`, `config.yaml`, `profile.yaml`, `.env.example`, `pyproject.toml`, `README.md`, and `LICENSE`

#### Scenario: State directory is preserved but empty

- **WHEN** a user clones the repository
- **THEN** `state/` exists, contains only `.gitkeep`, and `state/seen.sqlite` is absent from the working tree

### Requirement: gitignore covers all secret-bearing and ephemeral paths

The committed `.gitignore` SHALL list at minimum: `.env`, `state/seen.sqlite`, `run.log`, `__pycache__/`, `.venv/`, `/tmp/raw/`, and `/tmp/briefing.md`. The gitignore SHALL NOT list `config.yaml`, `profile.yaml`, or any `*.local.*` pattern.

#### Scenario: Secrets file is not tracked

- **WHEN** a user populates `.env` with their Slack webhook URL and YouTube API key
- **THEN** `git status` does not list `.env`

#### Scenario: Tracked config files are tracked

- **WHEN** a user edits `config.yaml` or `profile.yaml` to their own values
- **THEN** `git status` lists the edits as modifications and `git add` stages them normally

#### Scenario: Generated state and ephemeral artifacts are not tracked

- **WHEN** a pipeline run produces `state/seen.sqlite`, `run.log`, `/tmp/raw/*.json`, or `/tmp/briefing.md`
- **THEN** none of these paths are reported by `git status`

## REMOVED Requirements

### Requirement: Two-tier configuration layering

**Reason**: The two-tier model (committed `*.example` templates plus gitignored `*.local.*` overrides) is replaced by a single-tier model in which non-secret configuration is committed directly and secrets live in `.env`. The maintainer is comfortable with their non-secret configuration being public and the layered model imposed manual setup overhead and cost the maintainer's own configuration its version history.

**Migration**: Replaced by the "Tracked configuration with secrets in environment" requirement above. Existing `config.local.yaml` and `profile.local.yaml` content is migrated into the new committed `config.yaml` and `profile.yaml` as part of this change. After the change lands, the gitignored local files are inert and may be deleted by the maintainer.
