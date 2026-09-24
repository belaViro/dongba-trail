# Native Client Verification

Date: 2026-09-23.

Scope: AUTH-01, MINI-01, AI-03, CONTENT-01, USER-01, FEEDBACK-01,
MERCHANT-01, GEO-01, REC-01, COUPON-01/02 tourist controls,
QUEST-01/02, SHARE-01, PRIVACY-01, DESIGN-01 figures 01-08 implementation.
These requirements are implemented at the client level, not fully externally accepted.

## Commands And Results

| Command | Result |
| --- | --- |
| `node miniprogram/tests/validate-project.js` | 18 native pages validated: JSON and JS syntax, registered tab/navigation routes, WXML event handlers, marker assets |
| `node --test --experimental-test-isolation=none miniprogram/tests/*.test.js` | 22 tests passed, 0 failed |
| `.venv\Scripts\python.exe miniprogram/tests/run_business_flow.py` | Complete native-controller business flow passed against a real isolated HTTP API |
| `node miniprogram/tests/native-compile.js "D:\engineering_software\微信web开发者工具"` | Official WeChat WCC/WCSC accepted 20 WXML and 16 WXSS files |
| `.venv\Scripts\python.exe -m ruff check miniprogram/tools miniprogram/tests` | Passed |
| `.venv\Scripts\python.exe -m ruff format --check miniprogram/tools miniprogram/tests` | Passed |
| `.venv\Scripts\python.exe miniprogram/tools/generate_assets.py` | Three neutral marker PNGs generated |

The ordinary `node --test` runner initially hit Windows sandbox `spawn EPERM`.
The approved outside-sandbox run passed; the final Node test run also passed
inside the sandbox using Node's documented no-isolation mode. No runtime
application authentication or provider checks were bypassed.

Code fingerprint from validate-project.js:

`3763b3fcc3f956c21750212c196ce8c5dba555e35e415a96a3879483932892a6`

The SHA-256 hashes sorted relative paths and content for `.js`, `.json`, `.wxml`,
`.wxss`, `.png` and `.py` beneath miniprogram, including test source. Markdown
records do not change that fingerprint.

## Behavioral Evidence

- Protected calls cannot send without a real session token; 401 clears identity.
- Uploads carry authenticated image and scene; unconfigured provider errors remain errors.
- Unknown-candidate feedback cannot invent a dictionary ID; selected feedback uses
  the server's actual non-null string comment contract.
- Task check-in payloads contain only the evidence for their configured condition.
- Missing coordinates/distances/scores cannot become fictional zero-valued data.
- Generic camera entry clears old quest context; privacy unpublished state blocks login.
- Poster selection is limited to three; API pagination exposes history beyond 100 rows.
- Client events use backend allowlisted names and plural entity kinds. Coupon
  conversion events are server-generated; optional recognition attribution is passed
  on the claim request.
- Failed history records offer retaking rather than bogus candidate confirmation;
  historical retake opens the camera. Private cached lists clear after logout.
- Existing enrollment progress and pending rewards remain accessible after a route
  is unpublished. POI-only task nodes have a working navigation action, and the map
  derives quest points from real configured route nodes.
- The profile and manual task dialog expose/copy the current tourist's ID for the
  operator's manual completion form. Logged-out cached identities cannot be copied.
- Cultural audio uses a separate player instance from its tap handler. Regression
  coverage verifies play, pause, completion/error state and destruction on exit,
  including exiting a page that never started audio. Actual audio streaming remains
  part of real-device validation with approved content.
- Privacy retention wording now matches the backend: results, corrections, events
  and posters have a retention period; original recognition images are not retained.

## Real HTTP Business Flow

`run_business_flow.py` starts an isolated temporary SQLite database and FastAPI HTTP
server, then executes actual native page controllers through a wx API harness.
The complete path passed: privacy/login code exchange, home and product content,
camera upload, candidate confirmation and later correction, published culture,
merchant recommendation, favorite, coupon claim, authenticated PNG QR download
and text-code copy, merchant redemption, recognition/QR/geofence/coupon/manual
quest conditions, stamp collection, reward claim, POI navigation, task map filter,
real PNG poster generation, image save and share route, history deletion while
favorites remain. The test closes its server and removes its temporary database.
Manual completion uses the ID copied by the actual native task dialog; the profile
copy action is also verified against the current authenticated user.

The WeChat exchange, recognition provider, OS location/camera and share functions
are explicit test substitutes. QR and poster PNGs are produced by real backend
code, and every business API call goes over HTTP. This proves page-controller/API
compatibility; it does not prove real provider accuracy, real-device capabilities,
or MySQL behavior (covered separately by backend MySQL evidence).

## Remaining External Verification

The follow-up installation search found WeChat developer tools at
`D:/engineering_software/微信web开发者工具`. Its standalone official WCC/WCSC
executables successfully compiled all native templates and styles. The package's
Node addon could not load its native dependency, so the test uses the provided
standalone compiler executables. These produce transient compiled output in
memory; no upload or publication is performed.

An authenticated mini-program account was not available. Native template/style
compilation and the static binding validator are not an IDE screenshot or real-device
test. Actual iOS/Android camera, privacy consent, login exchange, map, geofence
accuracy, photo saving and WeChat sharing remain acceptance gates in README.md.

No real provider API, approved dictionary/merchant data or real route was supplied.
Unit-test tokens, coordinates and IDs are fixtures isolated from the application and
do not establish recognition accuracy or operational metrics. A licensed Lijiang
photograph could not be retrieved; ASSETS.md records this limitation. The client
uses approved CMS images and a real native map when actual data is configured.

The client renders server-generated PNG posters and honors share_code_available;
it never substitutes a fake QR code or claims missing WeChat code support is verified.
