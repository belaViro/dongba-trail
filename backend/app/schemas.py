from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Character(StrictModel):
    character_id: str = Field(pattern=r"^[A-Za-z0-9_-]{2,64}$")
    cn_name: str = Field(min_length=1, max_length=100)
    culture_summary: str = Field(min_length=1, max_length=1000)
    source_ref: str = Field(min_length=1, max_length=1000)
    status: Literal["draft", "reviewed", "published", "disabled"]
    reviewed_by: str | None = Field(default=None, min_length=1, max_length=100)
    reviewed_at: datetime | None = None
    image_url: str = Field(default="", max_length=1000)
    variants: list[dict[str, str]] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def require_publication_review(self) -> Self:
        if self.status == "published":
            if not self.reviewed_by or self.reviewed_at is None:
                raise ValueError("Published characters require review metadata")
            if self.reviewed_at.utcoffset() is None:
                raise ValueError("Review timestamps must include a timezone")
        return self


class CharacterPublic(StrictModel):
    character_id: str
    cn_name: str
    culture_summary: str
    source_ref: str
    image_url: str = ""
    variants: list[dict[str, str]] = Field(default_factory=list)

    @classmethod
    def from_character(cls, character: Character) -> Self:
        return cls.model_validate(character.model_dump(include=set(cls.model_fields)))


class ProviderCandidate(StrictModel):
    character_id: str = Field(min_length=1, max_length=64)
    score: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)


class ProviderResult(StrictModel):
    model_version: str = Field(min_length=1, max_length=100)
    candidates: list[ProviderCandidate] = Field(max_length=5)
    observed_text: str = Field(default="", max_length=2000)
    keywords: list[str] = Field(default_factory=list, max_length=50)
    scene: str = Field(default="", max_length=100)


class RecognitionCandidate(CharacterPublic):
    provider_score: float | None = None


class RecognitionResponse(StrictModel):
    request_id: str
    status: Literal["NEED_USER_CONFIRM", "UNKNOWN"]
    provider: str
    model_version: str
    latency_ms: int
    candidates: list[RecognitionCandidate]
    observed_text: str = ""
    rag_hits: list[dict] = Field(default_factory=list)
    rag_applied: bool = False


class ErrorResponse(StrictModel):
    request_id: str
    code: str
    message: str


class HealthResponse(StrictModel):
    status: Literal["ok"] = "ok"
    version: str


class ReadinessResponse(StrictModel):
    status: Literal["ready", "not_ready"]
    provider_configured: bool
    published_characters: int
    reasons: list[str]
