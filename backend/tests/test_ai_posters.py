"""SHARE-01 / OPS-03 / AUTH-02: synthetic AI posters, never real provider calls.

Database cases reuse Context: SQLite is isolated fixture coverage; MySQL runs only
through its explicitly enabled disposable-test-database branch.
"""

import asyncio
import base64
import json
import socket
from datetime import UTC, datetime, timedelta
from email import policy
from email.parser import BytesParser
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from cryptography.fernet import Fernet
from PIL import Image
from pydantic import SecretStr
from starlette.background import BackgroundTasks

from backend.app import image_provider, media, poster_art, poster_jobs, system_config
from backend.app.business.models import Audit, Entity, Event, Setting
from backend.app.config import Settings
from backend.app.errors import ApiError
from backend.tests import test_business_api

context = test_business_api.context
IMAGE_KEY = "synthetic-image-key-not-a-real-credential"
VISION_KEY = "synthetic-vision-key-not-a-real-credential"
ENDPOINT = "https://images.example.invalid/v1/images/generations"
CONFIG_PATH = "/api/v1/admin/system-config"
JOBS_PATH = "/api/v1/share/poster/jobs"


def png_bytes(color="cornflowerblue", size=(320, 480), image_format="PNG"):
    output = BytesIO()
    Image.new("RGB", size, color).save(output, format=image_format)
    return output.getvalue()


def b64_body(content=None):
    if content is None:
        content = png_bytes()
    return {"data": [{"b64_json": base64.b64encode(content).decode()}]}


def assert_error(response, status, code):
    assert response.status_code == status, response.text
    assert response.json()["code"] == code, response.text
    assert IMAGE_KEY not in response.text
    assert VISION_KEY not in response.text


@pytest.fixture(autouse=True)
def no_external_services(monkeypatch):
    # Settings(_env_file=None) still reads process env: never inherit real keys.
    for name in (
        "IMAGE_PROVIDER_API_KEY",
        "IMAGE_PROVIDER_NAME",
        "IMAGE_PROVIDER_ENDPOINT",
        "IMAGE_PROVIDER_MODEL",
        "PROVIDER_API_KEY",
        "WECHAT_APP_ID",
        "WECHAT_APP_SECRET",
        "SYSTEM_CONFIG_ENCRYPTION_KEY",
    ):
        monkeypatch.delenv("DONGBA_" + name, raising=False)

    def deny_http(*args, **kwargs):
        pytest.fail("Unexpected external HTTP; use the explicit MockTransport fixture")

    async def deny_async_http(*args, **kwargs):
        deny_http()

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", deny_http)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", deny_async_http)


@pytest.fixture
def image_settings(tmp_path):
    return Settings(
        _env_file=None,
        environment="test",
        database_url="sqlite:///:memory:",
        media_directory=tmp_path / "media",
        image_provider_name="openai-compatible",
        image_provider_endpoint=ENDPOINT,
        image_provider_model="fixture-art-model",
        image_provider_api_key=SecretStr(IMAGE_KEY),
    )


@pytest.fixture
def adapter_http(monkeypatch):
    """Only replace DNS policy here; retain real URL validation and HTTP parsing."""
    original_client = httpx.AsyncClient
    state = SimpleNamespace(requests=[], clients=[], checked_urls=[])

    async def fixture_public_host(url):
        image_provider.validate_url(url, query=True)
        state.checked_urls.append(url)

    def install(handler):
        def dispatch(request):
            state.requests.append(request)
            return handler(request)

        def client(**kwargs):
            state.clients.append(kwargs.copy())
            return original_client(transport=httpx.MockTransport(dispatch), **kwargs)

        monkeypatch.setattr(image_provider, "public_host", fixture_public_host)
        monkeypatch.setattr(image_provider.httpx, "AsyncClient", client)
        return state

    return install


@pytest.fixture
def dns_answers(monkeypatch):
    def install(addresses):
        def lookup(*args, **kwargs):
            if isinstance(addresses, Exception):
                raise addresses
            return [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443)) for address in addresses
            ]

        monkeypatch.setattr(image_provider.socket, "getaddrinfo", lookup)

    return install


@pytest.mark.parametrize("image_format", ["PNG", "JPEG", "WEBP"])
def test_adapter_decodes_base64_and_sends_background_only(
    image_settings, adapter_http, image_format
):
    state = adapter_http(
        lambda request: httpx.Response(200, json=b64_body(png_bytes(image_format=image_format)))
    )
    image = asyncio.run(image_provider.generate_background(image_settings, "mountain"))
    assert image.size == (320, 480) and image.mode == "RGB"
    assert len(state.requests) == 1
    request = state.requests[0]
    assert request.method == "POST" and str(request.url) == ENDPOINT
    assert request.headers["authorization"] == "Bearer " + IMAGE_KEY
    payload = json.loads(request.content)
    assert set(payload) == {"model", "prompt", "n", "size"}
    assert payload["model"] == "fixture-art-model"
    assert payload["n"] == 1 and payload["size"] == "1024x1536"
    assert image_provider.STYLES["mountain"] in payload["prompt"]
    assert "No writing" in payload["prompt"] and "no QR codes" in payload["prompt"]
    assert state.clients[0]["follow_redirects"] is False
    assert state.clients[0]["trust_env"] is False


@pytest.mark.parametrize("size,quality", [("auto", "auto"), ("1024x1024", "high")])
def test_adapter_respects_optional_size_and_quality(image_settings, adapter_http, size, quality):
    image_settings.image_provider_size = size
    image_settings.image_provider_quality = quality
    state = adapter_http(lambda request: httpx.Response(200, json=b64_body()))
    asyncio.run(image_provider.generate_background(image_settings, "paper"))
    payload = json.loads(state.requests[0].content)
    for key, value in (("size", size), ("quality", quality)):
        if value == "auto":
            assert key not in payload
        else:
            assert payload[key] == value


def test_adapter_url_download_redirect_never_forwards_bearer(image_settings, adapter_http):
    first = "https://cdn.example.invalid/first.png?signature=synthetic"
    final = "https://assets.example.invalid/final.png?signature=synthetic"

    def handler(request):
        if request.method == "POST":
            return httpx.Response(200, json={"data": [{"url": first}]})
        assert "authorization" not in request.headers
        if str(request.url) == first:
            return httpx.Response(302, headers={"location": final})
        assert str(request.url) == final
        return httpx.Response(200, content=png_bytes("seagreen"))

    state = adapter_http(handler)
    image = asyncio.run(image_provider.generate_background(image_settings, "old-town"))
    assert image.getpixel((0, 0)) == (46, 139, 87)
    assert state.checked_urls == [ENDPOINT, first, final]
    assert [request.method for request in state.requests] == ["POST", "GET", "GET"]


@pytest.mark.parametrize(
    "url",
    [
        "http://cdn.example.invalid/image.png",
        "https://127.0.0.1/image.png",
        "https://[::1]/image.png",
        "https://10.1.2.3/image.png",
        "https://169.254.169.254/latest/meta-data",
        "https://localhost/image.png",
        "https://printer.local/image.png",
        "https://service.internal/image.png",
        "https://user:secret@cdn.example.invalid/image.png",
        "https://cdn.example.invalid:8443/image.png",
    ],
)
@pytest.mark.parametrize("redirect", [False, True])
def test_adapter_rejects_unsafe_image_urls_before_fetch(
    image_settings, adapter_http, url, redirect
):
    def handler(request):
        if request.method == "POST":
            return httpx.Response(
                200,
                json={"data": [{"url": "https://cdn.example.invalid/start" if redirect else url}]},
            )
        assert redirect and request.url.host == "cdn.example.invalid"
        return httpx.Response(302, headers={"location": url})

    state = adapter_http(handler)
    with pytest.raises(ApiError) as caught:
        asyncio.run(image_provider.generate_background(image_settings, "minimal"))
    assert caught.value.code == "IMAGE_PROVIDER_INVALID_RESPONSE"
    assert len(state.requests) == (2 if redirect else 1)


def test_adapter_rejects_redirect_loop(image_settings, adapter_http):
    def handler(request):
        if request.method == "POST":
            return httpx.Response(200, json={"data": [{"url": "https://cdn.example.invalid/loop"}]})
        return httpx.Response(307, headers={"location": "/loop"})

    state = adapter_http(handler)
    with pytest.raises(ApiError, match="redirect") as caught:
        asyncio.run(image_provider.generate_background(image_settings, "paper"))
    assert caught.value.code == "IMAGE_PROVIDER_INVALID_RESPONSE"
    assert len(state.requests) == 5


@pytest.mark.parametrize(
    "addresses",
    [
        [],
        ["127.0.0.1"],
        ["10.0.0.1"],
        ["::1"],
        ["169.254.169.254"],
        ["8.8.8.8", "192.168.1.1"],
        socket.gaierror("synthetic DNS failure"),
    ],
)
def test_real_public_host_rejects_private_or_failed_dns(dns_answers, addresses):
    dns_answers(addresses)
    with pytest.raises(ApiError) as caught:
        asyncio.run(image_provider.public_host("https://cdn.example.invalid/image.png"))
    assert caught.value.code == "IMAGE_PROVIDER_UNAVAILABLE"


def test_real_public_host_accepts_public_dns(dns_answers):
    dns_answers(["8.8.8.8", "1.1.1.1"])
    asyncio.run(image_provider.public_host("https://cdn.example.invalid/image.png"))


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "IMAGE_PROVIDER_AUTH_FAILED"),
        (403, "IMAGE_PROVIDER_AUTH_FAILED"),
        (429, "IMAGE_PROVIDER_BUSY"),
        (500, "IMAGE_PROVIDER_UNAVAILABLE"),
        (302, "IMAGE_PROVIDER_UNAVAILABLE"),
    ],
)
def test_provider_errors_are_sanitized_without_fallback(image_settings, adapter_http, status, code):
    state = adapter_http(
        lambda request: httpx.Response(
            status,
            text="supplier leaked " + IMAGE_KEY,
            headers={"location": "https://elsewhere.example.invalid/generate"},
        )
    )
    with pytest.raises(ApiError) as caught:
        asyncio.run(image_provider.generate_background(image_settings, "paper"))
    assert caught.value.status_code == 502 and caught.value.code == code
    assert IMAGE_KEY not in caught.value.message
    assert len(state.requests) == 1


@pytest.mark.parametrize(
    "failure,code,status",
    [
        (httpx.ReadTimeout, "IMAGE_PROVIDER_TIMEOUT", 504),
        (httpx.ConnectTimeout, "IMAGE_PROVIDER_TIMEOUT", 504),
        (httpx.ConnectError, "IMAGE_PROVIDER_UNAVAILABLE", 502),
    ],
)
def test_adapter_transport_failure_never_returns_fake_art(
    image_settings, adapter_http, failure, code, status
):
    def handler(request):
        raise failure("synthetic upstream " + IMAGE_KEY, request=request)

    state = adapter_http(handler)
    with pytest.raises(ApiError) as caught:
        asyncio.run(image_provider.generate_background(image_settings, "paper"))
    assert (caught.value.status_code, caught.value.code) == (status, code)
    assert IMAGE_KEY not in caught.value.message
    assert len(state.requests) == 1


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"data": []},
        {"data": [{}]},
        {"data": [{"b64_json": "!not-base64!"}]},
        {"data": [{"url": 123}]},
        {"data": [None]},
        {"data": ["not-an-object"]},
    ],
)
def test_adapter_malformed_results_are_typed_errors(image_settings, adapter_http, body):
    adapter_http(lambda request: httpx.Response(200, json=body))
    with pytest.raises(ApiError) as caught:
        asyncio.run(image_provider.generate_background(image_settings, "paper"))
    assert caught.value.code == "IMAGE_PROVIDER_INVALID_RESPONSE"


@pytest.mark.parametrize(
    "content",
    [
        b"not an image",
        png_bytes(size=(255, 300)),
        png_bytes(image_format="GIF"),
    ],
)
def test_adapter_rejects_invalid_small_or_unsupported_image(image_settings, adapter_http, content):
    adapter_http(lambda request: httpx.Response(200, json=b64_body(content)))
    with pytest.raises(ApiError) as caught:
        asyncio.run(image_provider.generate_background(image_settings, "paper"))
    assert caught.value.code == "IMAGE_PROVIDER_INVALID_RESPONSE"


class Chunks(httpx.AsyncByteStream):
    def __init__(self, chunks):
        self.chunks = chunks
        self.read_count = 0
        self.closed = False

    async def __aiter__(self):
        for chunk in self.chunks:
            self.read_count += 1
            yield chunk

    async def aclose(self):
        self.closed = True


@pytest.mark.parametrize("download", [False, True])
def test_adapter_bounds_streaming_without_content_length(
    image_settings, adapter_http, monkeypatch, download
):
    stream = Chunks([b"a" * 9, b"b" * 9, b"must-not-be-read"])
    monkeypatch.setattr(image_provider, "MAX_IMAGE_BYTES" if download else "MAX_RESPONSE_BYTES", 16)

    def handler(request):
        if download and request.method == "POST":
            return httpx.Response(
                200, json={"data": [{"url": "https://cdn.example.invalid/image"}]}
            )
        return httpx.Response(200, stream=stream)

    adapter_http(handler)
    with pytest.raises(ApiError) as caught:
        asyncio.run(image_provider.generate_background(image_settings, "paper"))
    assert caught.value.code == "IMAGE_PROVIDER_INVALID_RESPONSE"
    assert stream.read_count == 2 and stream.closed


def test_adapter_bounds_decoded_base64(image_settings, adapter_http, monkeypatch):
    monkeypatch.setattr(image_provider, "MAX_IMAGE_BYTES", 16)
    adapter_http(lambda request: httpx.Response(200, json=b64_body()))
    with pytest.raises(ApiError) as caught:
        asyncio.run(image_provider.generate_background(image_settings, "paper"))
    assert caught.value.code == "IMAGE_PROVIDER_INVALID_RESPONSE"


@pytest.mark.parametrize(
    "updates",
    [
        {"image_provider_name": "unconfigured"},
        {"image_provider_api_key": None},
        {"image_provider_api_key": SecretStr("")},
        {"image_provider_model": ""},
        {"image_provider_endpoint": ""},
        {"image_provider_endpoint": "https://127.0.0.1"},
    ],
)
def test_adapter_unconfigured_never_calls_upstream(image_settings, adapter_http, updates):
    state = adapter_http(lambda request: pytest.fail("Unconfigured provider must not bill"))
    with pytest.raises(ApiError) as caught:
        asyncio.run(
            image_provider.generate_background(image_settings.model_copy(update=updates), "paper")
        )
    assert (caught.value.status_code, caught.value.code) == (503, "IMAGE_PROVIDER_UNCONFIGURED")
    assert state.requests == []


def test_models_discovery_sanitizes_and_caps_results(adapter_http):
    rows = [{"id": "fixture-art-model", "credential": IMAGE_KEY, "owned_by": "private"}]
    rows += [None, "bad", {}, {"id": 2}, {"id": ""}, {"id": "x" * 161}]
    rows += [{"id": "model-" + str(i), "extra": IMAGE_KEY} for i in range(600)]
    state = adapter_http(lambda request: httpx.Response(200, json={"data": rows}))
    result = asyncio.run(image_provider.available_models(ENDPOINT, IMAGE_KEY))
    assert len(result) == 500 and result[0] == {"id": "fixture-art-model"}
    assert all(set(item) == {"id"} for item in result)
    assert IMAGE_KEY not in json.dumps(result)
    assert str(state.requests[0].url) == "https://images.example.invalid/v1/models"
    assert state.requests[0].headers["authorization"] == "Bearer " + IMAGE_KEY


def test_models_discovery_bounds_stream(adapter_http):
    stream = Chunks([b" " * (1024 * 1024), b" " * (1024 * 1024), b" ", b"never"])
    adapter_http(lambda request: httpx.Response(200, stream=stream))
    with pytest.raises(ApiError) as caught:
        asyncio.run(image_provider.available_models(ENDPOINT, IMAGE_KEY))
    assert caught.value.code == "IMAGE_PROVIDER_INVALID_RESPONSE"
    assert stream.read_count == 3 and stream.closed


def config_payload(**updates):
    return {
        "provider_name": "volcengine-ark",
        "provider_endpoint": "https://vision.example.invalid/api/v3/chat/completions",
        "provider_model": "fixture-vision-model",
        "provider_timeout_seconds": 20,
        "map_web_key": "synthetic-public-map-key",
        **updates,
    }


@pytest.fixture
def configured_context(context):
    context.app.state.settings.system_config_encryption_key = SecretStr(
        Fernet.generate_key().decode()
    )
    response = context.client.put(
        CONFIG_PATH,
        headers=context.admin,
        json=config_payload(
            provider_api_key=VISION_KEY,
            image_provider_name="openai-compatible",
            image_provider_endpoint="https://images.example.invalid/v1",
            image_provider_model="fixture-art-model",
            image_provider_timeout_seconds=45,
            image_provider_size="1024x1536",
            image_provider_quality="high",
            image_provider_api_key=IMAGE_KEY,
        ),
    )
    assert response.status_code == 200, response.text
    return context


def test_image_config_independent_encryption_redaction_and_fresh_reader(configured_context):
    ctx = configured_context
    response = ctx.client.get(CONFIG_PATH, headers=ctx.admin)
    assert response.status_code == 200
    assert response.json()["image_provider_api_key_configured"] is True
    assert response.json()["provider_api_key_configured"] is True
    assert response.json()["image_provider_endpoint"] == ENDPOINT
    assert "image_provider_api_key" not in response.json()
    assert "provider_api_key" not in response.json()
    assert IMAGE_KEY not in response.text and VISION_KEY not in response.text
    with ctx.app.state.database.session() as session:
        stored = session.get(Setting, system_config.CONFIG_KEY).value
        assert IMAGE_KEY not in json.dumps(stored) and VISION_KEY not in json.dumps(stored)
        cipher = system_config.cipher(ctx.app.state.settings)
        assert cipher.decrypt(stored["encrypted_image_api_key"].encode()).decode() == IMAGE_KEY
        assert cipher.decrypt(stored["encrypted_api_key"].encode()).decode() == VISION_KEY
        audits = session.query(Audit).filter(Audit.entity_type == "system_config").all()
        assert len(audits) == 1
        assert audits[0].detail["image_provider_key_action"] == "replaced"
        assert all(IMAGE_KEY not in json.dumps(row.detail) for row in audits)
        assert all(VISION_KEY not in json.dumps(row.detail) for row in audits)
        assert all(
            stored["encrypted_image_api_key"] not in json.dumps(row.detail) for row in audits
        )

    # A separate app/engine proves configuration is not an in-memory-only write.
    from backend.app.main import create_app

    second = create_app(settings=ctx.app.state.settings)
    try:
        with second.state.database.session() as session:
            image = system_config.image_effective(session, second.state.settings)
            vision = system_config.effective(session, second.state.settings)
            assert image.image_provider_model == "fixture-art-model"
            assert image.image_provider_api_key.get_secret_value() == IMAGE_KEY
            assert vision.provider_api_key.get_secret_value() == VISION_KEY
            assert image.image_provider_timeout_seconds == 45
    finally:
        second.state.database.engine.dispose()


def test_old_client_and_empty_key_preserve_all_image_fields(configured_context):
    ctx = configured_context
    with ctx.app.state.database.session() as session:
        before = dict(session.get(Setting, system_config.CONFIG_KEY).value)
    for updates in ({}, {"image_provider_api_key": ""}):
        response = ctx.client.put(
            CONFIG_PATH,
            headers=ctx.admin,
            json=config_payload(
                map_web_key="changed-public-map", provider_model="new-vision-only", **updates
            ),
        )
        assert response.status_code == 200, response.text
        assert response.json()["image_provider_api_key_configured"] is True
        for field in system_config.IMAGE_FIELDS:
            assert response.json()[field] == before[field]
        with ctx.app.state.database.session() as session:
            after = session.get(Setting, system_config.CONFIG_KEY).value
            assert after["encrypted_image_api_key"] == before["encrypted_image_api_key"]
            assert after["encrypted_api_key"] == before["encrypted_api_key"]
    public = ctx.client.get("/api/v1/public/map-config")
    assert public.status_code == 200 and public.headers["cache-control"] == "no-store"
    assert public.json()["web_key"] == "changed-public-map"
    assert set(public.json()) == {"web_key", "center_longitude", "center_latitude", "default_zoom"}
    assert IMAGE_KEY not in public.text and VISION_KEY not in public.text


@pytest.mark.parametrize("clear_image_first", [True, False])
def test_image_and_vision_key_clear_are_independent_and_disable_env_fallback(
    configured_context, clear_image_first
):
    ctx = configured_context
    settings = ctx.app.state.settings
    settings.image_provider_api_key = SecretStr("synthetic-env-image")
    settings.provider_api_key = SecretStr("synthetic-env-vision")
    first = "clear_image_provider_api_key" if clear_image_first else "clear_provider_api_key"
    response = ctx.client.put(CONFIG_PATH, headers=ctx.admin, json=config_payload(**{first: True}))
    assert response.status_code == 200, response.text
    assert response.json()["image_provider_api_key_configured"] is (not clear_image_first)
    assert response.json()["provider_api_key_configured"] is clear_image_first
    second = "clear_provider_api_key" if clear_image_first else "clear_image_provider_api_key"
    response = ctx.client.put(CONFIG_PATH, headers=ctx.admin, json=config_payload(**{second: True}))
    assert response.status_code == 200, response.text
    with ctx.app.state.database.session() as session:
        assert system_config.image_effective(session, settings).image_provider_api_key is None
        assert system_config.effective(session, settings).provider_api_key is None
        data = session.get(Setting, system_config.CONFIG_KEY).value
        assert "encrypted_image_api_key" not in data and "encrypted_api_key" not in data
    # A deliberate replacement re-enables only the image key after clearing.
    response = ctx.client.put(
        CONFIG_PATH,
        headers=ctx.admin,
        json=config_payload(image_provider_api_key="synthetic-replacement-image"),
    )
    assert response.status_code == 200, response.text
    assert response.json()["image_provider_api_key_configured"] is True
    assert response.json()["provider_api_key_configured"] is False
    with ctx.app.state.database.session() as session:
        assert system_config.image_effective(
            session, settings
        ).image_provider_api_key.get_secret_value() == ("synthetic-replacement-image")
        audits = session.query(Audit).filter(Audit.entity_type == "system_config").all()
        assert {row.detail["image_provider_key_action"] for row in audits} == {
            "replaced",
            "cleared",
            "unchanged",
        }
        assert all("synthetic-replacement-image" not in json.dumps(row.detail) for row in audits)


def test_image_config_is_admin_only(context):
    paths = [
        ("GET", CONFIG_PATH, None),
        ("PUT", CONFIG_PATH, config_payload()),
        ("POST", CONFIG_PATH + "/image-models", {"endpoint": ENDPOINT}),
    ]
    for method, path, body in paths:
        response = context.client.request(method, path, json=body)
        assert response.status_code == 401
    for role in ("tourist", "operator", "merchant"):
        merchant_id = context.merchant()["id"] if role == "merchant" else None
        _, headers = context.actor(role, merchant_id)
        for method, path, body in paths:
            response = context.client.request(method, path, headers=headers, json=body)
            assert response.status_code == 403, response.text


def test_image_key_requires_encryption_and_conflicts_roll_back(configured_context):
    ctx = configured_context
    with ctx.app.state.database.session() as session:
        before = dict(session.get(Setting, system_config.CONFIG_KEY).value)
        audit_count = session.query(Audit).filter(Audit.entity_type == "system_config").count()
    response = ctx.client.put(
        CONFIG_PATH,
        headers=ctx.admin,
        json=config_payload(
            image_provider_api_key="synthetic-conflict", clear_image_provider_api_key=True
        ),
    )
    assert_error(response, 422, "INVALID_REQUEST")
    ctx.app.state.settings.system_config_encryption_key = None
    response = ctx.client.put(
        CONFIG_PATH,
        headers=ctx.admin,
        json=config_payload(image_provider_api_key="synthetic-replacement"),
    )
    assert_error(response, 503, "CONFIG_ENCRYPTION_UNAVAILABLE")
    with ctx.app.state.database.session() as session:
        assert session.get(Setting, system_config.CONFIG_KEY).value == before
        assert (
            session.query(Audit).filter(Audit.entity_type == "system_config").count() == audit_count
        )


def test_models_route_uses_only_image_key_and_never_sends_saved_key_to_new_host(
    configured_context, adapter_http
):
    ctx = configured_context
    state = adapter_http(
        lambda request: httpx.Response(
            200, json={"data": [{"id": "fixture-art-model", "private": IMAGE_KEY}]}
        )
    )
    path = CONFIG_PATH + "/image-models"
    response = ctx.client.post(path, headers=ctx.admin, json={"endpoint": ENDPOINT})
    assert response.status_code == 200, response.text
    assert response.json() == {"items": [{"id": "fixture-art-model"}]}
    assert state.requests[0].headers["authorization"] == "Bearer " + IMAGE_KEY
    response = ctx.client.post(
        path, headers=ctx.admin, json={"endpoint": "https://new.example.invalid/v1"}
    )
    assert_error(response, 422, "IMAGE_PROVIDER_KEY_REQUIRED")
    assert len(state.requests) == 1
    response = ctx.client.post(
        path,
        headers=ctx.admin,
        json={"endpoint": "https://new.example.invalid/v1", "api_key": "synthetic-unsaved-key"},
    )
    assert response.status_code == 200, response.text
    assert state.requests[-1].headers["authorization"] == "Bearer synthetic-unsaved-key"
    with ctx.app.state.database.session() as session:
        active = system_config.image_effective(session, ctx.app.state.settings)
        assert active.image_provider_endpoint == ENDPOINT
        assert active.image_provider_api_key.get_secret_value() == IMAGE_KEY
    response = ctx.client.post(
        path, headers=ctx.admin, json={"endpoint": ENDPOINT, "clear_api_key": True}
    )
    assert_error(response, 503, "IMAGE_PROVIDER_UNCONFIGURED")
    assert len(state.requests) == 2


@pytest.fixture
def held_jobs(monkeypatch):
    """Keep the real worker callable, but control when TestClient runs it."""
    tasks = []

    def add_task(self, func, *args, **kwargs):
        tasks.append(SimpleNamespace(func=func, args=args, kwargs=kwargs))

    monkeypatch.setattr(BackgroundTasks, "add_task", add_task)
    return tasks


def run_job(task):
    asyncio.run(task.func(*task.args, **task.kwargs))


@pytest.fixture
def poster_context(configured_context, monkeypatch):
    ctx = configured_context
    owner, headers = ctx.actor()
    characters = []
    colors = [(220, 20, 30), (20, 180, 40), (30, 50, 210)]
    for index, color in enumerate(colors):
        uploaded = ctx.client.post(
            "/api/v1/media",
            headers=ctx.admin,
            files={"file": (f"fixture-{index}.png", png_bytes(color, (128, 128)), "image/png")},
        )
        assert uploaded.status_code == 200, uploaded.text
        character = ctx.create(
            "characters",
            {
                "cn_name": f"Fixture {index}",
                "culture_summary": "Synthetic fixture only",
                "source_ref": "synthetic:ai-poster-test",
                "image_url": uploaded.json()["url"],
                "status": "published",
            },
        )
        collected = ctx.client.put(f"/api/v1/me/favorites/{character['id']}", headers=headers)
        assert collected.status_code == 200, collected.text
        characters.append(character)
    background = Image.new("RGB", (900, 1400), (30, 60, 90))
    generate = AsyncMock(return_value=background)
    monkeypatch.setattr(poster_jobs, "generate_poster_art", generate)
    body = {
        "request_id": "fixture-poster-request-0001",
        "character_ids": [characters[1]["id"], characters[0]["id"], characters[2]["id"]],
        "template": "mountain",
        "caption": "  Fixture   caption  ",
    }
    return SimpleNamespace(
        ctx=ctx,
        owner=owner,
        headers=headers,
        characters=characters,
        colors=colors,
        generate=generate,
        background=background,
        body=body,
    )


def submit(poster):
    response = poster.ctx.client.post(JOBS_PATH, headers=poster.headers, json=poster.body)
    assert response.status_code == 202, response.text
    return response.json()


def poster_events(ctx):
    with ctx.app.state.database.session() as session:
        return session.query(Event).filter(Event.event == "poster_generate").count()


def test_jobs_are_owner_only_idempotent_entities_with_all_success_states(poster_context, held_jobs):
    p = poster_context
    ctx = p.ctx
    assert ctx.client.post(JOBS_PATH, json=p.body).status_code == 401
    first = submit(p)
    assert first["status"] == "queued"
    assert set(first) == {"id", "status"}
    identifier = first["id"]
    path = JOBS_PATH + "/" + identifier
    assert ctx.client.get(path).status_code == 401
    assert ctx.client.get(path, headers=p.headers).json() == first
    assert submit(p) == first and len(held_jobs) == 1
    p.generate.assert_not_awaited()
    with ctx.app.state.database.session() as session:
        row = session.get(Entity, identifier)
        assert row.kind == poster_jobs.JOB_KIND and row.status == "queued"
        assert row.data["owner"] == p.owner["id"]
        assert len(row.data["fingerprint"]) == 64
        assert IMAGE_KEY not in json.dumps(row.data)
    _, stranger = ctx.actor()
    for headers in (stranger, ctx.admin):
        assert_error(ctx.client.get(path, headers=headers), 404, "NOT_FOUND")

    async def during_generation(active, template, materials, records, caption, with_code):
        assert active.image_provider_api_key.get_secret_value() == IMAGE_KEY
        assert active.image_provider_model == "fixture-art-model" and template == "mountain"
        generating = ctx.client.get(path, headers=p.headers)
        assert generating.json() == {"id": identifier, "status": "generating"}
        assert submit(p) == generating.json() and len(held_jobs) == 1
        return p.background

    p.generate.side_effect = during_generation
    run_job(held_jobs[0])
    completed = ctx.client.get(path, headers=p.headers)
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert completed.json()["share_code_available"] is False
    assert set(completed.json()) == {"id", "status", "url", "share_code_available"}
    assert submit(p) == completed.json() and len(held_jobs) == 1
    run_job(held_jobs[0])  # A duplicate terminal delivery must not re-bill either.
    p.generate.assert_awaited_once()
    assert poster_events(ctx) == 1
    with ctx.app.state.database.session() as session:
        assert session.query(Entity).filter(Entity.kind == poster_jobs.JOB_KIND).count() == 1


@pytest.mark.parametrize(
    "origin", ["http://127.0.0.1:8010", "http://localhost:8010", "https://[::1]:8010"]
)
def test_legacy_poster_download_reuses_exact_image_and_owner_job(poster_context, held_jobs, origin):
    p = poster_context
    job = submit(p)
    run_job(held_jobs[0])
    path = JOBS_PATH + "/" + job["id"]
    completed = p.ctx.client.get(path, headers=p.headers).json()
    relative_url = completed["url"]
    assert relative_url.startswith("/api/v1/media/")
    original = p.ctx.client.get(relative_url)
    assert original.status_code == 200
    assert original.headers["content-type"] == "image/png"
    with p.ctx.app.state.database.write() as session:
        row = session.get(Entity, job["id"])
        row.data = {**row.data, "url": origin + relative_url}
    # Legacy jobs return a usable URL, but the stored record, image and event remain intact.
    recovered = p.ctx.client.get(path, headers=p.headers).json()
    assert recovered == completed
    assert p.ctx.client.get(recovered["url"]).content == original.content
    assert submit(p) == recovered and len(held_jobs) == 1
    assert p.ctx.client.get(path).status_code == 401
    _, stranger = p.ctx.actor()
    assert_error(p.ctx.client.get(path, headers=stranger), 404, "NOT_FOUND")
    with p.ctx.app.state.database.session() as session:
        row = session.get(Entity, job["id"])
        assert row.data["url"] == origin + relative_url
        assert session.query(Entity).filter(Entity.kind == poster_jobs.JOB_KIND).count() == 1
    p.generate.assert_awaited_once()
    assert poster_events(p.ctx) == 1


@pytest.mark.parametrize(
    "url",
    [
        "/api/v1/media/" + "a" * 32 + ".png",
        "https://cdn.example.invalid/api/v1/media/" + "a" * 32 + ".png",
        "http://127.0.0.1:8010/unrelated.png",
        "http://127.0.0.1:8010/api/v1/media/../private.png",
        "http://127.0.0.1:8010/api/v1/media/" + "a" * 32 + ".png?token=fixture",
        "http://127.0.0.1:8010/api/v1/media/" + "a" * 32 + ".png#fragment",
        "http://fixture@localhost/api/v1/media/" + "a" * 32 + ".png",
    ],
)
def test_poster_url_normalization_leaves_unrelated_urls_unchanged(url):
    assert poster_jobs.poster_media_url(url) == url


def test_same_token_changed_caption_template_or_selection_conflicts(poster_context, held_jobs):
    p = poster_context
    submit(p)
    for change in (
        {"caption": "Different caption"},
        {"template": "paper"},
        {"character_ids": list(reversed(p.body["character_ids"]))},
        {"character_ids": p.body["character_ids"][:1]},
    ):
        response = p.ctx.client.post(JOBS_PATH, headers=p.headers, json={**p.body, **change})
        assert_error(response, 409, "POSTER_REQUEST_CONFLICT")
    assert len(held_jobs) == 1
    p.generate.assert_not_awaited()


def test_same_token_belongs_to_each_owner_separately(poster_context, held_jobs):
    p = poster_context
    first = submit(p)
    other, headers = p.ctx.actor()
    for identifier in p.body["character_ids"]:
        response = p.ctx.client.put(f"/api/v1/me/favorites/{identifier}", headers=headers)
        assert response.status_code == 200
    response = p.ctx.client.post(JOBS_PATH, headers=headers, json=p.body)
    assert response.status_code == 202
    second = response.json()
    assert second["id"] != first["id"] and len(held_jobs) == 2
    assert_error(
        p.ctx.client.get(JOBS_PATH + "/" + second["id"], headers=p.headers), 404, "NOT_FOUND"
    )
    with p.ctx.app.state.database.session() as session:
        assert session.get(Entity, second["id"]).data["owner"] == other["id"]


@pytest.mark.parametrize(
    "failure,code",
    [
        (
            ApiError(502, "IMAGE_PROVIDER_AUTH_FAILED", "upstream " + IMAGE_KEY),
            "IMAGE_PROVIDER_AUTH_FAILED",
        ),
        (
            ApiError(504, "IMAGE_PROVIDER_TIMEOUT", "upstream " + IMAGE_KEY),
            "IMAGE_PROVIDER_TIMEOUT",
        ),
        (RuntimeError("private upstream " + IMAGE_KEY), "IMAGE_PROVIDER_UNAVAILABLE"),
    ],
)
def test_failed_jobs_are_sanitized_terminal_and_never_rebill(
    poster_context, held_jobs, failure, code
):
    p = poster_context
    p.generate.side_effect = failure
    job = submit(p)
    run_job(held_jobs[0])
    response = p.ctx.client.get(JOBS_PATH + "/" + job["id"], headers=p.headers)
    assert response.json() == {"id": job["id"], "status": "failed", "error_code": code}
    assert IMAGE_KEY not in response.text
    assert submit(p) == response.json() and len(held_jobs) == 1
    run_job(held_jobs[0])
    p.generate.assert_awaited_once()
    assert poster_events(p.ctx) == 0
    with p.ctx.app.state.database.session() as session:
        data = session.get(Entity, job["id"]).data
        assert "url" not in data and IMAGE_KEY not in json.dumps(data)
    poster_files = [
        path
        for path in p.ctx.app.state.settings.media_directory.glob("*.json")
        if json.loads(path.read_text(encoding="utf-8")).get("kind") == "poster"
    ]
    assert poster_files == []


@pytest.mark.parametrize("status", ["queued", "generating"])
def test_expired_jobs_fail_persistently_without_retrying_or_rebilling(
    poster_context, held_jobs, status
):
    p = poster_context
    job = submit(p)
    with p.ctx.app.state.database.write() as session:
        row = session.get(Entity, job["id"])
        row.status = status
        row.created_at = (datetime.now(UTC) - timedelta(minutes=9)).isoformat()
    response = p.ctx.client.get(JOBS_PATH + "/" + job["id"], headers=p.headers)
    assert response.json() == {
        "id": job["id"],
        "status": "failed",
        "error_code": "IMAGE_PROVIDER_TIMEOUT",
    }
    assert submit(p) == response.json() and len(held_jobs) == 1
    run_job(held_jobs[0])
    p.generate.assert_not_awaited()
    assert poster_events(p.ctx) == 0
    with p.ctx.app.state.database.session() as session:
        assert session.get(Entity, job["id"]).status == "failed"


def test_unknown_job_and_non_job_entity_are_not_found(poster_context):
    p = poster_context
    for identifier in ("missing-job", p.characters[0]["id"]):
        response = p.ctx.client.get(JOBS_PATH + "/" + identifier, headers=p.headers)
        assert_error(response, 404, "NOT_FOUND")


def test_unconfigured_image_is_unavailable_before_job_creation(poster_context, held_jobs):
    p = poster_context
    response = p.ctx.client.put(
        CONFIG_PATH, headers=p.ctx.admin, json=config_payload(clear_image_provider_api_key=True)
    )
    assert response.status_code == 200
    response = p.ctx.client.post(JOBS_PATH, headers=p.headers, json=p.body)
    assert_error(response, 503, "IMAGE_PROVIDER_UNCONFIGURED")
    p.generate.assert_not_awaited()
    assert held_jobs == [] and poster_events(p.ctx) == 0
    with p.ctx.app.state.database.session() as session:
        assert session.query(Entity).filter(Entity.kind == poster_jobs.JOB_KIND).count() == 0


def test_noncollected_glyph_is_denied_before_job_or_ai_charge(poster_context, held_jobs):
    p = poster_context
    uncollected = p.ctx.character()
    response = p.ctx.client.post(
        JOBS_PATH, headers=p.headers, json={**p.body, "character_ids": [uncollected["id"]]}
    )
    assert_error(response, 403, "CHARACTER_NOT_COLLECTED")
    p.generate.assert_not_awaited()
    assert held_jobs == [] and poster_events(p.ctx) == 0


@pytest.mark.parametrize(
    "problem,code,status",
    [
        ("unpublished", "CHARACTER_NOT_FOUND", 404),
        ("missing-image", "CHARACTER_IMAGE_UNAVAILABLE", 409),
    ],
)
def test_collected_but_unavailable_approved_art_is_rejected_before_ai(
    poster_context, held_jobs, problem, code, status
):
    p = poster_context
    identifier = p.body["character_ids"][0]
    with p.ctx.app.state.database.write() as session:
        row = session.get(Entity, identifier)
        if problem == "unpublished":
            row.status = "draft"
        else:
            row.data = {**row.data, "image_url": "/api/v1/media/" + "f" * 32 + ".png"}
    response = p.ctx.client.post(JOBS_PATH, headers=p.headers, json=p.body)
    assert_error(response, status, code)
    p.generate.assert_not_awaited()
    assert held_jobs == []


def test_full_design_sends_approved_materials_and_preserves_complete_ai_art(poster_context):
    p = poster_context
    job = submit(p)  # Real job lifecycle and PNG save; only upstream artwork is synthetic.
    response = p.ctx.client.get(JOBS_PATH + "/" + job["id"], headers=p.headers)
    assert response.json()["status"] == "completed", response.text
    assert response.json()["share_code_available"] is False
    active, template, materials, records, caption, with_code = p.generate.await_args.args
    assert [row["image_url"] for row in records] == [
        p.characters[index]["image_url"] for index in (1, 0, 2)
    ]
    assert template == "mountain" and with_code is False
    assert caption == "Fixture caption"
    assert [part[0] for part in materials] == [
        "design-reference.png",
        "glyph-1.png",
        "glyph-2.png",
        "glyph-3.png",
    ]
    for part, index in zip(materials[1:], (1, 0, 2), strict=True):
        with Image.open(BytesIO(part[1])) as glyph:
            assert glyph.convert("RGB").getpixel((64, 64)) == p.colors[index]
    result = p.ctx.client.get(response.json()["url"])
    assert result.status_code == 200
    with Image.open(BytesIO(result.content)) as image:
        assert image.format == "PNG" and image.size == (900, 1400)
        assert image.tobytes() == p.background.tobytes()
        # No WeChat credentials: the QR area stays artwork, not a fake QR.
        assert image.crop((680, 1170, 800, 1290)).getextrema() == ((30, 30), (60, 60), (90, 90))
    p.generate.assert_awaited_once()
    assert poster_events(p.ctx) == 1


def test_wechat_code_failure_does_not_block_real_poster_or_fake_code(poster_context, monkeypatch):
    p = poster_context
    qr = AsyncMock(
        side_effect=ApiError(502, "WECHAT_SHARE_UNAVAILABLE", "Synthetic WeChat failure")
    )
    monkeypatch.setattr(poster_jobs, "wechat_share_code", qr)
    job = submit(p)
    response = p.ctx.client.get(JOBS_PATH + "/" + job["id"], headers=p.headers)
    assert response.json()["status"] == "completed"
    assert response.json()["share_code_available"] is False
    qr.assert_awaited_once()
    p.generate.assert_awaited_once()
    assert poster_events(p.ctx) == 1
    result = p.ctx.client.get(response.json()["url"])
    assert result.status_code == 200
    with Image.open(BytesIO(result.content)) as image:
        assert image.format == "PNG" and image.size == (900, 1400)
        assert image.crop((680, 1170, 800, 1290)).getextrema() == ((30, 30), (60, 60), (90, 90))


def test_optional_share_code_does_not_swallow_unrelated_errors(image_settings, monkeypatch):
    qr = AsyncMock(side_effect=ApiError(503, "UNEXPECTED_FAILURE", "Synthetic failure"))
    monkeypatch.setattr(poster_jobs, "wechat_share_code", qr)
    with pytest.raises(ApiError) as error:
        asyncio.run(poster_jobs.optional_share_code(image_settings))
    assert error.value.code == "UNEXPECTED_FAILURE"


def test_optional_share_code_preserves_real_code(image_settings, monkeypatch):
    content = png_bytes()
    qr = AsyncMock(return_value=content)
    monkeypatch.setattr(poster_jobs, "wechat_share_code", qr)
    assert asyncio.run(poster_jobs.optional_share_code(image_settings)) == content
    qr.assert_awaited_once_with(image_settings, "poster")


def test_wechat_and_image_failure_still_fails_without_placeholder(poster_context, monkeypatch):
    p = poster_context
    monkeypatch.setattr(
        poster_jobs,
        "wechat_share_code",
        AsyncMock(side_effect=ApiError(502, "WECHAT_SHARE_UNAVAILABLE", "Synthetic failure")),
    )
    p.generate.side_effect = ApiError(502, "IMAGE_PROVIDER_UNAVAILABLE", "Synthetic failure")
    job = submit(p)
    response = p.ctx.client.get(JOBS_PATH + "/" + job["id"], headers=p.headers)
    assert response.json()["status"] == "failed"
    assert response.json()["error_code"] == "IMAGE_PROVIDER_UNAVAILABLE"
    p.generate.assert_awaited_once()
    assert poster_events(p.ctx) == 0


def test_missing_wechat_credentials_honestly_returns_no_code(image_settings):
    assert asyncio.run(media.wechat_share_code(image_settings, "poster")) is None


def test_models_route_normalizes_environment_base_url_before_using_saved_key(context, adapter_http):
    settings = context.app.state.settings
    settings.image_provider_name = "openai-compatible"
    settings.image_provider_endpoint = "https://images.example.invalid/v1"
    settings.image_provider_model = "fixture-art-model"
    settings.image_provider_api_key = SecretStr(IMAGE_KEY)
    state = adapter_http(lambda request: httpx.Response(200, json={"data": [{"id": "fixture"}]}))
    response = context.client.post(
        CONFIG_PATH + "/image-models", headers=context.admin, json={"endpoint": ENDPOINT}
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"items": [{"id": "fixture"}]}
    assert len(state.requests) == 1
    assert str(state.requests[0].url) == "https://images.example.invalid/v1/models"
    assert state.requests[0].headers["authorization"] == "Bearer " + IMAGE_KEY


@pytest.mark.parametrize("status", ["queued", "generating"])
def test_delayed_worker_fails_expired_job_without_needing_a_poll(poster_context, held_jobs, status):
    p = poster_context
    job = submit(p)
    with p.ctx.app.state.database.write() as session:
        row = session.get(Entity, job["id"])
        row.status = status
        row.created_at = (datetime.now(UTC) - timedelta(minutes=9)).isoformat()
    run_job(held_jobs[0])
    p.generate.assert_not_awaited()
    response = p.ctx.client.get(JOBS_PATH + "/" + job["id"], headers=p.headers)
    assert response.json() == {
        "id": job["id"],
        "status": "failed",
        "error_code": "IMAGE_PROVIDER_TIMEOUT",
    }
    assert poster_events(p.ctx) == 0


def test_missing_reference_fails_before_job_creation_or_ai_charge(
    poster_context, held_jobs, monkeypatch, tmp_path
):
    p = poster_context
    monkeypatch.setattr(poster_art, "REFERENCE_PATH", tmp_path / "missing-reference.jpg")
    response = p.ctx.client.post(JOBS_PATH, headers=p.headers, json=p.body)
    assert_error(response, 503, "POSTER_REFERENCE_UNAVAILABLE")
    p.generate.assert_not_awaited()
    assert held_jobs == []


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://images.example.invalid",
        "https://images.example.invalid/v1",
        ENDPOINT,
        "https://images.example.invalid/v1/images/edits",
    ],
)
@pytest.mark.parametrize("with_code", [False, True])
@pytest.mark.parametrize("template", ["paper", "mountain", "old-town", "minimal"])
def test_full_poster_edits_sends_actual_ordered_images_and_only_approved_copy(
    image_settings, adapter_http, endpoint, with_code, template
):
    image_settings.image_provider_endpoint = endpoint
    state = adapter_http(lambda request: httpx.Response(200, json=b64_body()))
    materials = [("design-reference.png", png_bytes("tan"), "image/png")]
    materials += [
        (f"glyph-{i}.png", png_bytes(color), "image/png")
        for i, color in enumerate(("red", "blue"), 1)
    ]
    if with_code:
        materials.append(("mini-program-code.png", png_bytes("black"), "image/png"))
    records = [
        {"cn_name": "山", "id": "private-id", "meaning": "not-approved-for-copy"},
        {"cn_name": "月", "image_url": "/api/v1/media/private.png"},
    ]
    caption = "记住丽江的风，也记住此刻。"
    result = asyncio.run(
        image_provider.generate_poster_art(
            image_settings, template, materials, records, caption, with_code
        )
    )
    assert result.size == (320, 480)
    assert len(state.requests) == 1
    request = state.requests[0]
    assert str(request.url) == "https://images.example.invalid/v1/images/edits"
    assert request.headers["authorization"] == "Bearer " + IMAGE_KEY
    content_type = request.headers["content-type"]
    assert content_type.startswith("multipart/form-data;")
    message = BytesParser(policy=policy.default).parsebytes(
        ("Content-Type: " + content_type + "\r\n\r\n").encode() + request.content
    )
    parts = list(message.iter_parts())
    files = [part for part in parts if part.get_filename()]
    assert [
        (part.get_filename(), part.get_payload(decode=True), part.get_content_type())
        for part in files
    ] == materials
    assert all(part.get_param("name", header="content-disposition") == "image[]" for part in files)
    fields = {
        part.get_param("name", header="content-disposition"): part.get_payload(decode=True).decode()
        for part in parts
        if not part.get_filename()
    }
    assert fields["n"] == "1" and fields["model"] == "fixture-art-model"
    prompt = fields["prompt"]
    assert f"selected style ID {template}" in prompt
    assert image_provider.STYLES[template] in prompt
    assert prompt.index(image_provider.STYLES[template]) < prompt.index("REFERENCE PRIORITY:")
    for other_template, direction in image_provider.STYLES.items():
        assert (direction in prompt) is (other_template == template)
    assert "overrides image 1's palette" in prompt
    assert "style should refine this reference" not in prompt
    assert "Blend the scenic lower half naturally into the parchment" not in prompt
    assert caption in prompt and "我的东巴印记" in prompt
    assert json.loads(prompt.split("Exact print content: ")[1]) == {
        "ordered_glyph_labels": ["山", "月"],
        "caption": caption,
    }
    for private in ("private-id", "private.png", "not-approved-for-copy", IMAGE_KEY, VISION_KEY):
        assert private not in prompt
    assert ("The last image is the real mini-program code" in prompt) is with_code


@pytest.mark.parametrize("status", [400, 404, 429, 500])
def test_edits_failure_never_retries_or_falls_back_to_generations(
    image_settings, adapter_http, status
):
    state = adapter_http(lambda request: httpx.Response(status, json={"error": "fixture"}))
    with pytest.raises(ApiError):
        asyncio.run(
            image_provider.generate_poster_art(
                image_settings,
                "mountain",
                [("reference.png", png_bytes(), "image/png")],
                [{"cn_name": "山"}],
                "",
                False,
            )
        )
    assert len(state.requests) == 1 and state.requests[0].url.path.endswith("/images/edits")


def test_full_poster_rejects_landscape_instead_of_stretching(image_settings, adapter_http):
    adapter_http(lambda request: httpx.Response(200, json=b64_body(png_bytes(size=(480, 320)))))
    with pytest.raises(ApiError) as error:
        asyncio.run(
            image_provider.generate_poster_art(
                image_settings,
                "mountain",
                [("reference.png", png_bytes(), "image/png")],
                [{"cn_name": "山"}],
                "",
                False,
            )
        )
    assert error.value.code == "IMAGE_PROVIDER_INVALID_RESPONSE"


def test_optional_genuine_code_is_the_only_compositing_and_cannot_change_artwork():
    artwork = Image.new("RGB", (1000, 1500), "navy")
    assert poster_art.finish_poster(artwork, None).tobytes() == artwork.tobytes()
    code = Image.new("RGB", (180, 180), "white")
    code.paste("black", (10, 10, 50, 50))
    material = poster_art.png_material("code.png", code)
    result = poster_art.finish_poster(artwork, material[1])
    assert result.crop((780, 1280, 960, 1460)).tobytes() == code.tobytes()
    result.paste("navy", (780, 1280, 960, 1460))
    assert result.tobytes() == artwork.tobytes()


def test_uploaded_materials_remove_metadata_without_changing_pixels():
    source = Image.new("RGB", (40, 60), "ivory")
    exif = Image.Exif()
    exif[315] = "private-fixture-author"
    source.info["exif"] = exif.tobytes()
    source.info["icc_profile"] = b"private-fixture-profile"
    material = poster_art.png_material("glyph-1.png", source)
    with Image.open(BytesIO(material[1])) as decoded:
        assert decoded.tobytes() == source.tobytes()
        assert not decoded.getexif() and not decoded.info
    assert "exif" in source.info  # Never mutate the approved local original.


def test_full_design_does_not_depend_on_server_chinese_fonts(poster_context, monkeypatch):
    def unavailable(size):
        raise AssertionError("Full AI poster must not use local title/glyph/caption fonts")

    monkeypatch.setattr(media, "chinese_font", unavailable)
    job = submit(poster_context)
    assert (
        poster_context.ctx.client.get(
            JOBS_PATH + "/" + job["id"], headers=poster_context.headers
        ).json()["status"]
        == "completed"
    )


@pytest.mark.parametrize("operation", ["background", "models"])
def test_http_total_timeout_is_typed_and_does_not_retry(
    image_settings, adapter_http, monkeypatch, operation
):
    stream = Chunks([b"unused"])

    async def stalled(self):
        await asyncio.sleep(60)
        yield b"unreachable"

    monkeypatch.setattr(Chunks, "__aiter__", stalled)
    state = adapter_http(lambda request: httpx.Response(200, stream=stream))
    original_timeout = asyncio.timeout
    monkeypatch.setattr(image_provider.asyncio, "timeout", lambda seconds: original_timeout(0.05))
    with pytest.raises(ApiError) as caught:
        if operation == "background":
            asyncio.run(image_provider.generate_background(image_settings, "paper"))
        else:
            asyncio.run(image_provider.available_models(ENDPOINT, IMAGE_KEY))
    assert (caught.value.status_code, caught.value.code) == (504, "IMAGE_PROVIDER_TIMEOUT")
    assert len(state.requests) == 1 and stream.closed
