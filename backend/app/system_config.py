"""Runtime provider and public map configuration (OPS-03, GEO-01)."""

import ipaddress
from typing import Literal
from urllib.parse import urlsplit

from cryptography.fernet import Fernet, InvalidToken
from pydantic import BaseModel, Field, SecretStr, field_validator
from sqlalchemy.orm import Session

from backend.app.config import Settings
from backend.app.errors import ApiError
from backend.app.provider_factory import create_provider
from backend.app.provider_status import RecognitionServiceStatus, describe_provider

from .business.models import Setting

CONFIG_KEY = "runtime_system_config"
IMAGE_FIELDS = (
    "image_provider_name",
    "image_provider_endpoint",
    "image_provider_model",
    "image_provider_timeout_seconds",
    "image_provider_size",
    "image_provider_quality",
)


class SystemConfigPublic(BaseModel):
    provider_name: str
    provider_endpoint: str
    provider_model: str
    provider_timeout_seconds: float
    provider_api_key_configured: bool
    local_model_version: str
    local_model_threads: int
    recognition_service: RecognitionServiceStatus
    image_provider_name: str
    image_provider_endpoint: str
    image_provider_model: str
    image_provider_timeout_seconds: float
    image_provider_size: str
    image_provider_quality: str
    image_provider_api_key_configured: bool
    key_editable: bool
    map_web_key: str
    map_center_longitude: float
    map_center_latitude: float
    map_default_zoom: int


class SystemConfigUpdate(BaseModel):
    image_provider_name: Literal["unconfigured", "openai-compatible"] = "unconfigured"
    image_provider_endpoint: str = Field(default="", max_length=500)
    image_provider_model: str = Field(default="", max_length=160)
    image_provider_timeout_seconds: float = Field(default=180, ge=10, le=240)
    image_provider_size: Literal["1024x1536", "1024x1024", "1536x1024", "auto"] = "1024x1536"
    image_provider_quality: Literal["auto", "low", "medium", "high", "standard", "hd"] = "auto"
    image_provider_api_key: str = Field(default="", max_length=4096, repr=False)
    clear_image_provider_api_key: bool = False
    provider_name: str = Field(max_length=40)
    provider_endpoint: str = Field(max_length=500)
    provider_model: str = Field(max_length=160)
    provider_timeout_seconds: float = Field(gt=0, le=60)
    provider_api_key: str = Field(default="", max_length=4096, repr=False)
    clear_provider_api_key: bool = False
    map_web_key: str = Field(max_length=256)
    map_center_longitude: float = Field(default=100.235, ge=73, le=135)
    map_center_latitude: float = Field(default=26.875, ge=3, le=54)
    map_default_zoom: int = Field(default=12, ge=3, le=18)

    @field_validator("image_provider_endpoint")
    @classmethod
    def valid_image_endpoint(cls, value: str) -> str:
        from backend.app.image_provider import normalize_endpoint

        return normalize_endpoint(value) if value.strip() else ""

    @field_validator("provider_name")
    @classmethod
    def valid_provider(cls, value: str) -> str:
        if value.strip().lower() not in {
            "unconfigured",
            "local",
            "db1404-local",
            "ark",
            "volcengine",
            "volcengine-ark",
        }:
            raise ValueError("Unsupported provider")
        name = value.strip().lower()
        return {
            "local": "db1404-local",
            "ark": "volcengine-ark",
            "volcengine": "volcengine-ark",
        }.get(name, name)

    @field_validator("provider_endpoint")
    @classmethod
    def valid_endpoint(cls, value: str) -> str:
        value = value.strip()
        if not value:
            return value
        try:
            parsed = urlsplit(value)
            host = parsed.hostname or ""
            if (
                parsed.scheme != "https"
                or not host
                or parsed.username
                or parsed.password
                or parsed.fragment
                or parsed.query
                or parsed.port not in (None, 443)
            ):
                raise ValueError("Invalid HTTPS endpoint")
            if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
                raise ValueError("Local endpoints are not allowed")
            try:
                address = ipaddress.ip_address(host)
            except ValueError:
                address = None
            if address is not None and not address.is_global:
                raise ValueError("Private IP endpoints are not allowed")
        except ValueError as exc:
            raise ValueError("Provider endpoint must be a public HTTPS URL") from exc
        return (
            value
            if parsed.path.rstrip("/").endswith("/chat/completions")
            else (value.rstrip("/") + "/chat/completions")
        )


def stored(session: Session) -> dict:
    record = session.get(Setting, CONFIG_KEY)
    return record.value if record else {}


class ImageModelsInput(BaseModel):
    endpoint: str = Field(max_length=500)
    api_key: str = Field(default="", max_length=4096, repr=False)
    clear_api_key: bool = False

    @field_validator("endpoint")
    @classmethod
    def endpoint_valid(cls, value: str) -> str:
        from backend.app.image_provider import normalize_endpoint

        return normalize_endpoint(value)


def cipher(settings: Settings) -> Fernet:
    secret = settings.system_config_encryption_key
    if not secret or not secret.get_secret_value():
        raise ApiError(
            503, "CONFIG_ENCRYPTION_UNAVAILABLE", "Server encryption key is not configured"
        )
    try:
        return Fernet(secret.get_secret_value().encode())
    except (ValueError, TypeError) as exc:
        raise ApiError(
            503, "CONFIG_ENCRYPTION_UNAVAILABLE", "Server encryption key is invalid"
        ) from exc


def effective(session: Session, settings: Settings) -> Settings:
    data = stored(session)
    if not data:
        return settings
    override = {
        key: data[key]
        for key in (
            "provider_name",
            "provider_endpoint",
            "provider_model",
            "provider_timeout_seconds",
        )
        if key in data
    }
    name = override.get("provider_name", settings.provider_name).strip().lower()
    if name in {"local", "db1404-local", "unconfigured"}:
        # The retained external key is unrelated to local inference (D-088).
        override["provider_api_key"] = None
    elif data.get("encrypted_api_key"):
        try:
            override["provider_api_key"] = SecretStr(
                cipher(settings).decrypt(data["encrypted_api_key"].encode()).decode()
            )
        except InvalidToken as exc:
            raise ApiError(
                503, "CONFIG_ENCRYPTION_UNAVAILABLE", "Stored provider key cannot be decrypted"
            ) from exc
    elif data.get("clear_provider_api_key"):
        override["provider_api_key"] = None
    return settings.model_copy(update=override)


def public_config(session: Session, settings: Settings) -> dict:
    data = stored(session)
    active = effective(session, settings)
    image = image_effective(session, settings)
    provider = create_provider(active)
    return {
        **{key: getattr(image, key) for key in IMAGE_FIELDS},
        "image_provider_api_key_configured": bool(
            image.image_provider_api_key and image.image_provider_api_key.get_secret_value()
        ),
        "provider_name": provider.name,
        "provider_endpoint": active.provider_endpoint,
        "provider_model": active.provider_model,
        "provider_timeout_seconds": active.provider_timeout_seconds,
        "provider_api_key_configured": bool(data.get("encrypted_api_key"))
        or (
            not data.get("clear_provider_api_key")
            and bool(settings.provider_api_key and settings.provider_api_key.get_secret_value())
        ),
        "local_model_version": settings.local_model_version,
        "local_model_threads": settings.local_model_threads,
        "recognition_service": describe_provider(provider, active).model_dump(),
        "key_editable": bool(settings.system_config_encryption_key),
        "map_web_key": data.get("map_web_key", ""),
        "map_center_longitude": data.get("map_center_longitude", 100.235),
        "map_center_latitude": data.get("map_center_latitude", 26.875),
        "map_default_zoom": data.get("map_default_zoom", 12),
    }


def update(session: Session, settings: Settings, payload: SystemConfigUpdate) -> dict:
    data = dict(stored(session))
    if payload.image_provider_api_key and payload.clear_image_provider_api_key:
        raise ApiError(422, "INVALID_REQUEST", "Cannot set and clear the image key together")
    if payload.image_provider_api_key:
        data["encrypted_image_api_key"] = (
            cipher(settings).encrypt(payload.image_provider_api_key.encode()).decode()
        )
        data["clear_image_provider_api_key"] = False
    elif payload.clear_image_provider_api_key:
        data.pop("encrypted_image_api_key", None)
        data["clear_image_provider_api_key"] = True
    # Old admin clients must not reset the separately configured image service.
    for key in IMAGE_FIELDS:
        if key in payload.model_fields_set:
            data[key] = getattr(payload, key)
    if payload.provider_api_key and payload.clear_provider_api_key:
        raise ApiError(422, "INVALID_REQUEST", "Cannot set and clear the provider key together")
    if payload.provider_api_key:
        data["encrypted_api_key"] = (
            cipher(settings).encrypt(payload.provider_api_key.encode()).decode()
        )
        data["clear_provider_api_key"] = False
    elif payload.clear_provider_api_key:
        data.pop("encrypted_api_key", None)
        data["clear_provider_api_key"] = True
    for key in (
        "provider_name",
        "provider_endpoint",
        "provider_model",
        "provider_timeout_seconds",
        "map_web_key",
        "map_center_longitude",
        "map_center_latitude",
        "map_default_zoom",
    ):
        data[key] = getattr(payload, key)
    record = session.get(Setting, CONFIG_KEY)
    if record is None:
        session.add(Setting(key=CONFIG_KEY, value=data))
    else:
        record.value = data
    session.flush()
    return public_config(session, settings)


def active_provider(session: Session, settings: Settings):
    active = effective(session, settings)
    return create_provider(active), active


def image_effective(session: Session, settings: Settings) -> Settings:
    data = stored(session)
    override = {key: data[key] for key in IMAGE_FIELDS if key in data}
    if data.get("encrypted_image_api_key"):
        try:
            override["image_provider_api_key"] = SecretStr(
                cipher(settings).decrypt(data["encrypted_image_api_key"].encode()).decode()
            )
        except InvalidToken as exc:
            raise ApiError(503, "CONFIG_ENCRYPTION_UNAVAILABLE", "Image key unavailable") from exc
    elif data.get("clear_image_provider_api_key"):
        override["image_provider_api_key"] = None
    return settings.model_copy(update=override)
