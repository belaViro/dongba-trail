import asyncio
import hashlib
from datetime import UTC, datetime
from io import BytesIO

import pytest
from PIL import Image

from backend.app.config import Settings
from backend.app.local_glyph_provider import LocalGlyphProvider, _load_runtime, _model_class
from backend.app.provider_factory import create_provider
from backend.app.providers import ProviderUnavailable
from backend.app.schemas import Character


def character(character_id: str) -> Character:
    return Character(
        character_id=character_id,
        cn_name=character_id,
        culture_summary="Test fixture only.",
        source_ref="test:local-model",
        status="published",
        reviewed_by="test-reviewer",
        reviewed_at=datetime(2026, 10, 10, tzinfo=UTC),
    )


def artifact(tmp_path, labels=("0001", "0018", "0476")):
    torch = pytest.importorskip("torch")
    path = tmp_path / "inference.pt"
    model = _model_class(torch)(len(labels))
    torch.save(
        {
            "model": model.state_dict(),
            "labels": [
                {"class_id": value, "label": index, "name": value, "aliases": []}
                for index, value in enumerate(labels)
            ],
            "identity": {"fixture": True},
        },
        path,
    )
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def image_bytes():
    stream = BytesIO()
    Image.new("L", (128, 96), "white").save(stream, format="PNG")
    return stream.getvalue()


def test_factory_selects_local_provider_and_missing_artifact_is_not_ready(tmp_path):
    provider = create_provider(
        Settings(
            _env_file=None,
            provider_name="db1404-local",
            local_model_path=tmp_path / "missing.pt",
        )
    )
    assert provider.name == "db1404-local"
    assert provider.configured is False


def test_local_provider_verifies_artifact_and_only_returns_published_ids(tmp_path):
    path, digest = artifact(tmp_path)
    provider = LocalGlyphProvider(
        artifact_path=path,
        expected_sha256=digest,
        model_version="fixture-local-v1",
        threads=1,
    )
    result = asyncio.run(
        provider.recognize(
            image_bytes(),
            "image/png",
            (character("DB1404_0018"), character("DB1404_0476")),
        )
    )
    assert provider.configured is True
    assert result.model_version == "fixture-local-v1"
    assert {item.character_id for item in result.candidates} == {
        "DB1404_0018",
        "DB1404_0476",
    }
    assert all(0 <= item.score <= 1 for item in result.candidates)


def test_local_provider_rejects_wrong_artifact_digest(tmp_path):
    path, _ = artifact(tmp_path)
    provider = LocalGlyphProvider(
        artifact_path=path,
        expected_sha256="0" * 64,
        model_version="fixture-local-v1",
    )
    assert provider.configured is False
    with pytest.raises(ProviderUnavailable):
        asyncio.run(provider.recognize(image_bytes(), "image/png", (character("DB1404_0018"),)))


def test_matching_digest_but_invalid_model_is_unavailable(tmp_path):
    path = tmp_path / "invalid.pt"
    path.write_bytes(b"not a model; valid digest is insufficient")
    provider = LocalGlyphProvider(
        artifact_path=path,
        expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        model_version="fixture-invalid",
    )
    assert provider.configured is False


@pytest.mark.parametrize("error", [ImportError, OSError])
def test_missing_or_broken_cpu_dependency_is_unavailable(tmp_path, monkeypatch, error):
    import builtins

    original_import = builtins.__import__

    def missing_torch(name, *args, **kwargs):
        if name == "torch":
            raise error("synthetic dependency failure")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing_torch)
    path = tmp_path / "dependency.pt"
    path.write_bytes(b"fixture")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    provider = LocalGlyphProvider(
        artifact_path=path, expected_sha256=digest, model_version="fixture-missing-dependency"
    )
    assert provider.configured is False
    with pytest.raises(ProviderUnavailable):
        _load_runtime(path, digest, 2)


def test_ready_load_is_cached_and_modified_artifact_is_rejected(tmp_path):
    path, digest = artifact(tmp_path)
    provider = LocalGlyphProvider(
        artifact_path=path, expected_sha256=digest, model_version="fixture-cache", threads=1
    )
    assert provider.configured
    runtime = _load_runtime(path, digest, 1)
    assert provider.configured
    assert _load_runtime(path, digest, 1) is runtime
    path.write_bytes(b"corrupt after loading")
    assert provider.configured is False
