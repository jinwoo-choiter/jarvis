## Purpose

The committed project layout, the single-tier configuration model (non-secret config tracked in git, secrets in `.env`), and gitignore guarantees that keep this repository safe to fork in public.

## Requirements

### Requirement: Project directory layout

The repository SHALL contain the following committed top-level structure: a `jarvis/` Python package (with a `fetchers/` subpackage, `state.py`, `deliver.py`), a `prompts/` directory, a `samples/` directory, a `scripts/` directory, a `state/` directory containing only a `.gitkeep`, a `run.sh` entry point, a `pyproject.toml` manifest, a `README.md`, a `LICENSE` file, and the configuration files defined in the tracked-configuration requirement below.

#### Scenario: Fresh clone exposes the layout

- **WHEN** a user clones the repository
- **THEN** the working tree contains `jarvis/__init__.py`, `jarvis/fetchers/__init__.py`, `jarvis/fetchers/arxiv.py`, `jarvis/fetchers/youtube.py`, `jarvis/state.py`, `jarvis/deliver.py`, `prompts/daily_brief.md`, `samples/example_briefing.md`, `scripts/init.sh`, `state/.gitkeep`, `run.sh`, `config.yaml`, `profile.yaml`, `.env.example`, `pyproject.toml`, `README.md`, and `LICENSE`

#### Scenario: State directory is preserved but empty

- **WHEN** a user clones the repository
- **THEN** `state/` exists, contains only `.gitkeep`, and `state/seen.sqlite` is absent from the working tree

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

### Requirement: Pre-commit secret scanner

The repository SHALL ship a `.pre-commit-config.yaml` that runs a secret scanner (e.g. `gitleaks` or `detect-secrets`) on every commit. The README SHALL document `pre-commit install` as a setup step.

#### Scenario: Commit containing a secret-shaped string is blocked

- **WHEN** a user stages a file containing a value that matches a known credential pattern and runs `git commit`
- **THEN** the secret-scanner hook fails the commit and prints a diagnostic identifying the offending content

### Requirement: README documents the public-repo safety contract

The committed `README.md` SHALL include a section that instructs the user to enable GitHub Push Protection, install the pre-commit hooks, and run a pre-first-push checklist (review `git status`, review `git diff --cached`, grep for credential-shaped strings).

#### Scenario: Forker reads the README before pushing

- **WHEN** a user reads the README's safety section
- **THEN** the README explicitly directs the user to (a) enable GitHub Push Protection, (b) install pre-commit hooks, and (c) verify staged content before the first push

### Requirement: Python project manifest

The repository SHALL contain a `pyproject.toml` declaring the project's Python version requirement, runtime dependencies (sufficient for fetchers, state, and delivery), and a build backend.

#### Scenario: Standard install works

- **WHEN** a user runs `pip install -e .` from the repository root in a fresh virtual environment
- **THEN** installation succeeds and the `jarvis` package is importable

### Requirement: License

The repository SHALL include a `LICENSE` file at the root with an OSI-approved open-source license suitable for forking.

#### Scenario: License is unambiguous

- **WHEN** any reviewer inspects `LICENSE`
- **THEN** the file contains a complete, unmodified text of a single OSI-approved license
