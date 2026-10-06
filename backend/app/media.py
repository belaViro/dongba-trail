"""Reviewed cultural media and user-requested poster generation."""

import json
import re
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

import httpx
import qrcode
from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import FileResponse, Response
from PIL import Image, ImageDraw, ImageFont, ImageOps
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from backend.app.business.auth import current_user
from backend.app.business.models import Claim, Entity, User
from backend.app.errors import ApiError
from backend.app.recognition import validate_image

ASSET_NAME = re.compile(r"^[a-f0-9]{32}\.png$")


def referenced_asset_names(settings, records) -> set[str]:
    names = set()
    prefix = "/api/v1/media/"
    for record in records:
        urls = [record.get("image_url", "")]
        urls.extend(variant.get("image_url", "") for variant in record.get("variants", []))
        for url in urls:
            relative = url.removeprefix(settings.public_base_url.rstrip("/"))
            name = relative.removeprefix(prefix)
            if relative.startswith(prefix) and ASSET_NAME.fullmatch(name):
                names.add(name)
    return names


class PosterInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    character_ids: list[str] = Field(min_length=1, max_length=3)
    template: Literal["mountain", "paper", "old-town", "minimal"] = "paper"
    caption: str = Field(default="在丽江，收藏时光里的美好。", max_length=50)

    @field_validator("caption")
    @classmethod
    def normalize_caption(cls, value: str) -> str:
        return " ".join(value.split())


def chinese_font(size: int):
    paths = (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
        # Alibaba Cloud Linux ships this CJK font instead of Debian's Noto paths.
        Path("/usr/share/fonts/google-droid/DroidSansFallback.ttf"),
    )
    for path in paths:
        if path.is_file():
            try:
                return ImageFont.truetype(str(path), size)
            except OSError:
                continue
    raise ApiError(503, "POSTER_FONT_UNAVAILABLE", "A Chinese font must be installed")


def save_asset(settings, image: Image.Image, owner: str, kind: str) -> str:
    directory = settings.media_directory
    directory.mkdir(parents=True, exist_ok=True)
    name = f"{uuid4().hex}.png"
    image.save(directory / name, format="PNG", optimize=True)
    (directory / f"{name}.json").write_text(
        json.dumps(
            {
                "owner": owner,
                "kind": kind,
                "created_at": datetime.now(UTC).isoformat(),
            }
        ),
        encoding="utf-8",
    )
    return name


def local_asset(settings, url: str) -> Path:
    prefix = "/api/v1/media/"
    if url.startswith(settings.public_base_url.rstrip("/") + prefix):
        url = url.removeprefix(settings.public_base_url.rstrip("/"))
    name = url.removeprefix(prefix)
    if not url.startswith(prefix) or not ASSET_NAME.fullmatch(name):
        raise ApiError(
            409, "CHARACTER_IMAGE_UNAVAILABLE", "Upload the approved character image first"
        )
    path = settings.media_directory / name
    if not path.is_file():
        raise ApiError(409, "CHARACTER_IMAGE_UNAVAILABLE", "Character image is unavailable")
    return path


def render_poster(
    settings,
    records: list[dict],
    template: str,
    code: bytes | None,
    background: Image.Image | None = None,
    caption: str = "在丽江，收藏时光里的美好。",
) -> Image.Image:
    # The endpoint always supplies AI artwork; optional background supports pure renderer tests.
    canvas = (
        ImageOps.fit(background, (900, 1400)).convert("RGB")
        if background is not None
        else Image.new("RGB", (900, 1400), "#f6efe3")
    )
    veil = Image.new("RGBA", canvas.size)
    overlay = ImageDraw.Draw(veil)
    for y in range(1020):
        alpha = 225 if y < 800 else max(0, int(225 * (1020 - y) / 220))
        overlay.line((24, y, 876, y), fill=(255, 250, 237, alpha))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), veil).convert("RGB")
    draw = ImageDraw.Draw(canvas)
    draw.text((450, 55), "东巴寻迹 · 丽江", fill="#785e49", font=chinese_font(25), anchor="mt")
    draw.text((450, 120), "我的东巴印记", fill="#432b1c", font=chinese_font(76), anchor="mt")
    draw.text(
        (450, 230), "一字一故事 · 一程一印记", fill="#785e49", font=chinese_font(27), anchor="mt"
    )
    draw.line((75, 295, 825, 295), fill="#b99b7c", width=1)
    width = 780 // len(records)
    for index, record in enumerate(records):
        with Image.open(local_asset(settings, record["image_url"])) as original:
            glyph = ImageOps.contain(original.convert("RGBA"), (min(width - 36, 250), 235))
        center = 60 + width * index + width // 2
        canvas.paste(glyph, (center - glyph.width // 2, 345 + (235 - glyph.height) // 2), glyph)
        text = record["cn_name"]
        font = chinese_font(42)
        while draw.textbbox((0, 0), text, font=font)[2] > width - 20 and font.size > 14:
            font = chinese_font(font.size - 2)
        draw.text((center, 610), text, fill="#432b1c", font=font, anchor="mt")
    draw.line((100, 705, 800, 705), fill="#b99b7c", width=1)
    font = chinese_font(31)
    lines, current = [], ""
    for char in caption:
        if char in "\r\n":
            if current:
                lines.append(current)
                current = ""
            continue
        if draw.textlength(current + char, font=font) > 710:
            lines.append(current)
            current = ""
        current += char
    if current:
        lines.append(current)
    for index, line in enumerate(lines[:4]):
        draw.text((450, 751 + index * 47), line, fill="#432b1c", font=font, anchor="mt")
    draw.rounded_rectangle((42, 1260, 550, 1364), radius=14, fill="#fff7e7")
    draw.text((62, 1272), "在丽江 · 收藏时光里的美好", fill="#6a3925", font=chinese_font(26))
    if code:
        with Image.open(BytesIO(code)) as original:
            stamp = ImageOps.contain(original.convert("RGB"), (155, 155))
        draw.rounded_rectangle((654, 1150, 843, 1350), radius=9, fill="white")
        canvas.paste(stamp, (670, 1165))
        draw.text((748, 1324), "一起寻迹丽江", fill="#432b1c", font=chinese_font(17), anchor="mt")
    return canvas


async def wechat_share_code(settings, scene: str) -> bytes | None:
    secret = settings.wechat_app_secret
    if not settings.wechat_app_id or not secret or not secret.get_secret_value():
        return None
    try:
        async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
            response = await client.get(
                "https://api.weixin.qq.com/cgi-bin/token",
                params={
                    "grant_type": "client_credential",
                    "appid": settings.wechat_app_id,
                    "secret": secret.get_secret_value(),
                },
            )
            response.raise_for_status()
            token = response.json().get("access_token")
            if not token:
                raise ValueError("No access token")
            response = await client.post(
                "https://api.weixin.qq.com/wxa/getwxacodeunlimit",
                params={"access_token": token},
                json={
                    "scene": scene,
                    "page": "pages/home/index",
                    "check_path": True,
                    "width": 280,
                    "env_version": "release",
                },
            )
            response.raise_for_status()
            if "image/" not in response.headers.get("content-type", ""):
                raise ValueError("No share code image")
            return response.content
    except (httpx.HTTPError, ValueError) as exc:
        raise ApiError(
            502, "WECHAT_SHARE_UNAVAILABLE", "WeChat share code could not be generated"
        ) from exc


def install_media(app, settings):
    router = APIRouter(prefix="/api/v1", tags=["Media and sharing"])

    @router.get("/me/coupons/{claim_id}/qr", response_class=Response)
    def coupon_qr(claim_id: str, request: Request, user: User = Depends(current_user)):
        with request.app.state.database.session() as session:
            claim = session.get(Claim, claim_id)
            if claim is None or claim.user_id != user.id:
                raise ApiError(404, "COUPON_NOT_FOUND", "Coupon was not found")
            code = claim.code
        output = BytesIO()
        qrcode.make(code, box_size=8, border=4).save(output, format="PNG")
        return Response(
            output.getvalue(), media_type="image/png", headers={"Cache-Control": "no-store"}
        )

    @router.post("/media")
    async def upload_media(
        file: Annotated[UploadFile, File()],
        user: User = Depends(current_user),
    ):
        if user.role not in {"admin", "operator", "merchant"}:
            raise ApiError(403, "FORBIDDEN", "Media upload requires publishing permission")
        try:
            content = await file.read(settings.max_image_bytes + 1)
        finally:
            await file.close()
        await run_in_threadpool(validate_image, content, settings)

        def save():
            with Image.open(BytesIO(content)) as image:
                clean = ImageOps.exif_transpose(image).convert("RGBA")
                clean.thumbnail((2400, 2400))
                return save_asset(settings, clean, user.id, "content")

        name = await run_in_threadpool(save)
        return {"url": f"/api/v1/media/{name}"}

    @router.get("/media/{name}")
    def media_file(name: str, request: Request):
        if not ASSET_NAME.fullmatch(name):
            raise ApiError(404, "MEDIA_NOT_FOUND", "Media not found")
        path = settings.media_directory / name
        metadata_path = settings.media_directory / f"{name}.json"
        if not path.is_file() or not metadata_path.is_file():
            raise ApiError(404, "MEDIA_NOT_FOUND", "Media not found")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        public = metadata["kind"] == "poster"
        if not public and metadata["kind"] != "sample":
            with request.app.state.database.session() as session:
                entities = session.scalars(select(Entity).where(Entity.status == "published")).all()
                public = name in referenced_asset_names(
                    settings, (entity.data for entity in entities)
                )
        if not public:
            user = current_user(request)
            if user.role not in {"admin", "operator"} and user.id != metadata["owner"]:
                raise ApiError(403, "FORBIDDEN", "This media has not been published")
        return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-store"})

    @router.post("/share/poster")
    async def poster(payload: PosterInput, request: Request, user: User = Depends(current_user)):
        from backend.app.poster_jobs import generate_poster

        return await generate_poster(request.app.state.database, settings, user.id, payload)

    app.include_router(router)
    from backend.app.poster_jobs import install_poster_jobs

    install_poster_jobs(app, settings)
