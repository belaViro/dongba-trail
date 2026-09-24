# Business Backend Verification

Date: 2026-09-23. Scope: the persisted business backend, its API contracts and MySQL
migrations. These results establish implemented business behavior using synthetic
fixtures; they do not claim real recognition accuracy, live merchant activity or
WeChat device acceptance. The user accepted the recognition provider configuration
placeholder and prioritized completion of business flows over further safety,
concurrency or performance work. No additional specialist testing is planned here.

## Delivered Scope

- Persistent MySQL business records; portable isolated SQLite tests; migration setup.
- First-admin setup, password login, session revocation, real WeChat code exchange
  adapter, privacy/configuration gates, roles and merchant ownership.
- Published dictionary, cultural images/variants, merchant/POI/product/activity
  management, publication review and audit, merchant cultural-tag applications.
- All six recommendation weights, actual user interests and effective coupon state.
- Coupon claims, quotas, inventory, expiry, merchant redemption and source events.
- Recognition confirmation, feedback review, favorites, history and history deletion.
- All five configured quest conditions, progress, stamps, completion rewards and
  pending-reward retry after route expiry.
- Actual event-derived operations/merchant statistics and scoped event deduplication.
- Audited, filtered CSV exports with explicit field/size limits and spreadsheet
  formula escaping for dictionary, feedback, recognitions, audit and tag claims.
- Concrete request models in OpenAPI for content creation and partial updates.

Implementation details and exact response semantics are recorded in
`../contracts/business-implementation.md` and the generated OpenAPI contract.

## Version Evidence

Business-owned fingerprint:

`sha256:d1ba2adbe01297d9dad710eb6e22d8f84bd16a85d98691877fb9e79198b55bc2`

The fingerprint covers 15 files: `backend/app/business/*.py`,
`backend/migrations/**/*.py`, `backend/tests/test_business*.py` and
`backend/alembic.ini`. Paths are sorted by full path; each relative path uses forward
slashes. The SHA-256 input is UTF-8 relative path, NUL, UTF-8 content normalized to
LF, NUL, repeated for each file. Documentation is excluded. This scoped fingerprint
remains independent of concurrent client and deployment changes. The final integrated
release evidence must also record the whole-project fingerprint.

## Commands And Results

All commands use `.venv\Scripts\python.exe` from the project root.

```powershell
$env:DONGBA_RUN_MYSQL_TESTS='1'
.venv\Scripts\python.exe -m pytest backend/tests/test_business_api.py backend/tests/test_business_migrations.py -q
```

Result: **52 passed**, 102.50 seconds, one existing Starlette/AnyIO deprecation
warning. This consists of 24 business tests run once on SQLite and once on the real
isolated MySQL service, plus four migration checks across those two databases.

The real service is MySQL 8.0.44 on localhost. The tests require the dedicated
`dongba_test` database and explicit `DONGBA_RUN_MYSQL_TESTS=1` opt-in. They reject
other database names before any schema reset. Credentials are read by the test
configuration and are never printed. `dongba` and `dongba_ui` are not modified by
these tests.

```powershell
.venv\Scripts\python.exe -m ruff check backend/app/business backend/migrations backend/tests/test_business_api.py backend/tests/test_business_migrations.py
```

Result: all checks passed. Owned Python files were formatted with Ruff. At the time
of the package verification, whole-repository Ruff still reported two unrelated
in-progress formatting issues in `scripts/mysql_local.py` and `scripts/serve.py`;
those were reported to the integrating agent and are outside this package result.

```powershell
$env:DONGBA_RUN_MYSQL_TESTS='1'
.venv\Scripts\python.exe -m pytest backend/tests -q
```

Integrated result: **89 passed**, 106.03 seconds, the same existing deprecation
warning. This includes the recognition, media, provider-placeholder and privacy
integration tests present at execution time. No test process remains running.

## Business Verification Details

Tests exercise setup restrictions, logout and disabled accounts, login failure
handling, explicit WeChat consent/configuration and mocked official exchange,
publication gates, merchant isolation, tag approval, recommendation behavior,
coupon expiry and quotas, idempotent redemption, source-scoped reporting, private
history/favorites, candidate ownership and feedback deletion, all quest conditions,
pending rewards, rule freezing, event deduplication, exports and OpenAPI fields.

Independent `Database` instances and connection pools verify inventory does not
oversell, one-user limits hold, repeat redemptions remain idempotent and simultaneous
quest completion grants one reward. The real MySQL run exposed a stale snapshot
under its default repeatable-read isolation; READ COMMITTED plus row locking fixed
the behavior, and the real database regression tests passed.

Migrations were upgraded twice, checked for schema drift, downgraded on the isolated
test database, upgraded again and checked again. A separate test changed existing
MySQL tables to the old collation, inserted FK-linked synthetic user/favorite/session
records, applied `0002_mysql_storage`, and verified those records survived.

## Limits

- No real WeChat account or phone was used. Official exchange responses in tests
  are isolated fixtures, not a simulated production authentication mode.
- No default cultural or merchant records are seeded in the application database.
- The provider configuration placeholder is expected until the user supplies their
  chosen implementation and credentials.
- Coordinates are checked against configured places, but client GPS and static QR
  tokens do not establish physical presence beyond those supplied signals.
- Production runtime traffic, real device navigation/sharing, content approval and
  final delivery recipient requirements remain part of integrated release review.
