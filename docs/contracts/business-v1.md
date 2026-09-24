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
- `POST /share/poster` `{character_ids:[...],template:"mountain"|"paper"}` -> `{id,url,share_code_available}`.
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
