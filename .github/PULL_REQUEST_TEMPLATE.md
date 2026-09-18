## Summary

<!-- What does this PR do and why? Link the issue it closes, e.g. "Closes #12". -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Docs / assets
- [ ] CI / tooling
- [ ] Refactor

## Checklist

- [ ] `venv/bin/ruff check src/ tests/` passes.
- [ ] `venv/bin/black --check src/ tests/` passes.
- [ ] `venv/bin/python -m pytest tests/ -q --cov=src --cov-fail-under=60` passes.
- [ ] Tests added/updated for the change (if code).
- [ ] CHANGELOG updated (if user-facing).
- [ ] No secrets committed (`WALLET_PRIVATE_KEY`, API keys, `.env`).

## Risk management note

<!-- If this change touches risk logic (TP/SL, exposure, daily loss, scoring),
explain why the new behavior is still honest and conservative. If not, write
"N/A". -->

## Screenshots (if visual)