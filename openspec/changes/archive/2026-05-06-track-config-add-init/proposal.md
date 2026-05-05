## Why

The current configuration model — committed `*.example` templates that the user copies to gitignored `*.local.*` overrides — costs three things in practice: (1) a forker has no obvious starting point even with good docs, (2) the copy-and-edit dance is manual and error-prone, and (3) the maintainer's own settings (channels, search themes, profile) have no version history. The maintainer is comfortable with their non-secret configuration being public, so the cost is unjustified. Flip the model so non-secret config is committed, and replace the manual copy step with an interactive `init` script that captures only the credentials.

## What Changes

- **BREAKING**: Replace the two-tier `config.yaml` + `config.local.yaml.example` + `config.local.yaml` layering with a single committed `config.yaml`. Delete the example variant. The loader stops merging local overrides.
- **BREAKING**: Replace `profile.example.yaml` + `profile.local.yaml` with a single committed `profile.yaml`.
- Continue gitignoring `.env` (the only home for true secrets — Slack webhook URL and YouTube API key). Keep `.env.example` as a documented manifest of expected variables.
- Add `scripts/init.sh`, an interactive setup script that:
  - Refuses to overwrite an existing `.env` without confirmation,
  - Prompts for each variable declared in `.env.example`, with the variable's leading comment shown as the prompt help text,
  - Writes `.env` with `chmod 600`,
  - Optionally smoke-tests the Slack webhook end of the pipeline by posting a one-line setup notice,
  - Exits non-zero with a readable message on any failure.
- Migrate the maintainer's current `config.local.yaml` and `profile.local.yaml` content into the new committed files, in place. Forkers who clone the repo will read those values inline and edit them in their own working copy or fork.
- Update the synthesis prompt's §0 reference from `config.local.yaml` / `profile.local.yaml` to `config.yaml` / `profile.yaml`.
- Update `_config.load_config` to read only `config.yaml` (drop the local-override merge).
- Update `.gitignore` to remove `*.local.yaml` and `prompts/*.local.md` entries; the local-override convention no longer exists.
- Update README setup section: `bash scripts/init.sh` replaces the multi-step copy instructions.

## Capabilities

### New Capabilities

- `credential-bootstrap`: Interactive `init` script that captures secrets into `.env` and verifies them against the live services where feasible.

### Modified Capabilities

- `repo-bootstrap`: The two-tier configuration layering requirement is replaced by a single-tier "non-secret config tracked, secrets in `.env`" requirement. Several scenarios about `*.example` files and `*.local.*` gitignore entries are removed; new scenarios cover the committed config files and the init-script entry point.

## Impact

- **Code**: `jarvis/_config.py` simplifies (drop merge logic). New `scripts/init.sh`. `prompts/daily_brief.md` §0 file references update.
- **Repo layout**: `config.yaml` rewritten in place; `config.local.yaml.example`, `profile.example.yaml` removed; `profile.yaml` added. `.gitignore` shrinks.
- **Forker experience**: One scripted setup step (`bash scripts/init.sh`) plus inline editing of two committed YAML files, instead of copying three template files and editing them blind.
- **Maintainer experience**: Personal config is now version-controlled — channel additions, theme tweaks, and `upcoming_events` accumulate in git history rather than living in an untracked file that is one `rm` away from being lost.
- **Existing local files**: The maintainer's current `config.local.yaml` and `profile.local.yaml` content is migrated into the new tracked files as the implementation step. After the change lands, those gitignored files become orphaned and can be deleted by the maintainer.
- **Public-fork audience**: A forker's first commit on their fork edits `config.yaml` and `profile.yaml` directly. The maintainer's data is plainly visible until replaced — acceptable per the maintainer's stated preference.
