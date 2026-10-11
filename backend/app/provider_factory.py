"""The only integration point to replace when the model supplier is selected."""

from backend.app.config import Settings
from backend.app.providers import RecognitionProvider, UnconfiguredProvider
from backend.app.volcengine_provider import DEFAULT_ENDPOINT, VolcengineArkProvider


def create_provider(settings: Settings) -> RecognitionProvider:
    """Implement the supplier protocol here, then return a configured adapter.

    Available configuration: provider_endpoint, provider_api_key (SecretStr),
    provider_model, provider_timeout_seconds. Never expose these secrets to clients.

    The adapter returns ProviderResult candidates using canonical dictionary IDs.
    See docs/contracts/recognition.md. Server defaults come from environment;
    encrypted runtime overrides are stored separately. Secrets are never exposed.
    """
    provider_name = settings.provider_name.casefold().strip()
    if provider_name in {"local", "db1404-local"}:
        from backend.app.local_glyph_provider import LocalGlyphProvider

        return LocalGlyphProvider(
            artifact_path=settings.local_model_path,
            expected_sha256=settings.local_model_sha256,
            model_version=settings.local_model_version,
            threads=settings.local_model_threads,
        )
    if provider_name in {"ark", "volcengine", "volcengine-ark"}:
        return VolcengineArkProvider(
            endpoint=settings.provider_endpoint or DEFAULT_ENDPOINT,
            api_key=(
                settings.provider_api_key.get_secret_value() if settings.provider_api_key else ""
            ),
            model=settings.provider_model,
            timeout=settings.provider_timeout_seconds,
        )
    return UnconfiguredProvider()
