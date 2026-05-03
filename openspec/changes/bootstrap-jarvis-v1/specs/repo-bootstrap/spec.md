## ADDED Requirements

### Requirement: Project directory layout

The repository SHALL contain the following committed top-level structure: a `jarvis/` Python package (with a `fetchers/` subpackage, `state.py`, `deliver.py`), a `prompts/` directory, a `samples/` directory, a `state/` directory containing only a `.gitkeep`, a `run.sh` entry point, a `pyproject.toml` manifest, a `README.md`, a `LICENSE` file, and the configuration template files defined in the configuration-layering requirement below.

#### Scenario: Fresh clone exposes the v1 layout

- **WHEN** a user clones the repository
- **THEN** the working tree contains `jarvis/__init__.py`, `jarvis/fetchers/__init__.py`, `jarvis/fetchers/arxiv.py`, `jarvis/fetchers/youtube.py`, `jarvis/state.py`, `jarvis/deliver.py`, `prompts/daily_brief.md`, `samples/example_briefing.md`, `state/.gitkeep`, `run.sh`, `pyproject.toml`, `README.md`, and `LICENSE`

#### Scenario: State directory is preserved but empty

- **WHEN** a user clones the repository
- **THEN** `state/` exists, contains only `.gitkeep`, and `state/seen.sqlite` is absent from the working tree

### Requirement: Two-tier configuration layering

The system SHALL separate configuration into committed templates (`*.example` files) and user-local overrides (`*.local.*` files). Committed files MUST NOT contain real secrets, real API keys, real channel identifiers, or real personal context. The committed templates MUST include `.env.example`, `config.yaml`, `config.local.yaml.example`, and `profile.example.yaml`. The user-local files (`.env`, `config.local.yaml`, `profile.local.yaml`, and optional `prompts/daily_brief.local.md`) MUST be ignored by git.

#### Scenario: User adopts the configuration

- **WHEN** a user copies `.env.example` to `.env`, `config.local.yaml.example` to `config.local.yaml`, and `profile.example.yaml` to `profile.local.yaml`, and fills in real values
- **THEN** the pipeline can run end-to-end using only those local files, without modifying any committed file

#### Scenario: Templates contain no real values

- **WHEN** any reviewer inspects `.env.example`, `config.yaml`, `config.local.yaml.example`, or `profile.example.yaml`
- **THEN** every value is either an empty string, a documented placeholder, or a generic non-sensitive default

### Requirement: gitignore covers all secret-bearing and ephemeral paths

The committed `.gitignore` SHALL list at minimum: `.env`, `*.local.yaml`, `prompts/*.local.md`, `state/seen.sqlite`, `run.log`, `__pycache__/`, `.venv/`, `/tmp/raw/`, and `/tmp/briefing.md`.

#### Scenario: User-local files are not tracked

- **WHEN** a user creates `.env`, `config.local.yaml`, `profile.local.yaml`, or `prompts/daily_brief.local.md` with real values
- **THEN** `git status` does not list these files as untracked or modified

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
