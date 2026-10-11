"""Volcengine Ark vision adapter using its [OI]-compatible chat endpoint.

AI-01 / D-066: Dongba glyphs are visually distinct but share no relation to
their Chinese glosses, so the model must be shown reviewed reference glyph
images instead of a text-only catalog of names.
"""

import base64
import json
import logging
import re

import httpx

from backend.app.glyph_refs import GlyphReference, build_reference_sheets
from backend.app.providers import ProviderUnavailable
from backend.app.schemas import Character, ProviderResult

logger = logging.getLogger(__name__)
DEFAULT_ENDPOINT = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"


def catalog_text(characters: tuple[Character, ...]) -> str:
    return "\n".join(f"- {item.character_id}: {item.cn_name}" for item in characters)


def reference_prompt(references: tuple[GlyphReference, ...]) -> str:
    return (
        "下面每张参考对照图由多个方格组成，每格顶部是已审核参考字形的编号，下面是对应字形。"
        "请按方格编号仔细比较这些参考字形的笔画结构。方格顶部编号不是字形笔画。\n"
        "然后识别最后那张待识别照片中央由四角取景框圈住的单个东巴文字。"
        "只抄录实际看到的东巴字形笔画，忽略框外环境、手指、纸张边缘、阴影、装饰和其他文字；"
        "框内若有多个字形，只取中央最完整的一个。"
        "不要把字形联想成动物或物体，也不要描述画面内容；"
        "若框内没有可辨认的东巴文字，必须返回空 candidates，不要猜测。"
        "只从上面给出的参考字形编号中选择，不能创建新编号，不能编造文化解释。返回严格 JSON："
        '{"observed_text":"框内东巴字的笔画或读法","keywords":[],"scene":"",'
        '"candidates":[{"character_id":"参考字形编号","score":0.0}]}。'
        "最多返回5个候选，按可能性从高到低排列；不确定时返回空 candidates。"
    )


def catalog_prompt(characters: tuple[Character, ...]) -> str:
    return (
        "识别图片中央由四角取景框圈住的单个东巴文字。只抄录实际看到的东巴字形笔画，"
        "忽略框外环境、手指、纸张边缘、阴影、装饰和其他文字；框内若有多个字形，只取中央最完整的一个。"
        "不要把字形联想成动物或物体，也不要描述画面内容；"
        "若框内没有可辨认的东巴文字，必须返回空 candidates，不要猜测。"
        "只从下面的已审核候选中选择，不能创建新编号，不能编造文化解释。返回严格 JSON："
        '{"observed_text":"框内东巴字的笔画或读法","keywords":[],"scene":"",'
        '"candidates":[{"character_id":"候选编号","score":0.0}]}。'
        "最多返回5个候选；不确定时返回空 candidates。候选目录：\n" + catalog_text(characters)
    )


def image_part(image: bytes, media_type: str) -> dict:
    return {
        "type": "image_url",
        "image_url": {"url": "data:" + media_type + ";base64," + base64.b64encode(image).decode()},
    }


def upstream_error_code(response: httpx.Response) -> str:
    """Return only the upstream error code, never the message or credentials."""
    try:
        body = response.json()
    except ValueError:
        return "unparsable"
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict) and isinstance(error.get("code"), str):
            return error["code"][:64]
    return "unknown"


class VolcengineArkProvider:
    name = "volcengine-ark"

    def __init__(self, *, endpoint: str, api_key: str, model: str, timeout: float):
        self.endpoint = endpoint.rstrip("/") or DEFAULT_ENDPOINT
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.model and self.endpoint)

    @staticmethod
    def _content_text(content) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(item.get("text", "") for item in content if isinstance(item, dict))
        return ""

    @staticmethod
    def _parse_json(text: str) -> dict:
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S | re.I)
        candidate = fenced.group(1) if fenced else text.strip()
        start, end = candidate.find("{"), candidate.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("Ark response does not contain a JSON object")
        value = json.loads(candidate[start : end + 1])
        if not isinstance(value, dict):
            raise ValueError("Ark response JSON is not an object")
        return value

    @staticmethod
    def _message_content(prompt, image, media_type, references=()) -> list[dict]:
        content: list[dict] = [{"type": "text", "text": prompt}]
        for index, (group, sheet) in enumerate(build_reference_sheets(references), start=1):
            content.append(
                {
                    "type": "text",
                    "text": f"参考对照图{index}：\n"
                    + "\n".join(
                        f"参考字形 {reference.character_id}（{reference.cn_name}）"
                        for reference in group
                    ),
                }
            )
            content.append(image_part(sheet, "image/png"))
        content.append({"type": "text", "text": "以下是待识别照片（不是参考对照图）："})
        content.append(image_part(image, media_type))
        return content

    @staticmethod
    def _usage_counts(body: dict) -> tuple[int | None, int | None, int | None]:
        usage = body.get("usage")
        if not isinstance(usage, dict):
            return None, None, None

        def count(name: str) -> int | None:
            value = usage.get(name)
            return (
                value
                if isinstance(value, int) and not isinstance(value, bool) and value >= 0
                else None
            )

        return count("prompt_tokens"), count("completion_tokens"), count("total_tokens")

    async def recognize(
        self,
        image: bytes,
        media_type: str,
        characters: tuple[Character, ...],
        references: tuple[GlyphReference, ...] = (),
    ) -> ProviderResult:
        if not self.configured:
            raise ProviderUnavailable("Volcengine Ark provider is not configured")
        if references:
            content = self._message_content(
                reference_prompt(references), image, media_type, references
            )
        else:
            content = self._message_content(catalog_prompt(characters), image, media_type)
        payload = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 400,
            "thinking": {"type": "disabled"},
            "messages": [{"role": "user", "content": content}],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.endpoint, headers=headers, json=payload)
            if response.status_code >= 400:
                # Billing/quota problems must be diagnosable without exposing
                # upstream messages. An overdue account returns 403.
                logger.warning(
                    "volcengine_provider_http_error status=%s code=%s",
                    response.status_code,
                    upstream_error_code(response),
                )
            response.raise_for_status()
            body = response.json()
            prompt_tokens, completion_tokens, total_tokens = self._usage_counts(body)
            if total_tokens is not None:
                logger.info(
                    "volcengine_provider_usage model=%s reference_count=%s image_count=%s "
                    "prompt_tokens=%s completion_tokens=%s total_tokens=%s",
                    str(body.get("model") or self.model),
                    len(references),
                    (len(references) + 19) // 20 + 1 if references else 1,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                )
            message = body["choices"][0]["message"]["content"]
            parsed = self._parse_json(self._content_text(message))
            return ProviderResult.model_validate(
                {
                    "model_version": str(body.get("model") or self.model),
                    "candidates": parsed.get("candidates", []),
                    "observed_text": parsed.get("observed_text", ""),
                    "keywords": parsed.get("keywords", []),
                    "scene": parsed.get("scene", ""),
                }
            )
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            logger.warning("volcengine_provider_failure error_type=%s", type(exc).__name__)
            raise ProviderUnavailable("Volcengine Ark request failed") from exc
