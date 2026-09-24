"""The only integration point to replace when the model supplier is selected."""

from backend.app.config import Settings
from backend.app.providers import RecognitionProvider, UnconfiguredProvider


def create_provider(settings: Settings) -> RecognitionProvider:
    """Implement the supplier protocol here, then return a configured adapter.

    Available configuration: provider_endpoint, provider_api_key (SecretStr),
    provider_model, provider_timeout_seconds. Never expose these secrets to clients.

    The adapter must implement RecognitionProvider and return ProviderResult with
    canonical dictionary IDs. See docs/contracts/recognition.md. Merely filling
    the environment variables must not claim that an adapter is implemented.
    """
    return UnconfiguredProvider()
