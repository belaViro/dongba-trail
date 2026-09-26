"""Runtime provider and public map configuration (OPS-03, GEO-01)."""

import ipaddress
from urllib.parse import urlsplit

from cryptography.fernet import Fernet, InvalidToken
from pydantic import BaseModel, Field, SecretStr, field_validator
from sqlalchemy.orm import Session

from backend.app.config import Settings
from backend.app.errors import ApiError
from backend.app.provider_factory import create_provider

from .business.models import Setting

CONFIG_KEY = "runtime_system_config"


class SystemConfigUpdate(BaseModel):
    provider_name: str = Field(max_length=40)
    provider_endpoint: str = Field(max_length=500)
    provider_model: str = Field(max_length=160)
    provider_timeout_seconds: float = Field(gt=0, le=60)
    provider_api_key: str = Field(default="", max_length=4096)
    clear_provider_api_key: bool = False
    map_web_key: str = Field(max_length=256)
    map_center_longitude: float = Field(default=100.235, ge=73, le=135)
    map_center_latitude: float = Field(default=26.875, ge=3, le=54)
    map_default_zoom: int = Field(default=12, ge=3, le=18)

    @field_validator("provider_name")
    @classmethod
    def valid_provider(cls, value: str) -> str:
        if value.strip().lower() not in {"unconfigured", "ark", "volcengine", "volcengine-ark"}:
            raise ValueError("Unsupported provider")
        return value.strip().lower()

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
    if data.get("encrypted_api_key"):
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
    return {
        "provider_name": active.provider_name,
        "provider_endpoint": active.provider_endpoint,
        "provider_model": active.provider_model,
        "provider_timeout_seconds": active.provider_timeout_seconds,
        "provider_api_key_configured": bool(
            active.provider_api_key and active.provider_api_key.get_secret_value()
        ),
        "key_editable": bool(settings.system_config_encryption_key),
        "map_web_key": data.get("map_web_key", ""),
        "map_center_longitude": data.get("map_center_longitude", 100.235),
        "map_center_latitude": data.get("map_center_latitude", 26.875),
        "map_default_zoom": data.get("map_default_zoom", 12),
    }


def update(session: Session, settings: Settings, payload: SystemConfigUpdate) -> dict:
    data = dict(stored(session))
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
