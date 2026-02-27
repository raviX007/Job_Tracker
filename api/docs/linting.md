# Linting & Formatting

## What Is Linting?

A **linter** is a static analysis tool that reads your source code _without running it_ and flags problems: syntax errors, unused imports, unreachable code, style violations, and potential bugs. A **formatter** goes further — it rewrites your code to enforce a consistent style (indentation, quotes, line length) so you never debate formatting in code review.

Think of it as spell-check and grammar-check for code. The linter finds issues; the formatter fixes style automatically.

---

## Why It Matters

### Catches bugs before runtime

Linters find issues that would otherwise surface as runtime errors or subtle bugs:

```python
# Ruff catches this — variable 'reuslt' is assigned but never used (typo)
reuslt = analyze_job(job)
return result  # NameError at runtime
```

```typescript
// ESLint catches this — missing dependency in useEffect
useEffect(() => {
  fetchJobs(profileId);
}, []); // 'profileId' should be in the dependency array
```

### Enforces consistency across the team

Without a formatter, one developer uses single quotes, another uses double quotes. One uses 4-space tabs, another uses 2. Pull requests become noisy with style-only diffs. A formatter eliminates this — everyone's code looks the same after save.

### Prevents common security issues

Linters can catch patterns that lead to vulnerabilities:

- Unused variables that might indicate logic errors
- Mutable default arguments in Python (`def f(x=[])`)
- Unreachable code after `return` statements
- Missing `await` on async calls

### Speeds up code review

Reviewers focus on logic and architecture instead of pointing out `import os` is unused or a line is too long. The tooling handles the mechanical stuff.

---

## Our Setup

This project uses three tools across the three services:

| Service | Linter | Formatter | Config |
|---------|--------|-----------|--------|
| **API** (Python) | Ruff | Ruff | `api/ruff.toml` |
| **Pipeline** (Python) | Ruff | Ruff | `pipeline/pyproject.toml` |
| **UI** (TypeScript) | ESLint | Prettier | `ui-next/eslint.config.mjs` + `ui-next/.prettierrc` |

All three run automatically on every commit via [pre-commit hooks](pre-commit.md).

---

## Backend: Ruff (Python)

[Ruff](https://docs.astral.sh/ruff/) is an extremely fast Python linter and formatter written in Rust. It replaces Flake8, isort, pyupgrade, and Black in a single tool.

### What it checks

| Rule Set | Code | What It Catches |
|----------|------|-----------------|
| pycodestyle | `E`, `W` | Style errors (whitespace, indentation, line length) |
| Pyflakes | `F` | Unused imports, undefined names, redefined variables |
| isort | `I` | Import ordering (stdlib → third-party → local) |
| flake8-bugbear | `B` | Common bugs (mutable defaults, assert on tuples, redundant exception types) |
| pyupgrade | `UP` | Outdated syntax (old-style string formatting, unnecessary `dict()` calls) |
| flake8-simplify | `SIM` | Simplifiable code (nested ifs, ternary expressions) |

### Example catches

```python
# F401: 'os' imported but unused
import os

# B006: Mutable default argument
def process(items=[]):
    items.append("new")
    return items

# UP035: 'typing.Dict' is deprecated, use 'dict'
from typing import Dict

# I001: Imports not sorted
import json
import asyncio  # should come before json
```

### API config (`api/ruff.toml`)

```toml
select = ["E", "F", "W", "I", "B", "UP"]
ignore = ["B008"]  # FastAPI Depends() uses function calls in defaults
```

### Pipeline config (`pipeline/pyproject.toml`)

```toml
select = ["E", "W", "F", "I", "UP", "B", "SIM"]
```

The pipeline enables `SIM` (simplification) rules in addition to the base set. Both configs have per-file ignores for test files and scripts where stricter rules don't apply.

### Running manually

```bash
# Lint (check only)
cd api && ruff check .
cd pipeline && ruff check .

# Lint and auto-fix
cd api && ruff check --fix .

# Format
cd api && ruff format .
```

---

## Frontend: ESLint + Prettier (TypeScript)

The UI uses two complementary tools:

- **ESLint** — Catches logic errors and React-specific issues
- **Prettier** — Handles code formatting (quotes, semicolons, indentation, line wrapping)

### ESLint: What it checks

| Plugin | What It Catches |
|--------|-----------------|
| `next/core-web-vitals` | Next.js performance rules (Image component, Link component, font optimization) |
| `@typescript-eslint` | TypeScript-specific rules (unused variables, type safety, `any` usage) |
| React hooks | Missing dependencies in `useEffect`, conditional hook calls |

### Example catches

```typescript
// React hooks rule: missing dependency
useEffect(() => {
  loadData(userId);
}, []); // ESLint: 'userId' is missing from the dependency array

// Next.js rule: use Image component
<img src="/logo.png" /> // ESLint: use next/image for optimized loading

// TypeScript: unused variable
const data = await fetchJobs(); // ESLint: 'data' is assigned but never used
```

### Prettier: What it formats

| Setting | Value | Effect |
|---------|-------|--------|
| `semi` | `true` | Always add semicolons |
| `singleQuote` | `false` | Use double quotes (`"hello"`) |
| `tabWidth` | `2` | 2-space indentation |
| `trailingComma` | `all` | Trailing commas everywhere (cleaner diffs) |
| `printWidth` | `100` | Wrap lines at 100 characters |

Prettier is opinionated by design — there are very few options. This is intentional: less config means less debate.

### Running manually

```bash
cd ui-next

# ESLint
npx eslint src/

# Prettier (check)
npm run format:check

# Prettier (fix)
npm run format
```

---

## When They Run

### On every commit (automatic)

Pre-commit hooks run the appropriate tools on staged files:

```
git commit → pre-commit triggers
  → ruff lint + format (Python files in api/ and pipeline/)
  → eslint (TypeScript files in ui-next/)
  → prettier (TypeScript, CSS, JSON files in ui-next/)
```

If any check fails, the commit is blocked until you fix the issue. See [pre-commit.md](pre-commit.md) for setup.

### In CI (GitHub Actions)

CI runs the same checks on every push and pull request:

- **API CI:** `ruff check` + `ruff format --check`
- **Pipeline CI:** `ruff check` + `ruff format --check`
- **UI CI:** `next lint` (includes ESLint)

This catches anything that slipped through (e.g., someone used `--no-verify`).

### In your editor (optional but recommended)

Most editors have extensions that run linters in real-time:

| Editor | Python | TypeScript |
|--------|--------|------------|
| VS Code | [Ruff extension](https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff) | ESLint + Prettier extensions (built-in) |
| PyCharm | Ruff plugin | ESLint integration (built-in) |

With format-on-save enabled, you never have to think about formatting — just write code and save.

---

## Linting vs Formatting vs Type Checking

| Tool | Purpose | Fixes Code? | Example |
|------|---------|-------------|---------|
| **Linter** | Find bugs and bad patterns | Some (auto-fixable rules) | Unused import, missing `await` |
| **Formatter** | Enforce consistent style | Always | Indentation, quotes, line length |
| **Type checker** | Verify type correctness | No | Wrong argument type, missing return |

This project uses all three:

- **Linting:** Ruff (Python), ESLint (TypeScript)
- **Formatting:** Ruff (Python), Prettier (TypeScript)
- **Type checking:** mypy (Python, in CI), TypeScript compiler (UI, in `next build`)
