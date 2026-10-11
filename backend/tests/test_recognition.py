import asyncio
import logging
from datetime import UTC, datetime
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError

from backend.app.config import Settings
from backend.app.dictionary import CharacterDictionary
from backend.app.glyph_refs import REFERENCE_SIDE, GlyphReference, load_references
from backend.app.main import create_app
from backend.app.providers import ProviderUnavailable
from backend.app.schemas import Character, ProviderCandidate, ProviderResult
from backend.app.volcengine_provider import VolcengineArkProvider


def fixture_character(character_id="TEST_A", status="published"):
    return Character(
        character_id=character_id,
        cn_name="Fixture only",
        culture_summary="Reviewed fixture text, not actual Dongba content.",
        source_ref="test-fixture:not-a-cultural-source",
        status=status,
        reviewed_by="test-reviewer",
        reviewed_at=datetime(2026, 9, 23, tzinfo=UTC),
    )


def image_bytes(image_format="PNG", size=(8, 8)):
    stream = BytesIO()
    Image.new("RGB", size, "white").save(stream, format=image_format)
    return stream.getvalue()


class FixtureProvider:
    name = "test-fixture"
    configured = True
    # Fixture recognition never consumes reference glyph images; skip the
    # filesystem lookup so unit tests stay hermetic.
    uses_reference_images = False

    def __init__(self, result=None, error=None, delay=0):
        self.result = (
            result
            if result is not None
            else ProviderResult(
                model_version="fixture-v1",
                candidates=[ProviderCandidate(character_id="TEST_A", score=0.99)],
            )
        )
        self.error = error
        self.delay = delay
        self.calls = []

    async def recognize(self, image, media_type, characters, references=()):
        self.calls.append((image, media_type, characters, references))
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return self.result


def client_for(provider=None, characters=None, **settings):
    return TestClient(
        create_app(
            business_enabled=False,
            settings=Settings(_env_file=None, **settings),
            provider=provider,
            dictionary=CharacterDictionary(
                characters if characters is not None else [fixture_character()]
            ),
        )
    )


def upload(client, content=None, **kwargs):
    return client.post(
        "/api/v1/recognize",
        files={"image": ("sample.png", image_bytes() if content is None else content, "image/png")},
        **kwargs,
    )


def test_liveness_does_not_claim_readiness():
    with client_for(characters=[]) as client:
        assert client.get("/health").status_code == 200
        ready = client.get("/ready")
    assert ready.status_code == 503
    assert set(ready.json()["reasons"]) == {"PROVIDER_NOT_CONFIGURED", "DICTIONARY_NOT_READY"}


def test_ready_requires_provider_and_published_dictionary():
    provider = FixtureProvider()
    with client_for(provider) as client:
        assert client.get("/ready").json()["status"] == "ready"
    with client_for(provider, characters=[]) as client:
        response = upload(client)
    assert response.status_code == 503
    assert response.json()["code"] == "DICTIONARY_NOT_READY"
    assert provider.calls == []


def test_unconfigured_provider_returns_explicit_error():
    with client_for() as client:
        response = upload(client)
    assert response.status_code == 503
    assert response.json()["code"] == "PROVIDER_NOT_CONFIGURED"
    assert "candidates" not in response.json()


def test_known_candidates_use_reviewed_text_and_require_confirmation():
    provider = FixtureProvider(
        ProviderResult(
            model_version="fixture-v2",
            candidates=[
                ProviderCandidate(character_id="MISSING", score=1),
                ProviderCandidate(character_id="TEST_A", score=0.9999),
                ProviderCandidate(character_id="TEST_A", score=0.5),
                ProviderCandidate(character_id="TEST_DRAFT", score=0.2),
            ],
        )
    )
    with client_for(
        provider, characters=[fixture_character(), fixture_character("TEST_DRAFT", "draft")]
    ) as client:
        response = upload(client)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "NEED_USER_CONFIRM"
    assert body["model_version"] == "fixture-v2"
    assert len(body["candidates"]) == 1
    assert body["candidates"][0]["culture_summary"] == fixture_character().culture_summary
    assert body["candidates"][0]["provider_score"] == 0.9999
    assert [c.character_id for c in provider.calls[0][2]] == ["TEST_A"]


def test_unknown_candidates_are_not_published_as_dictionary_entries():
    provider = FixtureProvider(
        ProviderResult(
            model_version="fixture-v1", candidates=[ProviderCandidate(character_id="HALLUCINATED")]
        )
    )
    with client_for(provider) as client:
        response = upload(client)
    assert response.json()["status"] == "UNKNOWN"
    assert response.json()["candidates"] == []


@pytest.mark.parametrize("content", [b"", b"not an image", b"\x89PNG\r\n\x1a\ntruncated"])
def test_invalid_images_do_not_call_provider(content):
    provider = FixtureProvider()
    with client_for(provider) as client:
        response = upload(client, content)
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_IMAGE"
    assert not provider.calls


@pytest.mark.parametrize(
    ("settings", "content"),
    [({"max_image_bytes": 10}, image_bytes()), ({"max_image_pixels": 16}, image_bytes())],
)
def test_image_limits_prevent_provider_calls(settings, content):
    provider = FixtureProvider()
    with client_for(provider, **settings) as client:
        response = upload(client, content)
    assert response.status_code == 413
    assert not provider.calls


def test_actual_image_format_is_used_instead_of_client_mime():
    provider = FixtureProvider()
    with client_for(provider) as client:
        response = upload(client, image_bytes("JPEG"))
    assert response.status_code == 200
    assert provider.calls[0][1] == "image/jpeg"


def test_unsupported_image_format_is_rejected():
    provider = FixtureProvider()
    with client_for(provider) as client:
        response = upload(client, image_bytes("GIF"))
    assert response.status_code == 415
    assert not provider.calls


def test_invalid_scene_and_missing_file_are_rejected():
    provider = FixtureProvider()
    with client_for(provider) as client:
        response = upload(client, data={"scene": "unsupported"})
        missing = client.post("/api/v1/recognize")
    assert response.status_code == missing.status_code == 422
    assert response.json()["code"] == "INVALID_REQUEST"
    assert not provider.calls


def test_provider_timeout_has_distinct_retryable_error():
    with client_for(FixtureProvider(delay=1), provider_timeout_seconds=0.001) as client:
        response = upload(client)
    assert response.status_code == 504
    assert response.json()["code"] == "PROVIDER_TIMEOUT"


@pytest.mark.parametrize(
    "result",
    [
        {"model_version": "fixture-v1", "candidates": [{"character_id": "TEST_A", "score": 4}]},
        {"model_version": "fixture-v1", "candidates": [{"character_id": "TEST_A", "score": "NaN"}]},
        {"model_version": "fixture-v1", "candidates": [{"character_id": "TEST_A"}] * 6},
        {"model_version": "fixture-v1", "candidates": [], "culture_story": "unreviewed"},
    ],
)
def test_invalid_provider_output_is_rejected(result):
    with client_for(FixtureProvider(result=result)) as client:
        response = upload(client)
    assert response.status_code == 502
    assert response.json()["code"] == "INVALID_PROVIDER_RESPONSE"


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (RuntimeError("secret-fixture-token"), 502, "PROVIDER_ERROR"),
        (ProviderUnavailable("secret-fixture-token"), 503, "PROVIDER_UNAVAILABLE"),
    ],
)
def test_provider_errors_do_not_expose_sensitive_text(error, status, code, caplog):
    with client_for(FixtureProvider(error=error)) as client:
        response = upload(client)
    assert response.status_code == status
    assert response.json()["code"] == code
    assert "secret-fixture-token" not in response.text
    assert "secret-fixture-token" not in caplog.text


def test_request_ids_correlate_errors_and_success_and_are_not_client_controlled():
    with client_for(FixtureProvider()) as client:
        success = upload(client, headers={"X-Request-ID": "client-controlled"})
        failure = upload(client, b"invalid")
    for response in (success, failure):
        assert response.json()["request_id"] == response.headers["X-Request-ID"]
        assert response.headers["X-Request-ID"] != "client-controlled"
    assert success.headers["X-Request-ID"] != failure.headers["X-Request-ID"]


def test_dictionary_detail_does_not_expose_drafts_or_reviewer_identity():
    with client_for(
        characters=[fixture_character(), fixture_character("TEST_DRAFT", "draft")]
    ) as client:
        published = client.get("/api/v1/characters/TEST_A")
        draft = client.get("/api/v1/characters/TEST_DRAFT")
    assert published.status_code == 200
    assert "reviewed_by" not in published.json()
    assert draft.status_code == 404


def test_dictionary_rejects_duplicate_ids_and_unreviewed_publication():
    with pytest.raises(ValueError, match="duplicate"):
        CharacterDictionary([fixture_character(), fixture_character()])
    with pytest.raises(ValidationError, match="review metadata"):
        Character.model_validate(fixture_character().model_dump() | {"reviewed_by": None})


def test_dictionary_loader_fails_on_missing_or_invalid_files(tmp_path):
    with pytest.raises(FileNotFoundError):
        CharacterDictionary.from_path(tmp_path / "missing.json")
    path = tmp_path / "invalid.json"
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(ValidationError):
        CharacterDictionary.from_path(path)


def reference_character(character_id, image_url):
    return Character.model_validate(
        fixture_character(character_id).model_dump() | {"image_url": image_url}
    )


def test_reference_loader_normalizes_reviewed_glyphs(tmp_path):
    asset = tmp_path / ("a" * 32 + ".png")
    Image.new("RGB", (64, 64), "white").save(asset, format="PNG")
    published = reference_character("TEST_A", f"/api/v1/media/{asset.name}")
    references = load_references([published], tmp_path)
    assert len(references) == 1
    reference = references[0]
    assert (reference.character_id, reference.cn_name) == ("TEST_A", "Fixture only")
    with Image.open(BytesIO(reference.image)) as rendered:
        assert rendered.size == (REFERENCE_SIDE, REFERENCE_SIDE)
        assert rendered.mode == "RGB"
    # A second load must reuse the cached bytes instead of re-encoding.
    assert load_references([published], tmp_path)[0].image == reference.image


def test_reference_loader_skips_missing_unreadable_and_foreign_urls(tmp_path):
    good = tmp_path / ("b" * 32 + ".png")
    Image.new("RGB", (48, 48), "white").save(good, format="PNG")
    broken = tmp_path / ("c" * 32 + ".png")
    broken.write_bytes(b"not an image")
    characters = [
        reference_character("TEST_A", f"/api/v1/media/{good.name}"),
        reference_character("TEST_B", f"/api/v1/media/{'d' * 32}.png"),
        reference_character("TEST_C", f"/api/v1/media/{broken.name}"),
        reference_character("TEST_D", "https://example.invalid/remote.png"),
        reference_character("TEST_E", ""),
    ]
    references = load_references(characters, tmp_path)
    assert [reference.character_id for reference in references] == ["TEST_A"]
    assert load_references(characters, tmp_path, limit=0) == []


def reference_glyph(path, shape):
    """Write a white glyph on a white page so its ink box is deterministic."""
    image = Image.new("L", (64, 64), 255)
    pixels = image.load()
    for x, y in shape:
        pixels[x, y] = 0
    image.save(path, format="PNG")
    return path


def test_reference_loader_shortlists_by_local_feature_instead_of_prefix(tmp_path):
    # Three near-identical horizontal strokes plus one unmistakable vertical bar.
    bars = [(x, y) for x in range(20, 44) for y in range(18, 22)]
    shapes = {
        "TEST_A": bars,
        "TEST_B": [(x, y + 2) for x, y in bars],
        "TEST_C": [(x, y + 4) for x, y in bars],
        "TEST_D": [(x, y) for y in range(12, 52) for x in range(30, 34)],
    }
    characters = []
    for character_id, shape in shapes.items():
        asset = reference_glyph(tmp_path / f"{character_id}.png", shape)
        characters.append(reference_character(character_id, f"/api/v1/media/{asset.name}"))
    query_path = reference_glyph(tmp_path / "query.png", bars)
    query_bytes = query_path.read_bytes()

    # Without a query the loader still falls back to prefix order (legacy behavior).
    prefix = load_references(characters, tmp_path, limit=2)
    assert [reference.character_id for reference in prefix] == ["TEST_A", "TEST_B"]

    # With a query photo the shortlist must include the matching glyph even when
    # the dictionary is larger than the reference limit.
    ranked = load_references(characters, tmp_path, limit=2, query=query_bytes)
    ids = [reference.character_id for reference in ranked]
    assert len(ids) == 2
    assert "TEST_A" in ids
    assert "TEST_D" not in ids


def test_reference_loader_query_keeps_every_character_reachable(tmp_path):
    characters = []
    for index in range(6):
        asset = reference_glyph(
            tmp_path / f"TEST_{index}.png",
            [(x, y + index) for x in range(16, 48) for y in range(30, 33)],
        )
        characters.append(reference_character(f"TEST_{index}", f"/api/v1/media/{asset.name}"))
    query_shape = [(x, y) for x in range(16, 48) for y in range(41, 44)]
    query_bytes = reference_glyph(tmp_path / "query.png", query_shape).read_bytes()
    seen: set[str] = set()
    for limit in range(1, 7):
        ranked = load_references(characters, tmp_path, limit=limit, query=query_bytes)
        assert len(ranked) == limit
        seen.update(reference.character_id for reference in ranked)
    # Every published character can be reached through some shortlist size.
    assert seen == {character.character_id for character in characters}


def test_ark_provider_packs_reference_glyphs_before_the_photo(monkeypatch, caplog):
    import httpx

    captured = {}
    references = (
        GlyphReference(
            character_id="TEST_A" if index == 0 else f"TEST_{index:03d}",
            cn_name="Fixture only",
            image=image_bytes(),
        )
        for index in range(200)
    )
    references = tuple(references)
    characters = (fixture_character(),)

    class Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "model": "fixture-ark",
                "usage": {
                    "prompt_tokens": 24000,
                    "completion_tokens": 40,
                    "total_tokens": 24040,
                },
                "choices": [
                    {
                        "message": {
                            "content": '{"observed_text":"","keywords":[],"scene":"",'
                            '"candidates":[{"character_id":"TEST_A","score":1.0}]}'
                        }
                    }
                ],
            }

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return Response()

    monkeypatch.setattr(httpx, "AsyncClient", Client)
    provider = VolcengineArkProvider(
        endpoint="https://ark.example.invalid/chat", api_key="k", model="m", timeout=5
    )
    caplog.set_level(logging.INFO, logger="backend.app.volcengine_provider")
    result = asyncio.run(
        provider.recognize(image_bytes("JPEG"), "image/jpeg", characters, references)
    )
    assert [candidate.character_id for candidate in result.candidates] == ["TEST_A"]
    content = captured["json"]["messages"][0]["content"]
    kinds = [part["type"] for part in content]
    # All 200 candidates remain present in 10 sheets, plus one query photo.
    assert kinds.count("image_url") == 11
    assert kinds[-1] == "image_url"
    assert "参考字形 TEST_A" in content[1]["text"]
    assert "参考字形 TEST_199" in content[-4]["text"]
    assert content[-2]["text"] == "以下是待识别照片（不是参考对照图）："
    assert captured["json"]["max_tokens"] == 400
    assert "reference_count=200 image_count=11" in caplog.text
    assert "prompt_tokens=24000 completion_tokens=40 total_tokens=24040" in caplog.text


def test_ark_provider_without_references_falls_back_to_text_catalog(monkeypatch):
    import httpx

    captured = {}

    class Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "model": "fixture-ark",
                "choices": [{"message": {"content": '{"candidates":[]}'}}],
            }

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, headers=None, json=None):
            captured["json"] = json
            return Response()

    monkeypatch.setattr(httpx, "AsyncClient", Client)
    provider = VolcengineArkProvider(
        endpoint="https://ark.example.invalid/chat", api_key="k", model="m", timeout=5
    )
    asyncio.run(provider.recognize(image_bytes("JPEG"), "image/jpeg", (fixture_character(),), ()))
    content = captured["json"]["messages"][0]["content"]
    assert [part["type"] for part in content] == ["text", "text", "image_url"]
    assert "TEST_A: Fixture only" in content[0]["text"]
    assert content[-2]["text"] == "以下是待识别照片（不是参考对照图）："
