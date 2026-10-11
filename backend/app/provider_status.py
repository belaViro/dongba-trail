"""Safe, shared runtime identity for operations and failure records (OPS-03, AI-03)."""

from typing import Literal

from pydantic import BaseModel

from backend.app.config import Settings
from backend.app.providers import RecognitionProvider


class RecognitionServiceStatus(BaseModel):
    name: str
    model: str
    kind: Literal["local", "external", "unconfigured"]
    configured: bool
    status: Literal["ready", "configured", "unavailable", "unconfigured"]
    status_message: str
    endpoint_configured: bool | None = None
    timeout_seconds: float | None = None
    cpu_threads: int | None = None
    automatic_fallback: Literal[False] = False
    calibrated_confidence: Literal[False] = False


class ProviderStatus(RecognitionServiceStatus):
    recent_requests: int
    recent_errors: int
    p95_latency_ms: int | None
    statistics_scope: Literal["current_provider_and_model"] = "current_provider_and_model"
    statistics_limit: Literal[1000] = 1000


def provider_model(provider: RecognitionProvider, settings: Settings) -> str:
    if provider.name == "unconfigured":
        return ""
    if provider.name == "db1404-local":
        return provider.model_version
    return getattr(provider, "model", settings.provider_model)


def describe_provider(
    provider: RecognitionProvider, settings: Settings
) -> RecognitionServiceStatus:
    configured = provider.configured
    status = RecognitionServiceStatus(
        name=provider.name,
        model=provider_model(provider, settings),
        kind="unconfigured",
        configured=configured,
        status="unconfigured",
        status_message="识别服务未启用；不会自动切换到其他提供方。",
    )
    if provider.name == "db1404-local":
        status.kind = "local"
        status.cpu_threads = provider.threads
        status.timeout_seconds = settings.provider_timeout_seconds
        status.status = "ready" if configured else "unavailable"
        status.status_message = (
            "本地模型摘要校验和运行时加载已通过；不代表识别准确率。"
            if configured
            else "本地模型不可用：请检查模型文件、摘要及 CPU 推理依赖；不会自动调用大模型。"
        )
    elif provider.name != "unconfigured":
        status.kind = "external"
        status.status = "configured" if configured else "unavailable"
        status.endpoint_configured = bool(getattr(provider, "endpoint", settings.provider_endpoint))
        status.timeout_seconds = settings.provider_timeout_seconds
        status.status_message = (
            "外部识别服务配置完整；未进行连接探测或付费调用。"
            if configured
            else "外部识别服务配置不完整，请检查接口地址、模型 ID 和 API Key。"
        )
    return status
