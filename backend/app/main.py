import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from time import perf_counter
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException
from starlette.middleware.base import RequestResponseEndpoint
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response
from starlette.status import HTTP_503_SERVICE_UNAVAILABLE

from backend.app.config import Settings
from backend.app.dictionary import CharacterDictionary
from backend.app.errors import ApiError
from backend.app.guards import RequestGuards
from backend.app.provider_factory import create_provider
from backend.app.providers import RecognitionProvider
from backend.app.recognition import assess_image_quality, recognize, validate_image
from backend.app.schemas import (
    CharacterPublic,
    ErrorResponse,
    HealthResponse,
    ReadinessResponse,
    RecognitionResponse,
)

VERSION = "0.9.0"
logger = logging.getLogger(__name__)


def create_app(
    *,
    settings: Settings | None = None,
    provider: RecognitionProvider | None = None,
    dictionary: CharacterDictionary | None = None,
    business_enabled: bool = True,
) -> FastAPI:
    configuration = settings or Settings()
    recognition_provider = provider if provider is not None else create_provider(configuration)
    character_dictionary = dictionary if dictionary is not None else CharacterDictionary([])

    @asynccontextmanager
    async def lifespan(app):
        maintenance = None
        if business_enabled:
            from backend.app.maintenance import retention_loop

            maintenance = asyncio.create_task(retention_loop(app.state.database, configuration))
        try:
            yield
        finally:
            if maintenance is not None:
                maintenance.cancel()
                with suppress(asyncio.CancelledError):
                    await maintenance
                await run_in_threadpool(app.state.database.engine.dispose)

    application = FastAPI(title="Dongba Lijiang API", version=VERSION, lifespan=lifespan)
    application.state.recognition_provider = recognition_provider
    application.state.settings = configuration
    if business_enabled:
        from backend.app.business import install_business
        from backend.app.media import install_media

        install_business(application, configuration)
        install_media(application, configuration)

    def active_dictionary() -> CharacterDictionary:
        if not business_enabled or dictionary is not None:
            return character_dictionary
        from backend.app.schemas import Character

        return CharacterDictionary(
            [
                Character.model_validate(
                    {key: value for key, value in record.items() if key in Character.model_fields}
                )
                for record in application.state.database.published_characters()
            ]
        )

    def current_provider():
        if not business_enabled or provider is not None:
            return recognition_provider, configuration
        from backend.app.system_config import active_provider

        with application.state.database.session() as session:
            return active_provider(session, configuration)

    @application.middleware("http")
    async def request_identifier(request: Request, call_next: RequestResponseEndpoint) -> Response:
        request.state.request_id = getattr(request.state, "request_id", str(uuid4()))
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    def error_response(request: Request, status: int, code: str, message: str) -> JSONResponse:
        return JSONResponse(
            status_code=status,
            content=ErrorResponse(
                request_id=request.state.request_id, code=code, message=message
            ).model_dump(),
        )

    @application.exception_handler(ApiError)
    async def application_error(request: Request, exc: ApiError) -> JSONResponse:
        return error_response(request, exc.status_code, exc.code, exc.message)

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return error_response(request, 422, "INVALID_REQUEST", "Request fields are invalid")

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        return error_response(
            request, exc.status_code, "HTTP_ERROR", "Request could not be handled"
        )

    @application.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "request_failure request_id=%s error_type=%s",
            request.state.request_id,
            type(exc).__name__,
        )
        response = error_response(request, 500, "INTERNAL_ERROR", "Request could not be completed")
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @application.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(version=VERSION)

    @application.get(
        "/ready",
        response_model=ReadinessResponse,
        responses={503: {"model": ReadinessResponse}},
    )
    async def ready(response: Response) -> ReadinessResponse:
        reasons = []
        try:
            provider_now, _ = await run_in_threadpool(current_provider)
            if not provider_now.configured:
                reasons.append("PROVIDER_NOT_CONFIGURED")
        except ApiError:
            provider_now = recognition_provider
            reasons.append("PROVIDER_CONFIG_UNAVAILABLE")
        from sqlalchemy.exc import SQLAlchemyError

        try:
            count = len((await run_in_threadpool(active_dictionary)).published())
        except SQLAlchemyError:
            count = 0
            reasons.append("DATABASE_UNAVAILABLE")
        if not count:
            reasons.append("DICTIONARY_NOT_READY")
        if reasons:
            response.status_code = HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(
            status="not_ready" if reasons else "ready",
            provider_configured=provider_now.configured
            and "PROVIDER_CONFIG_UNAVAILABLE" not in reasons,
            published_characters=count,
            reasons=reasons,
        )

    async def character_detail(character_id: str) -> CharacterPublic:
        character = character_dictionary.get(character_id)
        if character is None:
            raise ApiError(404, "CHARACTER_NOT_FOUND", "Published character was not found")
        return CharacterPublic.from_character(character)

    if not business_enabled:
        application.add_api_route(
            "/api/v1/characters/{character_id}",
            character_detail,
            response_model=CharacterPublic,
            responses={404: {"model": ErrorResponse}},
        )

    @application.get("/api/v1/privacy", tags=["Privacy"])
    async def privacy_policy():
        try:
            provider_now, _ = await run_in_threadpool(current_provider)
        except ApiError:
            provider_now = recognition_provider
        return {
            "published": configuration.privacy_policy_published
            and bool(configuration.privacy_contact),
            "version": configuration.privacy_version,
            "provider_name": provider_now.name,
            "retention_days": configuration.retention_days,
            "sample_retention_days": configuration.retention_days,
            "contact": configuration.privacy_contact,
            "content": (
                "登录需要微信授权并保存账户标识。识别图片用于本次识别，不自动用于模型训练。"
                "仅在您单独选择保留图片用于人工复核后，才保存去除照片附加信息的图片样本。"
                "不同意保留不影响识别；同意时，识别失败的合法图片也可能留作复核。"
                "识别结果和纠错记录用于历史查询与服务质量复核，可在个人中心删除。"
                "您可单独删除本人图片样本；清空识别历史也会删除关联样本。"
                "位置仅在您授权后用于附近推荐、导航和任务打卡。优惠券、核销和任务进度用于提供相应服务。"
                "分享海报仅包含您选择的已收藏或已识别文字。模型服务启用前，将补充具体服务商与图片处理说明。"
                f"识别、纠错、游客图片样本、访问事件及分享海报保留{configuration.retention_days}天，"
                "到期后由每小时清理任务删除。收藏、任务进度和券交易记录用于持续提供服务，"
                "如需删除账户相关信息，请联系公布的运营联系方式。"
            ),
        }

    if business_enabled:
        from fastapi import Depends
        from sqlalchemy import select

        from backend.app.business.auth import current_user, require_operations
        from backend.app.business.content import audit
        from backend.app.business.models import RecognitionRecord
        from backend.app.system_config import SystemConfigUpdate, public_config, stored, update

        def require_admin(user=Depends(current_user)):
            if user.role != "admin":
                raise ApiError(403, "FORBIDDEN", "Administrator permission is required")
            return user

        @application.get("/api/v1/public/map-config", tags=["Map"])
        def map_config(response: Response):
            response.headers["Cache-Control"] = "no-store"
            with application.state.database.session() as session:
                data = stored(session)
                return {
                    "web_key": data.get("map_web_key", ""),
                    "center_longitude": data.get("map_center_longitude", 100.235),
                    "center_latitude": data.get("map_center_latitude", 26.875),
                    "default_zoom": data.get("map_default_zoom", 12),
                }

        @application.get("/api/v1/admin/system-config", tags=["System configuration"])
        def get_system_config(user=Depends(require_admin)):
            with application.state.database.session() as session:
                return public_config(session, configuration)

        @application.put("/api/v1/admin/system-config", tags=["System configuration"])
        def save_system_config(payload: SystemConfigUpdate, user=Depends(require_admin)):
            with application.state.database.write() as session:
                result = update(session, configuration, payload)
                audit(
                    session,
                    user,
                    "update",
                    "system_config",
                    "runtime",
                    {
                        "fields": [
                            "provider_name",
                            "provider_endpoint",
                            "provider_model",
                            "provider_timeout_seconds",
                            "map_web_key",
                            "map_center_longitude",
                            "map_center_latitude",
                            "map_default_zoom",
                        ],
                        "provider_key_action": "replaced"
                        if payload.provider_api_key
                        else "cleared"
                        if payload.clear_provider_api_key
                        else "unchanged",
                    },
                )
                return result

        @application.get("/api/v1/admin/provider", tags=["Model operations"])
        def provider_status(user=Depends(require_operations)):
            provider_now, active_settings = current_provider()
            with application.state.database.session() as session:
                rows = session.scalars(
                    select(RecognitionRecord)
                    .order_by(RecognitionRecord.created_at.desc())
                    .limit(1000)
                ).all()
                latencies = sorted(row.latency_ms for row in rows if not row.error_code)
            return {
                "configured": provider_now.configured,
                "name": provider_now.name,
                "model": active_settings.provider_model,
                "endpoint_configured": bool(active_settings.provider_endpoint),
                "timeout_seconds": active_settings.provider_timeout_seconds,
                "recent_requests": len(rows),
                "recent_errors": sum(bool(row.error_code) for row in rows),
                "p95_latency_ms": latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))]
                if latencies
                else None,
                "calibrated_confidence": False,
            }

    @application.post(
        "/api/v1/recognize",
        response_model=RecognitionResponse,
        responses={code: {"model": ErrorResponse} for code in (400, 413, 415, 422, 502, 503, 504)},
    )
    async def recognize_image(
        request: Request,
        image: Annotated[UploadFile, File()],
        scene: Annotated[Literal["camera", "album"], Form()] = "camera",
        sample_consent: Annotated[bool, Form()] = False,
        sample_scene: Annotated[str, Form(max_length=100)] = "other",
    ) -> RecognitionResponse:
        user = None
        if business_enabled:
            from backend.app.business.auth import current_user

            user = await run_in_threadpool(current_user, request)
        try:
            content = await image.read(configuration.max_image_bytes + 1)
        finally:
            await image.close()
        started_at = perf_counter()
        media_type = None
        provider_now, active_settings = await run_in_threadpool(current_provider)

        async def retain_sample(recognition_id: str):
            if sample_consent and user is not None and media_type is not None:
                from backend.app.business.samples import store_recognition_sample

                await run_in_threadpool(
                    store_recognition_sample,
                    application.state.database,
                    configuration,
                    recognition_id=recognition_id,
                    user_id=user.id,
                    content=content,
                    scene=sample_scene,
                    consent_version=configuration.privacy_version,
                )

        try:
            media_type = await run_in_threadpool(validate_image, content, configuration)
            if business_enabled and configuration.quality_checks_enabled:
                await run_in_threadpool(assess_image_quality, content, configuration)
            records = await run_in_threadpool(active_dictionary)
            result = await recognize(
                image=content,
                media_type=media_type,
                request_id=request.state.request_id,
                provider=provider_now,
                dictionary=records,
                settings=active_settings,
            )
        except ApiError as exc:
            if user is not None:
                await run_in_threadpool(
                    application.state.database.record_recognition,
                    request_id=request.state.request_id,
                    user_id=user.id,
                    status="FAILED",
                    provider=provider_now.name,
                    model=active_settings.provider_model,
                    candidates=[],
                    latency_ms=round((perf_counter() - started_at) * 1000),
                    scene=scene,
                    error_code=exc.code,
                )
                await retain_sample(request.state.request_id)
            raise
        if user is not None:
            await run_in_threadpool(
                application.state.database.record_recognition,
                request_id=result.request_id,
                user_id=user.id,
                status=result.status,
                provider=result.provider,
                model=result.model_version,
                candidates=[candidate.model_dump() for candidate in result.candidates],
                latency_ms=result.latency_ms,
                scene=scene,
            )
            await retain_sample(result.request_id)
        return result

    application.add_middleware(TrustedHostMiddleware, allowed_hosts=configuration.trusted_hosts)
    application.add_middleware(RequestGuards, settings=configuration)
    return application
