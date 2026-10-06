# Business API Implementation Contract

Base: `/api/v1`. JSON keys use snake_case. Dates use ISO-8601 UTC. IDs are strings.
Authentication: bearer access token. Roles: admin, operator, merchant, tourist.
Errors: `{request_id, code, message}`. Collection responses: `{items, total}`.
This is the agreed work contract; generated OpenAPI and integration tests are authoritative once implemented.

## Authentication

- `GET /auth/setup-status` -> `{setup_required: boolean}`
- `POST /auth/setup` `{username,password,display_name}` -> token; first admin only, local/explicit setup gate.
- `POST /auth/login` `{username,password}` -> `{access_token, token_type, user}`
- `POST /auth/wechat` `{code,privacy_accepted}` -> token; real WeChat code exchange, unavailable without configuration.
- `GET /auth/me` -> `{id,username,display_name,role,merchant_id}`
- `POST /auth/logout` invalidates current session.

## Public/Tourist

- `GET /characters`, `/characters/{id}`; published dictionary only.
- `GET /characters/{id}/nearby?latitude=&longitude=` -> merchant collection.
- `POST /recognize` multipart image + scene; authenticated in the integrated app.
- `POST /recognize/{request_id}/confirm` `{character_id?,comment?}` -> feedback.
- `GET /merchants`, `/merchants/{id}`, `/map/pois`, `/products`, `/activities`.
- `GET /coupons`, `POST /coupons/{id}/claim`, `GET /me/coupons`.
- `GET /me/coupons/{claim_id}/qr` -> authenticated owner-only PNG QR containing the redemption code.
- `GET /quests`, `/quests/{id}`; `POST /quests/{id}/join`; `POST /quests/{id}/checkin`
  `{node_id,recognition_id?,qr_token?,latitude?,longitude?,claim_id?}`.
- `GET /me/quests`, `/me/stamps`, `/me/history`, `/me/favorites`.
- `PUT /me/favorites/{character_id}`, `DELETE /me/favorites/{character_id}`, `DELETE /me/history`.
- `POST /share/poster` `{character_ids:[...],template:"mountain"|"paper"|"old-town"|"minimal",caption?:string}` -> `{id,url,share_code_available}`. Compatibility synchronous endpoint, now requires configured AI generation; no synthetic fallback.
- Mini-program uses `POST /share/poster/jobs` with the same fields plus `request_id` (12–100 ASCII letters/digits/underscore/hyphen) -> HTTP 202 `{id,status}`. `GET /share/poster/jobs/{id}` returns `{id,status,url?,share_code_available?,error_code?}`; states are `queued`, `generating`, `completed`, `failed`. Only the creator may read; other users receive 404.
- D-061: generated poster URLs are site-relative `/api/v1/media/{32-lowercase-hex}.png`, resolved against the configured API origin by clients. Reads/replays of legacy completed jobs normalize only known loopback HTTP(S) origins with this exact media path and no credentials, query or fragment. They do not change stored records, asset bytes, owner isolation or paid generation. The mini-program also normalizes cached legacy URLs before retrying the same download; unrelated/CDN URLs remain intact.
- D-062 supersedes the D-058 background-only composition rule: 1–3 authorized published glyph IDs retain selection order; captions remain at most 50 characters with whitespace normalized. The provider receives multipart Images Edits: sanitized image08 art reference first, approved local glyph bytes in selection order next, and an optional genuine mini-program code last. Only glyph names and exact caption are supplied as print content; no user identity, record IDs, media URLs or unapproved cultural interpretations are sent. AI designs the complete poster (including lettering), saved as one PNG without server template/text overlays. Only a genuine code may be restored over its reserved region to preserve machine readability. Missing/unreadable reference fails with POSTER_REFERENCE_UNAVAILABLE before a paid call; no local font prerequisite. Unsupported edits/failed generation never silently falls back to text-only backgrounds. Reference or generated art must not contain app UI, business/technical annotations, fake codes or missing-code placeholders.
- D-063 makes selected style authoritative over reference colors, textures and composition. `paper` uses warm fibrous paper with a lower scenic collage; `mountain` uses cool blue full-bleed alpine photography; `old-town` uses amber street-level architecture and lanterns; `minimal` uses at least 70% clean white with no photography. Each request includes only the selected style brief before reference instructions, with explicit excluded elements. The reference remains a quality/content-hierarchy aid, not a mandatory paper layout. Changing style starts a fresh idempotency token; downloading an old completed job must never regenerate or replace it.
- Owner plus request token identifies a persisted job. Same token/content returns the original job without another upstream call; changed content with that token returns `POSTER_REQUEST_CONFLICT`. Jobs interrupted for over eight minutes fail explicitly when queried, without automatic paid restart. No database migration is needed: private `poster_jobs` entities store owner/fingerprint/status/result only, not API keys or prompts.
- Generation without a configured service fails explicitly; provider failures never substitute a local placeholder. Missing WeChat credentials or a known `WECHAT_SHARE_UNAVAILABLE` allow a genuine AI poster with `share_code_available=false`. This machine-readable field remains for compatibility; D-062 removes no-code explanations from the artwork and customer page. Other errors still fail. A share action event describes an action, not verified delivery.
- Successful poster generation records a server-side `poster_generate` event; `share` records a client share action, not verified delivery.
- `POST /events` `{event,entity_type?,entity_id?,recognition_id?,event_id}` -> accepted.

## Operations

All CRUD resources use `GET/POST /admin/{resource}`, `PATCH/DELETE /admin/{resource}/{id}`.
GET is `{items,total}`; create/update return the entity. Search: `q`; filters: `status`; pagination: `offset`, `limit` (max 100).
Resources: characters, merchants, pois, products, coupons, activities, quests, quest-nodes, users.

Entity fields:

- characters: `id` (= character_id), `cn_name`, `category_l1`, `category_l2`, `culture_summary`, `culture_detail`,
  `source_ref`, `image_url`, `audio_url`, `variants` (array of {image_url,source_ref}), `tags` (strings), `status`.
- merchants: `id`, `name`, `description`, `address`, `latitude`, `longitude`, `phone`, `opening_hours`,
  `image_url`, `tags`, `character_ids`, `status`.
- pois: `id`, `name`, `description`, `latitude`, `longitude`, `poi_type`, `merchant_id?`, `character_ids`, `status`.
- products: `id`, `merchant_id`, `name`, `description`, `price`, `image_url`, `character_ids`, `status`.
- coupons: `id`, `merchant_id`, `title`, `rule`, `stock`, `claimed_count`, `per_user_limit`, `start_at`, `end_at`, `status`.
- activities: `id`, `merchant_id`, `name`, `description`, `start_at`, `end_at`, `capacity`, `status`.
- quests: `id`, `name`, `description`, `area`, `start_at`, `end_at`, `reward_coupon_id?`, `status`.
- quest-nodes: `id`, `quest_id`, `name`, `character_id?`, `merchant_id?`, `poi_id?`, `sequence`,
  `condition` (recognition|qr|geofence|coupon|manual), `radius_m`, `qr_token?` (privileged views only), `status`.
- users: `id`, `username`, `password` (write only), `display_name`, `role`, `merchant_id?`, `status`.

Publication status: draft, reviewed, published, disabled. Merchant owner edits reset publishable content to draft.
Review transitions require operations permissions; record reviewer and audit action.

- `GET /admin/feedback`, `PATCH /admin/feedback/{id}` `{status,review_note}`.
- `GET /admin/recognitions`, `/admin/audit`, `/admin/stats`, `/admin/provider`.
- `GET /admin/settings`, `PATCH /admin/settings` for allowed recommendation weights only; no secret management via browser.
- `POST /admin/quests/{id}/complete-node` `{user_id,node_id}` for audited manual nodes only.
- `POST /media` multipart `file` -> `{url}`; authenticated privileged image upload.

## Merchant

- `GET/PATCH /merchant/profile`; all updates follow review policy.
- `GET/POST /merchant/products|coupons|activities`, `PATCH/DELETE /merchant/{resource}/{id}`; ownership enforced server-side.
- `POST /merchant/tag-claims` `{character_id}`; `GET /merchant/tag-claims`; operations review via `/admin/tag-claims`.
- `POST /coupons/verify` `{code}`; atomic and idempotent for owning merchant only.
- `GET /merchant/redemptions`, `/merchant/stats`.

## Current external dependencies

Real provider, WeChat credentials, verified cultural data and merchant locations are unavailable.
Do not fabricate approved cultural records, successful WeChat login, real model accuracy, or operational metrics.
