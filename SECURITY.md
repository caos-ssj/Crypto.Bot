# Security Policy

## Reporting a vulnerability

Please **do not open a public issue** for security vulnerabilities. This is a
trading bot: a disclosed exploit could be used against real positions.

Report privately by opening a [security advisory](https://github.com/caosssj/Crypto.Bot/security/advisories/new)
or emailing the maintainer (see repo settings → About → contact).

Please include:

- The affected component and version/tag.
- Steps to reproduce, if possible.
- Estimated impact and any suggested fix.

You should receive an acknowledgment within **72 hours**. After triage we agree
on a fix timeline; we ask you to keep the issue private until a release is out.

## Scope

In scope:

- Code in `src/` (execution, risk, storage, config).
- CI pipeline and dependency management.
- Handling of `WALLET_PRIVATE_KEY` and API keys.

Out of scope (best-effort, not vulnerabilities by default):

- Keys or secrets stored **locally** outside the repo (`.env`), which is the
  intended usage.
- Failures of external services we depend on (DexScreener, Helius, Jupiter,
  LM Studio).
- Social engineering.

## Security notes for users

- `WALLET_PRIVATE_KEY` is loaded from `.env` **only**; it must never be committed.
- Trailing/risk limits exist for a reason: memecoin trading can lose 100 % of
  the capital. Run `DRY_RUN=true` first.
- API keys (Helius, etc.) are sent to their respective services only.

## Dependency updates

Dependency security updates are handled automatically via Dependabot
(`.github/dependabot.yml`); merge them with priority.

## Reporting flow

1. Private report received.
2. Maintainer acknowledges within 72 h.
3. A fix is prepared on a private branch with tests.
4. Release (SemVer PATCH/MINOR) + advisory published.
5. Reporter credited if they wish.