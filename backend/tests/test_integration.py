from datetime import UTC, datetime, timedelta
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app.config import Settings
from backend.app.main import create_app
from backend.tests.test_recognition import FixtureProvider, image_bytes


@pytest.fixture
def system(tmp_path):
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url="sqlite:///:memory:",
        media_directory=tmp_path / "media",
        request_limit_per_minute=1000,
        quality_checks_enabled=False,
    )
    app = create_app(settings=settings, provider=FixtureProvider())
    with TestClient(app, client=("127.0.0.1", 12345)) as client:
        setup = client.post(
            "/api/v1/auth/setup",
            json={
                "username": "test_admin",
                "password": "Test-only-password-42",
                "display_name": "Test admin",
            },
        )
        assert setup.status_code == 200, setup.text
        admin = {"Authorization": f"Bearer {setup.json()['access_token']}"}
        users = []
        for name in ("test_tourist_a", "test_tourist_b"):
            created = client.post(
                "/api/v1/admin/users",
                headers=admin,
                json={
                    "username": name,
                    "password": "Test-only-password-42",
                    "display_name": name,
                    "role": "tourist",
                    "status": "active",
                },
            )
            assert created.status_code in (200, 201), created.text
            login = client.post(
                "/api/v1/auth/login",
                json={
                    "username": name,
                    "password": "Test-only-password-42",
                },
            )
            assert login.status_code == 200, login.text
            users.append({"Authorization": f"Bearer {login.json()['access_token']}"})
        yield client, admin, users, settings
    app.state.database.engine.dispose()


def publish_character(client, admin):
    upload = client.post(
        "/api/v1/media",
        headers=admin,
        files={
            "file": ("fixture.png", image_bytes(size=(64, 64)), "image/png"),
        },
    )
    assert upload.status_code == 200, upload.text
    url = upload.json()["url"]
    created = client.post(
        "/api/v1/admin/characters",
        headers=admin,
        json={
            "id": "TEST_A",
            "cn_name": "Test only",
            "culture_summary": "Not actual cultural content.",
            "source_ref": "test:fixture",
            "image_url": url,
            "status": "published",
        },
    )
    assert created.status_code in (200, 201), created.text
    return url


def test_recognition_auth_persistence_confirmation_and_deletion(system):
    client, admin, users, _ = system
    publish_character(client, admin)
    image = {"image": ("fixture.png", image_bytes(), "image/png")}
    assert client.post("/api/v1/recognize", files=image).status_code == 401
    result = client.post("/api/v1/recognize", files=image, headers=users[0])
    assert result.status_code == 200, result.text
    request_id = result.json()["request_id"]
    assert result.json()["status"] == "NEED_USER_CONFIRM"
    assert client.get("/api/v1/me/history", headers=users[0]).json()["total"] == 1
    assert client.get("/api/v1/me/history", headers=users[1]).json()["total"] == 0
    denied = client.post(
        f"/api/v1/recognize/{request_id}/confirm", headers=users[1], json={"character_id": "TEST_A"}
    )
    assert denied.status_code in (403, 404)
    confirmed = client.post(
        f"/api/v1/recognize/{request_id}/confirm", headers=users[0], json={"character_id": "TEST_A"}
    )
    assert confirmed.status_code == 200, confirmed.text
    cleared = client.delete("/api/v1/me/history", headers=users[0])
    assert cleared.status_code == 200
    assert client.get("/api/v1/me/history", headers=users[0]).json()["total"] == 0


def test_draft_media_access_and_approved_poster(system, monkeypatch):
    client, admin, users, settings = system
    from pydantic import SecretStr

    from backend.app import poster_jobs

    settings.image_provider_name = "openai-compatible"
    settings.image_provider_endpoint = "https://images.example.invalid/v1/images/generations"
    settings.image_provider_model = "fixture-art-model"
    settings.image_provider_api_key = SecretStr("synthetic-image-key")

    async def fixture_artwork(active, template, materials, records, caption, with_code):
        assert active.image_provider_model == "fixture-art-model"
        assert template == "paper"
        assert len(materials) == 2 and materials[0][0] == "design-reference.png"
        assert materials[1][0] == "glyph-1.png"
        assert with_code is False
        return Image.new("RGB", (900, 1400), "cornflowerblue")

    monkeypatch.setattr(poster_jobs, "generate_poster_art", fixture_artwork)
    upload = client.post(
        "/api/v1/media",
        headers=admin,
        files={
            "file": ("draft.png", image_bytes(), "image/png"),
        },
    )
    draft_url = upload.json()["url"]
    assert client.get(draft_url).status_code == 401
    assert client.get(draft_url, headers=users[0]).status_code == 403
    assert client.get(draft_url, headers=admin).status_code == 200
    published_url = publish_character(client, admin)
    assert client.get(published_url).status_code == 200
    body = {"character_ids": ["TEST_A"], "template": "paper"}
    assert client.post("/api/v1/share/poster", headers=users[0], json=body).status_code == 403
    assert client.put("/api/v1/me/favorites/TEST_A", headers=users[0]).status_code == 200
    result = client.post("/api/v1/share/poster", headers=users[0], json=body)
    assert result.status_code == 200, result.text
    assert result.json()["share_code_available"] is False
    assert client.get("/api/v1/admin/stats", headers=admin).json()["events"]["poster_generate"] == 1
    url = result.json()["url"].removeprefix(settings.public_base_url)
    image = client.get(url)
    assert image.status_code == 200
    with Image.open(BytesIO(image.content)) as decoded:
        assert decoded.size == (900, 1400)
        # The complete synthetic provider image is preserved, not covered by a local template.
        assert decoded.getcolors() == [(900 * 1400, (100, 149, 237))]


def test_placeholder_provider_never_claims_ready_from_configuration_alone():
    settings = Settings(
        _env_file=None,
        provider_name="future-provider",
        provider_endpoint="https://example.invalid",
        provider_api_key="test-only-secret",
        provider_model="future-model",
    )
    with TestClient(create_app(settings=settings, business_enabled=False)) as client:
        response = client.get("/ready")
    assert response.status_code == 503
    assert not response.json()["provider_configured"]
    assert "test-only-secret" not in response.text


def test_streaming_body_limit_and_rate_limit():
    settings = Settings(_env_file=None, max_image_bytes=1, request_limit_per_minute=2)
    with TestClient(create_app(settings=settings, business_enabled=False)) as client:
        oversized = client.post("/api/v1/recognize", content=iter([b"x" * 40000, b"x" * 40000]))
        assert oversized.status_code == 413
        assert oversized.json()["code"] == "REQUEST_TOO_LARGE"
        assert client.get("/api/v1/privacy").status_code == 200
        limited = client.get("/api/v1/privacy")
        assert limited.status_code == 429
        assert limited.headers["Retry-After"] == "60"
        assert client.get("/health").status_code == 200


def test_production_requires_mysql_migrations_and_https():
    with pytest.raises(ValueError, match="MySQL"):
        Settings(_env_file=None, environment="production", database_url="sqlite:///:memory:")
    with pytest.raises(ValueError, match="migrations"):
        Settings(_env_file=None, environment="production")


def test_tourist_coupon_qr_and_merchant_redemption(system):
    client, admin, users, _ = system
    merchant = client.post(
        "/api/v1/admin/merchants",
        headers=admin,
        json={
            "name": "QR fixture shop",
            "latitude": 26.87,
            "longitude": 100.23,
            "status": "published",
        },
    )
    assert merchant.status_code == 200, merchant.text
    merchant_id = merchant.json()["id"]
    account = client.post(
        "/api/v1/admin/users",
        headers=admin,
        json={
            "username": "qr_merchant",
            "password": "Test-only-password-42",
            "display_name": "QR merchant",
            "role": "merchant",
            "merchant_id": merchant_id,
        },
    )
    assert account.status_code == 200, account.text
    login = client.post(
        "/api/v1/auth/login", json={"username": "qr_merchant", "password": "Test-only-password-42"}
    )
    merchant_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    now = datetime.now(UTC)
    coupon = client.post(
        "/api/v1/admin/coupons",
        headers=admin,
        json={
            "merchant_id": merchant_id,
            "title": "QR fixture coupon",
            "rule": "Test only",
            "stock": 3,
            "start_at": (now - timedelta(days=1)).isoformat(),
            "end_at": (now + timedelta(days=1)).isoformat(),
            "status": "published",
        },
    )
    assert coupon.status_code == 200, coupon.text
    claim = client.post(f"/api/v1/coupons/{coupon.json()['id']}/claim", headers=users[0])
    assert claim.status_code == 200, claim.text
    endpoint = f"/api/v1/me/coupons/{claim.json()['id']}/qr"
    assert client.get(endpoint).status_code == 401
    assert client.get(endpoint, headers=users[1]).status_code == 404
    image = client.get(endpoint, headers=users[0])
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/png"
    with Image.open(BytesIO(image.content)) as decoded:
        assert decoded.width == decoded.height
        assert len(decoded.getcolors()) == 2
    verified = client.post(
        "/api/v1/coupons/verify", headers=merchant_headers, json={"code": claim.json()["code"]}
    )
    assert verified.status_code == 200, verified.text
    assert client.get("/api/v1/me/coupons", headers=users[0]).json()["items"][0]["status"] == "used"
