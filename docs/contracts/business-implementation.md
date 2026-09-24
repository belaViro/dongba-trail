# Business Backend Implementation

Implementation baseline: `business-v1.md`, AUTH-01/02, DATA-01/02, CONTENT-01,
USER-01, FEEDBACK-01, MERCHANT-01/02, GEO-01, REC-01, COUPON-01/02,
QUEST-01/02, OPS-01/02/03, ANALYTICS-01 and the business portion of PRIVACY-01.

## Integration

`backend.app.business.install_business(app, settings)` installs the authentication,
catalogue, operations, merchant, visitor and audited export routes under `/api/v1`.
It returns the `Database` instance and exposes the same object as
`app.state.database`. Settings are available as `app.state.business_settings`.

`current_user` and `User` are exported from `backend.app.business`; stricter
`require_operations` and `require_merchant` dependencies live in `business.auth`.
`database.session()` opens a read session; `database.write()` commits on success
and rolls back on exceptions. The application must dispose `database.engine` on
shutdown. Media, posters, recognition provider calls and provider monitoring live
outside this business package and share these authentication dependencies.

Recognition integration calls:

```python
database.record_recognition(
    request_id=request_id,
    user_id=user.id,
    status=result.status,
    provider=result.provider,
    model=result.model_version,
    candidates=[candidate.model_dump() for candidate in result.candidates],
    latency_ms=result.latency_ms,
    scene=scene,
    error_code=None,
)
```

`database.published_characters()` supplies dictionary records including
`character_id`, `reviewed_by` and `reviewed_at`. `allowed_poster_character_ids(user_id)`
returns the union of current favorites and confirmed recognition history.

## Database And Migrations

The production target is MySQL 8.4, with MySQL 8.0 compatibility verified against
the available 8.0.44 instance. Tables use InnoDB, utf8mb4, and utf8mb4_bin so opaque
tokens, coupon codes and IDs use exact string comparisons. SQLAlchemy/PyMySQL
connections use READ COMMITTED; row locks and unique constraints enforce business
invariants across independent connection pools. SQLite is an isolated test option,
using an immediate transaction for writes. It is not production concurrency evidence.

Application code uses relational tables for identities, sessions, inventory,
claims, enrollments, stamps, events, feedback, favorites and audit records. The
`entities` table stores typed, validated content payloads with indexed type, status
and merchant ownership columns. Content relationships are validated by the service;
transactional foreign keys are also enforced by the database.

Apply migrations with:

```powershell
.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.venv\Scripts\python.exe -m alembic -c backend/alembic.ini check
```

Revision `0001_business` creates the schema and the locked first-admin setup row.
Revision `0002_mysql_storage` normalizes existing MySQL table engines and collations
without removing rows. Its downgrade intentionally retains exact collation because
returning to case-insensitive uniqueness could reject valid data. Downgrading the
initial migration to `base` removes all business tables and is only used on the
isolated migration test database. Production rollbacks require an approved backup
and restoration procedure, not an automatic destructive schema downgrade.

`auto_create_schema` is convenient locally. Production startup requires migrations
and must disable automatic table creation. No approved cultural content, merchant,
user, coupon or route is seeded automatically.

## Authentication And Ownership

- Passwords use salted scrypt. Access tokens are random 256-bit credentials; only
  SHA-256 token hashes are stored. Logout revokes the current session. Account
  updates revoke existing sessions; disabled accounts cannot authenticate.
- First-admin setup requires a loopback peer, `setup_enabled`, and no completed
  setup. Production additionally requires the configured setup secret. The setup
  singleton is locked to prevent concurrent creation of multiple initial admins.
- WeChat login requires published privacy information, a privacy contact, explicit
  user consent and configured credentials. The backend exchanges the code directly
  with WeChat. OpenID is hashed for the local identifier; session_key is not stored
  or returned. Missing configuration is a 503 unavailable state, not a fake login.
- Only admins manage users. Admins and operators manage operational content.
  Merchant ownership is taken from the authenticated account, never trusted from
  a supplied merchant ID. Merchants cannot set authoritative cultural associations,
  recommendation factors or publish their changes without operations review.
- User history, favorites, coupon claims, quest progress and stamps are scoped to
  the authenticated user. Recognized candidate confirmation requires both ownership
  of the original request and membership in its original candidate set.

## Content And Recommendations

Publishing cultural entries requires source, summary and at least one glyph image.
Published merchants require a coordinate pair. Coordinates use GCJ-02, matching
WeChat map and navigation APIs. Draft merchants can have no location; the service
does not invent coordinates. Operations publication records reviewer and timestamp
and appends an audit action. Merchant content edits return to draft. Deletion of
referenced business content disables it, preserving transactional history.

Public queries return published records, hide content of disabled merchants, and
exclude expired or future coupons, activities and quests from active lists. Quest
details remain readable for a published route after expiry; no new progress is
accepted outside its effective period.

Nearby recommendations first require an approved character-to-merchant relationship.
The six configured weights are applied to cultural relevance, distance, curated
merchant quality, available coupons, current-user interests, and operations weight.
Merchant quality and operations factors are normalized values editable only by
operations; their neutral default is 0.5. Current-user interests use favorites and
confirmed history. Without login or location those respective factors are zero.
Weights must be known, between zero and one, and sum to one. Free-form opening-hours
text is displayed as supplied; the service does not infer real-time opening status.

## Coupons And Quests

Coupon claims lock the user and coupon, verify availability and per-user limits,
then conditionally increment inventory only below stock. Changes to issued coupon
ownership, validity and redemption rules are rejected. Stock cannot fall below
already issued claims. Redemption locks the claim, checks merchant ownership and
validity, and records the verifier. Repeating redemption returns the same used claim
with `already_verified: true` and does not emit a second conversion.

Quest check-in conditions are verified on the server:

- Recognition: an owned, confirmed matching record created after joining.
- QR: exact match to the configured secret token; public endpoints omit the token.
- Geofence: a published mapped location and distance within the configured radius.
- Coupon: an owned claim redeemed at the required merchant after joining.
- Manual: an operations action, audited with the target user.

Node order is a route display order; the first release allows completion in any
order. Once a route has participants, node conditions, membership and publication
cannot change, and the route's validity and reward rules are fixed. Row locks and
unique constraints prevent repeated stamps, completion events or reward claims.

Earned reward coupons use a unique enrollment key and share the normal stock and
validity checks. An earned reward is a separate entitlement and is not blocked by
the ordinary voluntary-claim per-user limit. If reward stock is unavailable, quest
completion remains recorded with `reward_pending: true`; repeating an already
completed node retries the reward, including after the route expires. It never
repeats progress or grants a second reward.

Geofence checks do not provide device attestation against GPS spoofing. A static
shop QR token can be shared outside the shop. These are explicit trust limits of
these first-release completion methods.

## Events, Exports And Privacy

Client event IDs are unique per user and duplicate submission is idempotent.
Recognitions attached to client events must belong to the same user. Coupon claim,
redemption and quest completion events are emitted by server transactions; clients
cannot forge those event types. Optional `recognition_id` on the coupon claim query
links conversion to the source recognition. Counts and daily series derive from
stored rows; they are not fabricated business metrics or recognition accuracy.

`POST /admin/exports/{resource}` supports characters, feedback, recognitions, audit
and tag-claims. The request accepts `q`, `status` and `limit` (default 1000, maximum
10000). It returns `{filename, content_type, content, row_count, truncated}`. Content
is UTF-8 CSV with BOM, a 10 MiB hard limit, a fixed field allowlist and spreadsheet
formula neutralization. Exports require operations permission and record actor,
resource, row count, truncation and filter metadata in the audit trail. Password
hashes, access/session tokens, WeChat secrets and image binaries are not exported.
Feedback retains review status and must not be treated as approved training truth.

Recognition photographs are not persisted by this package. `DELETE /me/history`
removes recognition records and related feedback, and clears event references to
deleted recognitions. Favorites and earned stamps remain separately managed user
data. `workflows.delete_user_history(session, user_id)` exposes the same deletion
behavior for maintenance operations.

## Verification

See `docs/evidence/business-acceptance.md` for the exact commands, code fingerprint,
real MySQL concurrency checks and migration checks. All test content and WeChat
exchange responses are explicitly synthetic fixtures. They provide implementation
evidence, not real cultural recognition, real merchant operation or WeChat device
acceptance evidence.
