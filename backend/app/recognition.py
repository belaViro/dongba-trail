import asyncio
import logging
import warnings
from io import BytesIO
from time import perf_counter

from PIL import Image, ImageFilter, ImageStat, UnidentifiedImageError
from pydantic import ValidationError

from backend.app.config import Settings
from backend.app.dictionary import CharacterDictionary
from backend.app.errors import ApiError
from backend.app.providers import ProviderUnavailable, RecognitionProvider
from backend.app.schemas import ProviderResult, RecognitionCandidate, RecognitionResponse

logger = logging.getLogger(__name__)
MEDIA_TYPES = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


def assess_image_quality(image: bytes, settings: Settings) -> None:
    with Image.open(BytesIO(image)) as decoded:
        if min(decoded.size) < settings.quality_min_edge:
            raise ApiError(400, "IMAGE_TOO_SMALL", "The image is too small; move closer and retake")
        grayscale = decoded.convert("L")
        grayscale.thumbnail((512, 512))
        statistics = ImageStat.Stat(grayscale)
        if statistics.mean[0] < 12:
            raise ApiError(400, "IMAGE_TOO_DARK", "The image is too dark; improve the lighting")
        if statistics.mean[0] > 248 and statistics.stddev[0] < 10:
            raise ApiError(400, "IMAGE_OVEREXPOSED", "The image is overexposed; retake the photo")
        edges = grayscale.filter(ImageFilter.FIND_EDGES)
        inner = edges.crop((2, 2, edges.width - 2, edges.height - 2))
        if ImageStat.Stat(inner).var[0] < settings.quality_min_edge_variance:
            raise ApiError(400, "IMAGE_BLURRY", "The image has too little detail; retake the photo")


def validate_image(image: bytes, settings: Settings) -> str:
    if not image:
        raise ApiError(400, "INVALID_IMAGE", "Image is empty")
    if len(image) > settings.max_image_bytes:
        raise ApiError(413, "IMAGE_TOO_LARGE", "Image exceeds the upload size limit")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(image)) as decoded:
                media_type = MEDIA_TYPES.get(decoded.format or "")
                if media_type is None:
                    raise ApiError(415, "UNSUPPORTED_IMAGE", "Use JPEG, PNG, or WebP")
                if decoded.width * decoded.height > settings.max_image_pixels:
                    raise ApiError(413, "IMAGE_TOO_LARGE", "Image exceeds the pixel limit")
                if getattr(decoded, "is_animated", False):
                    raise ApiError(415, "UNSUPPORTED_IMAGE", "Animated images are not supported")
                decoded.verify()
            with Image.open(BytesIO(image)) as decoded:
                decoded.load()
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ApiError(413, "IMAGE_TOO_LARGE", "Image exceeds the pixel limit") from exc
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise ApiError(400, "INVALID_IMAGE", "Image cannot be decoded") from exc
    return media_type


async def recognize(
    *,
    image: bytes,
    media_type: str,
    request_id: str,
    provider: RecognitionProvider,
    dictionary: CharacterDictionary,
    settings: Settings,
) -> RecognitionResponse:
    if not provider.configured:
        raise ApiError(503, "PROVIDER_NOT_CONFIGURED", "Recognition provider is not configured")
    characters = dictionary.published()
    if not characters:
        raise ApiError(503, "DICTIONARY_NOT_READY", "No published dictionary entries are available")

    started_at = perf_counter()
    try:
        async with asyncio.timeout(settings.provider_timeout_seconds):
            result = ProviderResult.model_validate(
                await provider.recognize(image, media_type, characters)
            )
    except TimeoutError as exc:
        raise ApiError(504, "PROVIDER_TIMEOUT", "Recognition provider timed out") from exc
    except ProviderUnavailable as exc:
        raise ApiError(503, "PROVIDER_UNAVAILABLE", "Recognition provider is unavailable") from exc
    except ValidationError as exc:
        raise ApiError(502, "INVALID_PROVIDER_RESPONSE", "Recognition response is invalid") from exc
    except Exception as exc:
        # Exception messages may contain credentials, URLs, or request data.
        logger.error("provider_failure request_id=%s error_type=%s", request_id, type(exc).__name__)
        raise ApiError(502, "PROVIDER_ERROR", "Recognition provider failed") from exc

    candidates: list[RecognitionCandidate] = []
    matched_ids: set[str] = set()
    for candidate in result.candidates:
        character = dictionary.get(candidate.character_id)
        if character is None or character.character_id in matched_ids:
            continue
        matched_ids.add(character.character_id)
        candidates.append(
            RecognitionCandidate(
                character_id=character.character_id,
                cn_name=character.cn_name,
                culture_summary=character.culture_summary,
                source_ref=character.source_ref,
                image_url=character.image_url,
                variants=character.variants,
                provider_score=candidate.score,
            )
        )

    return RecognitionResponse(
        request_id=request_id,
        status="NEED_USER_CONFIRM" if candidates else "UNKNOWN",
        provider=provider.name,
        model_version=result.model_version,
        latency_ms=round((perf_counter() - started_at) * 1000),
        candidates=candidates,
    )
