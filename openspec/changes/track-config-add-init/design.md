## Context

The repository currently uses a layered configuration pattern: `config.yaml` (committed defaults) is merged with `config.local.yaml` (gitignored user overrides), and the user is expected to copy `config.local.yaml.example` to `config.local.yaml` before first run. The same pattern applies to `profile.example.yaml` → `profile.local.yaml`. This was originally chosen to keep the public repo free of any one user's data.

After running the system end-to-end the maintainer reports three problems with the pattern: forkers have no obvious starting point even with detailed example files, the copy-and-edit step is manual and error-prone, and the maintainer's own configuration is not under version control. The maintainer is explicitly comfortable with their non-secret configuration (channel IDs, search themes, role profile) being public.

The natural alternative — track the non-secret config in git and use a small script to capture only the secrets — is what this change implements.

## Goals / Non-Goals

**Goals:**

- Single source of truth for each non-secret configuration concern: `config.yaml` and `profile.yaml`, both committed.
- Secrets stay in `.env`, gitignored, populated by a single interactive command.
- A first-time user (maintainer or forker) can go from `git clone` to a working pipeline with one scripted step plus optional editing of two committed YAML files.
- Init script is idempotent against reruns and refuses to silently overwrite existing secrets.
- The maintainer's existing `config.local.yaml` and `profile.local.yaml` content is preserved verbatim during migration — this change carries no behavioral risk to the next daily run.

**Non-Goals:**

- Multi-profile support (e.g., one repo serving multiple users with their own committed profiles via env-var selector). Out of scope; the maintainer is one user, and forkers fork.
- A GUI or TUI configuration editor. The init script is a single-pass `read`-prompt loop, nothing more.
- Validation of YAML config beyond what `_config.load_config` already does. Forker mistakes in `config.yaml` will surface at runtime as before.
- Encrypting `.env` at rest. File permissions (`chmod 600`) are the only protection, matching the prior state.
- Backward compatibility with the layered pattern. After this change, `config.local.yaml` and `profile.local.yaml` are not consulted; if present in a working tree they are inert.

## Decisions

### 1. Single committed `config.yaml`, no override layer

**Decision:** `config.yaml` becomes the sole config file the loader reads. The `config.local.yaml` merge logic in `_config.load_config` is removed.

**Alternative considered:** Keep an optional `config.local.yaml` override that, if present, supersedes `config.yaml`. This preserves the maintainer's flexibility to keep one file pristine while editing another.

**Why rejected:** It reintroduces exactly the cognitive overhead the change is trying to remove. A maintainer who wants a "scratch" override can use a git branch.

### 2. `init.sh` reads `.env.example` to discover required variables

**Decision:** The init script does not hardcode a list of variables. It parses `.env.example`, treating each `KEY=` line as a prompt and any preceding `#` comment lines as the help text.

**Alternative considered:** Hardcode the variable list inside `init.sh`.

**Why rejected:** Drift. Adding a new credential later would require editing two files; with the parse approach, `.env.example` is the single authority.

### 3. Init script is bash, not Python

**Decision:** `scripts/init.sh` is a bash script, matching `run.sh`'s tooling style.

**Alternative considered:** A Python `jarvis init` subcommand alongside `jarvis.deliver`, `jarvis.state`, etc.

**Why rejected:** First-time users have not yet set up `.venv`. A Python-based init forces them through `python3 -m venv .venv` first, which is the kind of step the change is supposed to eliminate. Bash + standard `read` works on a fresh clone with nothing installed.

### 4. Smoke-test only the Slack webhook, not YouTube

**Decision:** After capturing secrets, the script offers (default-yes) to post a "JARVIS init complete" line to the user's Slack via the webhook they just entered. It does not call the YouTube API.

**Alternative considered:** Verify both, or neither.

**Why rejected (verify both):** A YouTube quota check requires picking a real channel and a parse step; it's enough mechanism to start being its own bug surface. The webhook test is one HTTP POST and confirms the most user-visible failure mode.

**Why rejected (verify neither):** The webhook test catches the most common typo (a webhook URL pasted from the wrong channel) at setup time rather than at 7 AM the next morning.

### 5. `.env` is `chmod 600`

**Decision:** After writing `.env`, `init.sh` runs `chmod 600` on it.

**Rationale:** Existing `.env` files are usually `0644` (mode-on-create with default umask). `0600` is the conventional permission for files containing secrets and is cheap to enforce.

### 6. Migration is a one-time content move, not an automated migration

**Decision:** Implementation tasks include manually copying the maintainer's current `config.local.yaml` content into the new committed `config.yaml`, and `profile.local.yaml` into `profile.yaml`. There is no migration script.

**Rationale:** Migration runs once, on the maintainer's machine, against known content. A migration script would carry more risk than the manual edit.

## Risks / Trade-offs

- **[Risk] Maintainer's data lands in public history.** Once committed, `config.yaml` and `profile.yaml` are in the repo's history forever. → **Mitigation:** The maintainer has explicitly stated they accept this for non-secret data. Anything they later regret committing can still be force-history-rewritten before push (mitigated further by GitHub Push Protection if enabled). The proposal covers no secrets in these files.

- **[Risk] Forkers accidentally commit the maintainer's profile values as if they were their own.** → **Mitigation:** README setup section will explicitly call out "edit `config.yaml` and `profile.yaml` to your own values before running" as the first post-init step.

- **[Risk] Init script's auto-parsing of `.env.example` misreads a malformed line and writes a broken `.env`.** → **Mitigation:** Keep `.env.example` strictly `KEY=` lines plus `#` comments. The script validates the file shape before prompting and exits early on parse failure.

- **[Trade-off] Loss of "two files, two purposes" clarity.** Some users find the `config.yaml` defaults / `config.local.yaml` overrides split semantically clean. They lose that mental model. → **Counter:** The split's value depended on having a generic shipped default. With personalized values committed, the split is decorative.

- **[Risk] Smoke-test posts a setup notice to the user's real channel, surprising other channel members.** → **Mitigation:** The smoke-test is opt-in (a single y/N prompt), the message is plainly labeled `[JARVIS init]`, and the prompt makes clear that the message will be visible to anyone in the channel.

## Migration Plan

1. Land the code changes (loader, prompt, gitignore, README, new script) on a branch.
2. In the same change, replace the contents of the committed `config.yaml` and `profile.yaml` with the maintainer's current local values, copy-paste verified.
3. After merge, the maintainer deletes their now-orphaned `config.local.yaml` and `profile.local.yaml` files; their working tree begins reading from the tracked files.
4. The next scheduled cron run is the verification: same data, new file paths, identical output.
5. **Rollback:** revert the merge commit. Loader falls back to the layered behavior; the maintainer recreates `config.local.yaml` from the reverted `config.yaml` content if needed.
