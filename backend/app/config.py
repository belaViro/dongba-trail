from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DONGBA_", env_file=PROJECT_ROOT / ".env", extra="ignore"
    )

    dictionary_path: Path = PROJECT_ROOT / "data" / "characters.json"
    max_image_bytes: int = Field(default=8 * 1024 * 1024, ge=1, le=20 * 1024 * 1024)
    max_image_pixels: int = Field(default=20_000_000, ge=1, le=40_000_000)
    provider_timeout_seconds: float = Field(default=15, gt=0, le=60)
    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "mysql+pymysql://dongba@127.0.0.1:3307/dongba?charset=utf8mb4"
    auto_create_schema: bool = True
    setup_enabled: bool = True
    setup_secret: SecretStr | None = None
    session_hours: int = Field(default=24, ge=1, le=168)
    wechat_app_id: str = ""
    wechat_app_secret: SecretStr | None = None
    public_base_url: str = "http://127.0.0.1:8010"
    media_directory: Path = PROJECT_ROOT / "runtime" / "media"
    provider_name: str = "unconfigured"
    provider_endpoint: str = ""
    provider_api_key: SecretStr | None = None
    provider_model: str = ""
    system_config_encryption_key: SecretStr | None = None
    request_limit_per_minute: int = Field(default=120, ge=1, le=10000)
    recognition_limit_per_minute: int = Field(default=10, ge=1, le=120)
    trusted_hosts: list[str] = ["localhost", "127.0.0.1", "testserver"]
    privacy_policy_published: bool = False
    privacy_contact: str = ""
    privacy_version: str = "2026-09-23.1"
    retention_days: int = Field(default=30, ge=1, le=365)
    quality_checks_enabled: bool = True
    quality_min_edge: int = Field(default=96, ge=16, le=1024)
    quality_min_edge_variance: float = Field(default=2.0, ge=0, le=100)

    @model_validator(mode="after")
    def production_configuration(self):
        if self.environment == "production":
            if not self.database_url.startswith("mysql+pymysql://"):
                raise ValueError("Production requires MySQL with the PyMySQL driver")
            if self.auto_create_schema:
                raise ValueError("Production schema must be managed with migrations")
            if self.setup_enabled and (
                not self.setup_secret or not self.setup_secret.get_secret_value()
            ):
                raise ValueError("Production account setup requires a setup secret")
            if not self.public_base_url.startswith("https://"):
                raise ValueError("Production public_base_url must use HTTPS")
        return self

    @field_validator("dictionary_path")
    @classmethod
    def resolve_dictionary_path(cls, value: Path) -> Path:
        return value if value.is_absolute() else PROJECT_ROOT / value

    @field_validator("media_directory")
    @classmethod
    def resolve_media_path(cls, value: Path) -> Path:
        return value if value.is_absolute() else PROJECT_ROOT / value
