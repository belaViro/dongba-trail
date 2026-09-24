# Media Provenance

The client intentionally contains no fabricated Dongba glyphs, merchant photographs,
geographic points, or cultural explanations. Published image and audio URLs come
from the reviewed backend dictionary and merchant records.

A Wikipedia / Wikimedia lookup for an actual Old Town of Lijiang photograph was
attempted on 2026-09-23 and timed out both inside and outside the sandbox. No image
was downloaded, licensed, or included from that request.

The native WeChat map supplies licensed map imagery under the publisher's WeChat
service terms. The app renders only actual API coordinates and explicitly handles
missing locations.

The Chinese character "迹" used for profile and stamp decoration is a normal
Chinese label, not a claimed Dongba glyph. Camera framing and interface shapes are
ordinary UI affordances.

The three PNG map markers in assets/ are original neutral UI markers generated
by tools/generate_assets.py. They distinguish cultural places, merchants and
quest points by color; none represents a Dongba character.

The backend poster renderer uses approved uploaded glyph images. Its output
reports whether a real WeChat mini-program code was generated; the client does
not draw substitute QR codes. Lijiang background photographs still require
publisher-supplied licensed assets before final design acceptance.
