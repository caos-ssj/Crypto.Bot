# Contributing to Crypto Bot

First off, thanks for taking the time to contribute! 👋

This project is built to be **educational and honest**: the core rules enforce
that unverified on-chain data never inflates a token's score. Every contribution
should respect that spirit.

## Table of contents

- [Code of Conduct](#code-of-conduct)
- [How to start](#how-to-start)
- [Development setup](#development-setup)
- [Code style](#code-style)
- [Testing](#testing)
- [Reporting bugs](#reporting-bugs)
- [Suggesting features](#suggesting-features)
- [Pull request workflow](#pull-request-workflow)
- [Project conventions](#project-conventions)

## Code of Conduct

By participating in this project you agree to abide by our
[Code of Conduct](CODE_OF_CONDUCT.md).

## How to start

1. Check the [README](README.EN.md) to know what the project does.
2. Look for issues labeled `good first issue` if you're new.
3. Comment on the issue you want to work on so people know you're on it.

## Development setup

The repo has no build system; it uses a plain virtualenv:

```bash
git clone git@github.com:caosssj/Crypto.Bot.git
cd Crypto.Bot
python3 -m venv venv
venv/bin/pip install -r requirements.txt
cp .env.example .env   # SOLANA_RPC_URL + optional HELIUS_API_KEY
```

Everything runs through `venv/bin/` (no Poetry/uv).

## Code style

- **Python 3.11 / 3.12** source, typed function signatures.
- **ruff** must pass: `venv/bin/ruff check src/ tests/`
- **black** must pass: `venv/bin/black --check src/ tests/`
- Only `BLE001`/`S110` are ignored, and only at API boundaries (see `ruff.toml`).

## Testing

```bash
venv/bin/python -m pytest tests/ -q --cov=src --cov-fail-under=60
```

- Coverage must stay **≥ 60 %** (blocking in CI).
- Every new filter, rule or behavior change must ship with tests.
- Tests never hit real networks: DexScreener/Helius/Jupiter calls are mocked.

## Reporting bugs

Use the **Bug report** issue form (English). Include:

- Exact command and mode used.
- Expected vs actual behavior.
- `.env` keys used (never paste your `WALLET_PRIVATE_KEY` or full `.env`).
- Relevant log output.

## Suggesting features

Use the **Feature request** issue form. Frame it around the user value, not the
implementation, and note if it touches risk management (that's the sensitive
core).

## Pull request workflow

1. Branch from `main`: `git checkout -b feat/my-change`.
2. Commit with a clear message (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).
3. Run the check suite locally (style + tests).
4. Open a PR against `main` and fill the PR template.
5. CI must be green: **ruff**, **black** and **pytest --cov** are blocking.

### Scope rules

- **Risk limits** (TP/SL/trailing, exposure, daily loss) are conservative by
  design. Changes that loosen them need strong justification and tests.
- **The honest-scoring rule is sacred**: never change `missing` data to score
  points in favor of a token.

## Project conventions

- Banner, CLI labels and docs are in **Spanish**; code, CI and this file are in
  **English**.
- Versioning follows SemVer (tags are annotated). See `CHANGELOG.md`.
- Architecture decisions live in `docs/arquitectura.md` and agent memory in
  `CLAUDE.md`.