import asyncio
from datetime import UTC, datetime
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError

from backend.app.config import Settings
from backend.app.dictionary import CharacterDictionary
from backend.app.main import create_app
from backend.app.providers import ProviderUnavailable
from backend.app.schemas import Character, ProviderCandidate, ProviderResult


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

    async def recognize(self, image, media_type, characters):
        self.calls.append((image, media_type, characters))
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
