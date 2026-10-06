"""Volcengine Ark vision adapter using its OpenAI-compatible chat endpoint."""

import base64
import json
import logging
import re

import httpx

from backend.app.providers import ProviderUnavailable
from backend.app.schemas import Character, ProviderResult

logger = logging.getLogger(__name__)
DEFAULT_ENDPOINT = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"


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
    def _catalog(characters: tuple[Character, ...]) -> str:
        return "\n".join(f"- {item.character_id}: {item.cn_name}" for item in characters)

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

    async def recognize(
        self, image: bytes, media_type: str, characters: tuple[Character, ...]
    ) -> ProviderResult:
        if not self.configured:
            raise ProviderUnavailable("Volcengine Ark provider is not configured")
        prompt = (
            "识别图片中的单个东巴字，并先抄录图片中实际看到的文字。只从下面的已审核候选中选择，不能创建新编号，"
            "不能编造文化解释。返回严格 JSON："
            '{"observed_text":"图片中读到的文字","keywords":[],"scene":"","candidates":[{"character_id":"候选编号","score":0.0}]}。'
            "最多返回5个候选；不确定时返回空 candidates。候选目录：\n" + self._catalog(characters)
        )
        payload = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 300,
            "thinking": {"type": "disabled"},
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": (
                                    "data:"
                                    + media_type
                                    + ";base64,"
                                    + base64.b64encode(image).decode()
                                )
                            },
                        },
                    ],
                }
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.endpoint, headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            parsed = self._parse_json(self._content_text(content))
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
