# Verification record

Verified locally on Python 3.14, macOS, using the pinned dependency set.

- Ruff lint and formatting checks.
- pytest domain and HTTP integration tests, including invalid input, stale review conflicts, origin/body boundaries and database rollback.
- Browser workflow: load synthetic input, execute inference, inspect results, save review, reload persisted history. No browser console errors observed.
- Reproducible synthetic evaluation: see evaluation.json and scripts/evaluate.py.
- JavaScript syntax checked with Node.js; frontend formatted with Prettier 3.6.2.

Not validated: production workloads, cloud deployment, multi-user security, real customer data, model generalization beyond the synthetic corpus, or exhaustive cross-browser/mobile compatibility. The test client emits an upstream Starlette/httpx deprecation warning; tests pass.
