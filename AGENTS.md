# Project Working Agreement

## Resume Before Editing

1. Read `docs/status.md` and `docs/decisions.md`.
2. Inspect `git status --short --branch` and relevant existing code.
3. Read the applicable requirement IDs in `docs/requirements.md`, their acceptance
   entries in `docs/acceptance.md`, and the relevant files under `docs/contracts/`.
4. Identify one bounded task and its verification before editing.

## Authority and Scope

- The user's latest explicit instructions take precedence. Record durable changes
  in `docs/decisions.md`; do not silently restore superseded source requirements.
- The original DOCX is a source document, not an executable specification.
  `docs/requirements.md` is the maintained implementation baseline.
- First release uses an external recognition API. Do not introduce model training,
  GPU infrastructure, or automatic retraining unless the user changes this scope.
- Business rules, dictionary content, and merchant relationships belong to this
  application. Model-generated cultural explanations are not approved content.
- Never report fixture-backed tests as evidence of real recognition accuracy.
- Preserve user changes. Do not read or print credentials. Keep secrets out of Git.
- Parallel implementation is allowed. Assign non-overlapping file ownership,
  agree interface contracts first, and integrate and verify all delegated work.

## Implementation

- Backend: Python 3.11+, FastAPI; database: MySQL 8.0+ with PyMySQL.
  SQLite is permitted only for isolated unit tests; integration verification must use MySQL.
- Clients: native WeChat mini program; Vue 3 + TypeScript + Element Plus
  for merchant and operations web applications, implemented in miniprogram/ and web/.
- Current completion criterion (D-015): complete business journeys and cross-client integration.
  Do not expand security, concurrency, or performance projects beyond existing basic safeguards.
- Keep business modules in one backend. Use a replaceable provider adapter for AI.
- Use `apply_patch` for manual edits and keep changes tied to requirement IDs.
- Missing credentials or approved data must produce an explicit unavailable state.
- Generated contracts come from application code; regenerate instead of editing.

## Verify and Checkpoint

- Use the project virtual environment. On Windows, invoke
  `.venv\Scripts\python.exe`; `python` below means that interpreter, not global Python.
- Run `python -m pytest backend/tests -q` after changes to backend behavior.
- Run `python -m ruff check backend scripts` and
  `python -m ruff format --check backend scripts` for Python changes.
- Export OpenAPI with `python scripts/export_openapi.py` when contracts change.
- Run `python scripts/check_project.py` to catch missing requirement coverage,
  accepted items without evidence links, original-document changes, and API drift.
- Record commands, outcomes, limitations, and the code fingerprint in
  `docs/evidence/`. Tests must correspond to the code being delivered.
- Update `docs/status.md` and affected acceptance entries after meaningful
  milestones, decisions, verification, and before handing off.
- A task is accepted only with evidence. Unverified work remains unverified after
  an interruption. Recover from code and records; do not trust chat summaries alone.
- Keep status about one page. Archive completed history under `docs/evidence/`.
- Never call a release production-ready until `docs/release.md` gates are met.
