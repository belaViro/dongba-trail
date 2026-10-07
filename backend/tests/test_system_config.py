"""Runtime configuration uses synthetic credentials and a disposable database only."""

from io import BytesIO

from cryptography.fernet import Fernet
from PIL import Image
from pydantic import SecretStr

from backend.app.business.models import Audit, Setting
from backend.app.main import create_app
from backend.app.schemas import ProviderResult
from backend.app.system_config import CONFIG_KEY
from backend.app.volcengine_provider import VolcengineArkProvider
from backend.tests import test_business_api

context = test_business_api.context


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
