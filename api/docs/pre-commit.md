# Pre-commit Hooks

Automated linting before every commit using [pre-commit](https://pre-commit.com/). Catches lint errors locally before they hit CI.

---

## Setup

```bash
# Install pre-commit (one-time)
pip install pre-commit

# Install git hooks (one-time per clone)
cd job-tracker
pre-commit install
```

After this, every `git commit` will automatically run the configured hooks on changed files.

---

## What Runs

| Hook | Scope | Tool |
|------|-------|------|
| `ruff-lint-api` | `api/**/*.py` | Ruff linter (rules from `api/ruff.toml`) |
| `ruff-format-api` | `api/**/*.py` | Ruff formatter |
| `ruff-lint-pipeline` | `pipeline/**/*.py` | Ruff linter (rules from `pipeline/pyproject.toml`) |
| `ruff-format-pipeline` | `pipeline/**/*.py` | Ruff formatter |
| `eslint-ui-next` | `ui-next/**/*.{ts,tsx,js,jsx}` | ESLint (Next.js config) |
| `prettier-ui-next` | `ui-next/**/*.{ts,tsx,js,jsx,json,css}` | Prettier formatter |

Each project has its own config with different rules and per-file ignores, so they run as separate hooks. See [linting.md](linting.md) for details on what each tool checks.

---

## Manual Run

```bash
# Run on all files (useful after config changes)
pre-commit run --all-files

# Run on specific files
pre-commit run --files api/core/logger.py

# Run a specific hook
pre-commit run ruff-lint-api --all-files
```

---

## Skipping Hooks (Emergency)

```bash
# Skip all hooks for one commit
git commit --no-verify -m "hotfix: ..."
```

Use sparingly — CI will still catch issues.

---

## Updating Hook Versions

```bash
# Update all hooks to latest versions
pre-commit autoupdate

# Then commit the updated .pre-commit-config.yaml
git add .pre-commit-config.yaml
git commit -m "chore: update pre-commit hooks"
```

---

## Troubleshooting

**Hook fails on first run:**
Pre-commit installs hook environments on first use. If ruff or eslint aren't available, it will install them automatically.

**ESLint hook fails with "npx not found":**
Ensure Node.js is installed and `ui-next/node_modules` exists (`cd ui-next && npm install`).

**Hook is too slow:**
Pre-commit only runs on changed files by default. Use `--all-files` only when needed.
