"""Runtime configuration uses synthetic credentials and a disposable database only."""

from io import BytesIO
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from PIL import Image
from pydantic import SecretStr

from backend.app.business.models import Audit, RecognitionRecord, Setting
from backend.app.main import create_app
from backend.app.schemas import ProviderResult
from backend.app.system_config import CONFIG_KEY, SystemConfigUpdate
from backend.app.volcengine_provider import VolcengineArkProvider
from backend.tests import test_business_api

context = test_business_api.context


def service(context):
    response = context.client.get("/api/v1/admin/provider", headers=context.admin)
    assert response.status_code == 200, response.text
    return response.json()


def payload(**updates):
    return {
        "provider_name": "volcengine-ark",
        "provider_endpoint": "https://example.invalid/api/v3/chat/completions",
        "provider_model": "fixture-vision-model",
        "provider_timeout_seconds": 20,
        "map_web_key": "test-public-map-key",
        **updates,
    }


def test_admin_only_and_public_map(context):
    _, operator = context.actor("operator")
    _, merchant = context.actor("merchant", context.merchant()["id"])
    path = "/api/v1/admin/system-config"
    assert context.client.get(path).status_code == 401
    for headers in (operator, merchant):
        assert context.client.get(path, headers=headers).status_code == 403
        assert context.client.put(path, headers=headers, json=payload()).status_code == 403
    assert context.client.get("/api/v1/public/map-config").json()["web_key"] == ""
    result = context.client.put(
        path,
        headers=context.admin,
        json=payload(map_center_longitude=100.3, map_center_latitude=26.9, map_default_zoom=11),
    )
    assert result.status_code == 200, result.text
    assert context.client.get("/api/v1/public/map-config").json()["web_key"] == (
        "test-public-map-key"
    )
    public = context.client.get("/api/v1/public/map-config")
    assert public.headers["cache-control"] == "no-store"
    assert public.json()["center_longitude"] == 100.3
    assert public.json()["center_latitude"] == 26.9
    assert public.json()["default_zoom"] == 11
    base_url_result = context.client.put(
        path,
        headers=context.admin,
        json=payload(provider_endpoint="https://example.invalid/api/v3"),
    )
    assert base_url_result.status_code == 200
    assert base_url_result.json()["provider_endpoint"] == (
        "https://example.invalid/api/v3/chat/completions"
    )
    assert context.client.get("/api/v1/admin/provider", headers=operator).json()["model"] == (
        "fixture-vision-model"
    )
    assert not result.json()["provider_api_key_configured"]
    assert context.client.get("/ready").json()["provider_configured"] is False


def test_encryption_redaction_and_immediate_cross_worker_visibility(context, monkeypatch):
    key = Fernet.generate_key().decode()
    context.app.state.settings.system_config_encryption_key = SecretStr(key)
    secret = "fixture-secret-not-for-logs"
    path = "/api/v1/admin/system-config"
    result = context.client.put(path, headers=context.admin, json=payload(provider_api_key=secret))
    assert result.status_code == 200, result.text
    assert result.json()["provider_api_key_configured"]
    assert secret not in result.text
    assert secret not in context.client.get(path, headers=context.admin).text
    assert context.client.get("/ready").json()["provider_configured"]
    assert context.client.get("/api/v1/admin/provider", headers=context.admin).json()["configured"]
    with context.app.state.database.session() as session:
        assert secret not in str(session.get(Setting, CONFIG_KEY).value)
        audits = session.query(Audit).filter(Audit.entity_type == "system_config").all()
        assert audits and all(secret not in str(audit.detail) for audit in audits)

    # A second application/worker reads the same database, not the first process's memory.
    second = create_app(settings=context.app.state.settings)
    from backend.app.system_config import active_provider

    with second.state.database.session() as session:
        provider, active = active_provider(session, second.state.settings)
        assert provider.configured and active.provider_model == "fixture-vision-model"
    second.state.database.engine.dispose()
    # Exercise actual HTTP recognition orchestration without a supplier/network call.
    context.character()
    context.app.state.settings.quality_checks_enabled = False
    seen = []

    async def fake_recognition(self, image, media_type, characters, references=()):
        seen.append((self.model, self.timeout))
        return ProviderResult(model_version=self.model, candidates=[])

    monkeypatch.setattr(VolcengineArkProvider, "recognize", fake_recognition)
    picture = BytesIO()
    Image.new("RGB", (128, 128), "white").save(picture, format="PNG")

    def recognize():
        response = context.client.post(
            "/api/v1/recognize",
            headers=context.admin,
            files={"image": ("fixture.png", picture.getvalue(), "image/png")},
        )
        assert response.status_code == 200, response.text
        return response.json()["model_version"]

    assert recognize() == "fixture-vision-model"
    replaced = context.client.put(
        path,
        headers=context.admin,
        json=payload(provider_model="fixture-vision-v2", provider_timeout_seconds=7),
    )
    assert replaced.status_code == 200
    assert recognize() == "fixture-vision-v2"
    assert seen == [("fixture-vision-model", 20), ("fixture-vision-v2", 7)]
    unchanged = context.client.put(path, headers=context.admin, json=payload(map_web_key="new-key"))
    assert unchanged.json()["provider_api_key_configured"]
    assert context.client.get("/api/v1/public/map-config").json()["web_key"] == "new-key"
    cleared = context.client.put(
        path, headers=context.admin, json=payload(clear_provider_api_key=True)
    )
    assert not cleared.json()["provider_api_key_configured"]
    assert not context.client.get("/ready").json()["provider_configured"]


def test_invalid_endpoint_and_missing_encryption_key(context):
    path = "/api/v1/admin/system-config"
    assert (
        context.client.put(
            path, headers=context.admin, json=payload(provider_endpoint="http://127.0.0.1/private")
        ).status_code
        == 422
    )
    assert (
        context.client.put(
            path, headers=context.admin, json=payload(provider_api_key="test-only")
        ).status_code
        == 503
    )
    assert context.client.get("/api/v1/public/map-config").json()["web_key"] == ""
    for endpoint in ("https://localhost/private", "https://192.168.1.1/private", "not-a-url"):
        assert (
            context.client.put(
                path, headers=context.admin, json=payload(provider_endpoint=endpoint)
            ).status_code
            == 422
        )


@pytest.mark.parametrize(
    ("alias", "name"),
    [(" LOCAL ", "db1404-local"), ("Ark", "volcengine-ark"), ("volcengine", "volcengine-ark")],
)
def test_provider_aliases_are_canonical(alias, name):
    assert SystemConfigUpdate(**payload(provider_name=alias)).provider_name == name


def test_local_config_preserves_ark_and_reports_actual_identity(context, tmp_path, monkeypatch):
    settings = context.app.state.settings
    settings.system_config_encryption_key = SecretStr(Fernet.generate_key().decode())
    settings.local_model_path = tmp_path / "missing-model.pt"
    settings.local_model_version = "fixture-local-v2"
    settings.local_model_threads = 1
    path = "/api/v1/admin/system-config"

    async def forbidden(*args, **kwargs):
        pytest.fail("Status/config/local recognition must not call Ark")

    monkeypatch.setattr(VolcengineArkProvider, "recognize", forbidden)
    assert (
        context.client.put(
            path, headers=context.admin, json=payload(provider_api_key="fixture-ark-key")
        ).status_code
        == 200
    )
    external = service(context)
    assert external["status"] == "configured"  # Configuration, not a network probe.
    assert external["model"] == "fixture-vision-model"

    result = context.client.put(path, headers=context.admin, json=payload(provider_name="local"))
    assert result.status_code == 200, result.text
    value = result.json()
    assert value["provider_name"] == "db1404-local"
    assert value["provider_model"] == "fixture-vision-model"  # Reserved Ark settings.
    assert value["provider_api_key_configured"]
    assert value["local_model_version"] == "fixture-local-v2"
    assert value["local_model_threads"] == 1
    local = service(context)
    assert value["recognition_service"] == {key: local[key] for key in value["recognition_service"]}
    assert local["name"] == "db1404-local"
    assert local["model"] == "fixture-local-v2"
    assert local["kind"] == "local"
    assert local["status"] == "unavailable"
    assert not local["configured"]
    assert local["endpoint_configured"] is None
    assert local["timeout_seconds"] == 20
    assert local["cpu_threads"] == 1
    assert not local["automatic_fallback"]
    assert not local["calibrated_confidence"]
    assert context.client.get("/ready").json()["provider_configured"] is False

    # Quality/input failures must not be recorded as the reserved Ark model either.
    response = context.client.post(
        "/api/v1/recognize",
        headers=context.admin,
        files={"image": ("bad.png", b"bad", "image/png")},
    )
    assert response.status_code == 400
    with context.app.state.database.session() as session:
        record = session.get(RecognitionRecord, response.json()["request_id"])
        assert record.provider == "db1404-local"
        assert record.model == "fixture-local-v2"

    assert context.client.put(path, headers=context.admin, json=payload()).status_code == 200
    assert service(context)["configured"]  # Retained encrypted key used again.


def test_local_runtime_is_independent_of_unreadable_reserved_ark_key(context, tmp_path):
    context.app.state.settings.local_model_path = tmp_path / "missing.pt"
    with context.app.state.database.write() as session:
        session.add(
            Setting(
                key=CONFIG_KEY,
                value={
                    **payload(provider_name="db1404-local"),
                    "encrypted_api_key": "fixture-invalid-ciphertext",
                },
            )
        )
    assert service(context)["status"] == "unavailable"
    response = context.client.get("/api/v1/admin/system-config", headers=context.admin)
    assert response.status_code == 200
    assert response.json()["provider_api_key_configured"]  # Stored, not validated or exposed.
    response = context.client.put(
        "/api/v1/admin/system-config", headers=context.admin, json=payload()
    )
    assert response.status_code == 503  # Switching to Ark still requires a readable key.
    assert service(context)["name"] == "db1404-local"  # Failed update rolled back.


def test_provider_statistics_only_include_active_provider_and_model(context):
    response = context.client.put(
        "/api/v1/admin/system-config", headers=context.admin, json=payload()
    )
    assert response.status_code == 200
    user, _ = context.actor()

    def record(provider="volcengine-ark", model="fixture-vision-model", latency=1, error=None):
        context.app.state.database.record_recognition(
            request_id=str(uuid4()),
            user_id=user["id"],
            status="FAILED" if error else "UNKNOWN",
            provider=provider,
            model=model,
            candidates=[],
            latency_ms=latency,
            error_code=error,
        )

    for latency in range(1, 21):
        record(latency=latency)
    record(latency=10000, error="PROVIDER_TIMEOUT")
    record(provider="db1404-local", latency=99000)
    record(model="old-ark-model", latency=88000)
    status = service(context)
    assert status["recent_requests"] == 21
    assert status["recent_errors"] == 1
    assert status["p95_latency_ms"] == 19
    assert status["statistics_scope"] == "current_provider_and_model"
    assert status["statistics_limit"] == 1000
    _, merchant = context.actor("merchant", context.merchant()["id"])
    assert context.client.get("/api/v1/admin/provider").status_code == 401
    assert context.client.get("/api/v1/admin/provider", headers=merchant).status_code == 403


def test_local_loaded_status_and_unavailable_recognition_never_falls_back(
    context, tmp_path, monkeypatch
):
    from backend.tests.test_local_glyph_provider import artifact

    path, digest = artifact(tmp_path)
    settings = context.app.state.settings
    settings.local_model_path = path
    settings.local_model_sha256 = digest
    settings.local_model_version = "fixture-http-local"
    settings.quality_checks_enabled = False
    context.character()

    async def forbidden(*args, **kwargs):
        pytest.fail("Local failure must not fall back to Ark")

    monkeypatch.setattr(VolcengineArkProvider, "recognize", forbidden)
    result = context.client.put(
        "/api/v1/admin/system-config",
        headers=context.admin,
        json=payload(provider_name="db1404-local"),
    )
    assert result.status_code == 200, result.text
    assert result.json()["recognition_service"]["status"] == "ready"
    assert service(context)["configured"]
    assert service(context)["model"] == "fixture-http-local"
    assert context.client.get("/ready").json()["provider_configured"]
    picture = BytesIO()
    Image.new("RGB", (256, 256), "white").save(picture, format="PNG")
    path.write_bytes(b"corrupted fixture model after status check")
    assert service(context)["status"] == "unavailable"
    result = context.client.post(
        "/api/v1/recognize",
        headers=context.admin,
        files={"image": ("fixture.png", picture.getvalue(), "image/png")},
    )
    assert result.status_code == 503
    with context.app.state.database.session() as session:
        record = session.get(RecognitionRecord, result.json()["request_id"])
        assert record.model == "fixture-http-local"
        assert record.error_code == "PROVIDER_NOT_CONFIGURED"
    assert service(context)["recent_errors"] == 1
    result = context.client.put(
        "/api/v1/admin/system-config",
        headers=context.admin,
        json=payload(provider_name="unconfigured"),
    )
    assert result.status_code == 200
    assert service(context)["model"] == ""
    assert service(context)["status"] == "unconfigured"
    assert service(context)["p95_latency_ms"] is None
