"""AI-01/03, FEEDBACK-01, OPS-03: reviewed memory, not recognition accuracy."""

import asyncio
import os

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import inspect
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

from backend.app.business.models import Feedback, RecognitionRecord
from backend.app.config import Settings
from backend.app.dictionary import CharacterDictionary
from backend.app.main import create_app
from backend.app.rag import _case_data, apply_hits, retrieve, serialize_case, text_terms
from backend.app.rag_database import RagDatabase
from backend.app.rag_models import RagBase, RagCase
from backend.app.recognition import recognize
from backend.app.schemas import ProviderResult
from backend.tests.test_business_api import ROOT, context  # noqa: F401
from backend.tests.test_data_foundation import upload
from backend.tests.test_recognition import FixtureProvider, fixture_character, image_bytes

PREFIX = "/api/v1/admin/rag"


@pytest.fixture
def rag(context, tmp_path):  # noqa: F811
    ctx = context
    if ctx.app.state.database.engine.dialect.name == "mysql":
        url = os.getenv("DONGBA_TEST_RAG_DATABASE_URL") or dotenv_values(ROOT / ".env").get(
            "DONGBA_TEST_RAG_DATABASE_URL"
        )
        assert url and make_url(url).database == "dongba_rag_test", "Dedicated RAG test DB required"
    else:
        url = f"sqlite:///{(tmp_path / 'rag.sqlite').as_posix()}"
    database = RagDatabase(url)
    # This fixture only ever deletes its dedicated test schema's single RAG table.
    RagBase.metadata.drop_all(database.engine)
    database.create_schema()
    ctx.app.state.rag_database = database
    yield ctx
    database.dispose()


def post(ctx, path, data=None, expected=200):
    response = ctx.client.post(PREFIX + path, headers=ctx.admin, json=data)
    assert response.status_code == expected, response.text
    return response.json()


def case(ctx, character=None, **extra):
    character = character or ctx.character()
    # Legacy manual rows are fixture data, not an available production intake.
    data = _case_data(
        {
            "text": "屋顶与房屋",
            "answer": "合成纠错答案",
            "character_id": character["id"],
            "scene": "",
            "image_uri": "",
            "sample_id": None,
            **extra,
        },
    )
    with ctx.app.state.rag_database.write() as session:
        row = RagCase(
            **data, source_type="manual", status="pending", created_by=ctx.admin_user["id"]
        )
        session.add(row)
        session.flush()
        return serialize_case(row)


def test_case_review_search_edit_deprecate_and_persistence(rag):
    ctx = rag
    row = case(ctx)
    path = f"/cases/{row['id']}"
    assert row["original_text"] == "屋顶与房屋" and row["status"] == "pending"
    assert post(ctx, "/search", {"text": "房屋"})["items"] == []
    row = post(ctx, path + "/review", {"status": "approved", "review_note": "合成测试"})
    assert row["status"] == "indexed" and row["reviewed_by"]
    hit = post(ctx, "/search", {"text": "房屋", "limit": 5})["items"][0]
    assert hit["id"] == row["id"] and hit["score"] > 0
    assert hit["retrieval_count"] == 1
    stats = ctx.client.get(PREFIX + "/stats", headers=ctx.admin).json()
    assert stats["total"] == stats["indexed"] == 1
    listing = ctx.client.get(PREFIX + "/cases?q=房屋&status=indexed", headers=ctx.admin).json()
    assert listing["total"] == 1
    other = RagDatabase(ctx.app.state.rag_database.engine.url.render_as_string(hide_password=False))
    try:
        assert retrieve(other, "房屋")[0]["id"] == row["id"]
    finally:
        other.dispose()
    changed = ctx.client.patch(PREFIX + path, headers=ctx.admin, json={"answer": "新的纠正"})
    assert changed.status_code == 200, changed.text
    assert changed.json()["status"] == "pending" and changed.json()["reviewed_by"] is None
    assert post(ctx, "/search", {"text": "房屋"})["total"] == 0
    post(ctx, path + "/review", {"status": "rejected"}, expected=422)
    post(ctx, path + "/review", {"status": "rejected", "review_note": "需核实"})
    assert post(ctx, path + "/reindex")["status"] == "rejected"
    post(ctx, path + "/review", {"status": "approved"})
    post(ctx, path + "/deprecate", {"reason": "不再适用"})
    assert post(ctx, "/rebuild")["indexed"] == 0
    assert post(ctx, "/search", {"text": "房屋"})["items"] == []
    assert "rag_cases" not in inspect(ctx.app.state.database.engine).get_table_names()
    assert inspect(ctx.app.state.rag_database.engine).get_table_names() == ["rag_cases"]


def test_access_validation_and_unavailable_states(rag):
    ctx = rag
    _, tourist = ctx.actor()
    assert ctx.client.get(PREFIX + "/cases").status_code == 401
    assert ctx.client.get(PREFIX + "/cases", headers=tourist).status_code == 403
    legacy = case(ctx)
    post(ctx, "/cases", {"answer": "答案", "character_id": legacy["character_id"]}, expected=409)
    post(ctx, "/cases", {"text": "房屋", "answer": "答案"}, expected=422)
    post(ctx, "/cases", {"answer": "答案", "character_id": "missing"}, expected=404)
    draft = ctx.character(status="draft")
    post(ctx, "/cases", {"answer": "答案", "character_id": draft["id"]}, expected=404)
    post(ctx, "/search", {"text": " "}, expected=422)
    post(ctx, "/search", {"text": "房屋", "limit": 0}, expected=422)
    database = ctx.app.state.rag_database
    ctx.app.state.rag_database = None
    assert ctx.client.get(PREFIX + "/stats", headers=ctx.admin).status_code == 503
    ctx.app.state.rag_database = database
    RagBase.metadata.drop_all(database.engine)
    response = ctx.client.get(PREFIX + "/stats", headers=ctx.admin)
    assert response.status_code == 503
    assert response.json()["code"] == "RAG_DATABASE_UNAVAILABLE"


def test_feedback_review_indexes_once_without_second_review(rag):
    ctx = rag
    character = ctx.character()
    user, headers = ctx.actor()
    recognition_id = ctx.record(user["id"], character["id"])
    with ctx.app.state.database.write() as session:
        session.get(RecognitionRecord, recognition_id).observed_text = "屋顶房屋"
    feedback = ctx.client.post(
        f"/api/v1/recognize/{recognition_id}/confirm",
        headers=headers,
        json={"character_id": character["id"], "comment": "合成纠错"},
    )
    assert feedback.status_code == 200, feedback.text
    path = f"/api/v1/admin/feedback/{feedback.json()['id']}"
    for _ in range(2):
        response = ctx.client.patch(path, headers=ctx.admin, json={"status": "approved"})
        assert response.status_code == 200, response.text
        assert response.json()["rag_status"] == "indexed"
    rows = ctx.client.get(PREFIX + "/cases", headers=ctx.admin).json()
    assert rows["total"] == 1
    assert rows["items"][0]["original_text"] == "屋顶房屋"
    assert rows["items"][0]["status"] == "indexed"
    assert post(ctx, "/search", {"text": "房屋"})["items"][0]["id"] == rows["items"][0]["id"]
    row = rows["items"][0]
    post(ctx, f"/cases/{row['id']}/review", {"status": "approved"}, expected=409)
    assert (
        ctx.client.patch(
            PREFIX + f"/cases/{row['id']}", headers=ctx.admin, json={"answer": "bypass"}
        ).status_code
        == 409
    )
    post(ctx, f"/cases/{row['id']}/deprecate", {"reason": "不再适用"})
    assert post(ctx, "/search", {"text": "房屋"})["items"] == []
    response = ctx.client.patch(path, headers=ctx.admin, json={"status": "approved"})
    assert response.json()["rag_status"] == "deprecated"
    post(ctx, f"/cases/{row['id']}/reindex")
    assert post(ctx, "/search", {"text": "房屋"})["items"]
    detail = ctx.client.get(path, headers=ctx.admin).json()
    assert detail["rag_case"]["id"] == row["id"]
    assert detail["rag_status"] == "indexed"
    RagBase.metadata.drop_all(ctx.app.state.rag_database.engine)
    response = ctx.client.patch(path, headers=ctx.admin, json={"status": "approved"})
    assert response.status_code == 503


def feedback_fixture(ctx, *, character_id=True):
    character = ctx.character()
    user, headers = ctx.actor()
    recognition_id = ctx.record(user["id"], character["id"])
    with ctx.app.state.database.write() as session:
        session.get(RecognitionRecord, recognition_id).observed_text = "房屋"
    response = ctx.client.post(
        f"/api/v1/recognize/{recognition_id}/confirm",
        headers=headers,
        json={"character_id": character["id"] if character_id else None, "comment": "合成测试纠错"},
    )
    assert response.status_code == 200
    return f"/api/v1/admin/feedback/{response.json()['id']}", response.json(), headers


def test_feedback_failure_is_pending_and_rejection_never_indexes(rag):
    ctx = rag
    path, feedback, headers = feedback_fixture(ctx)
    database = ctx.app.state.rag_database
    ctx.app.state.rag_database = None
    response = ctx.client.patch(path, headers=ctx.admin, json={"status": "approved"})
    assert response.status_code == 503
    detail = ctx.client.get(path, headers=ctx.admin).json()
    assert detail["status"] == "pending" and detail["rag_status"] == "unavailable"
    assert ctx.client.get(path, headers=headers).status_code == 403
    assert ctx.client.get(path).status_code == 401
    response = ctx.client.patch(
        path, headers=ctx.admin, json={"status": "rejected", "review_note": "无法核实"}
    )
    assert response.status_code == 200 and response.json()["status"] == "rejected"
    ctx.app.state.rag_database = database
    assert ctx.client.get(PREFIX + "/cases", headers=ctx.admin).json()["total"] == 0
    assert ctx.client.patch(path, headers=ctx.admin, json={"status": "approved"}).status_code == 409


@pytest.mark.parametrize("note", [None, "", "   "])
def test_feedback_rejection_note_is_optional(rag, note):
    path, _, _ = feedback_fixture(rag, character_id=False)
    payload = {"status": "rejected"}
    if note is not None:
        payload["review_note"] = note
    response = rag.client.patch(path, headers=rag.admin, json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "rejected"
    assert response.json()["review_note"] == ""
    assert rag.client.get(path, headers=rag.admin).json()["review_note"] == ""
    assert rag.client.get(PREFIX + "/cases", headers=rag.admin).json()["total"] == 0


def test_feedback_list_tracks_live_rag_state_after_maintenance(rag):
    ctx = rag
    path, feedback, _ = feedback_fixture(ctx)
    listing = "/api/v1/admin/feedback"

    def state(expected):
        response = ctx.client.get(listing, headers=ctx.admin, params={"q": feedback["id"]})
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        row = data["items"][0]
        detail = ctx.client.get(path, headers=ctx.admin).json()
        assert row["rag_status"] == detail["rag_status"] == expected
        assert row["status"] == detail["status"]
        assert row["rag_case_id"] == detail["rag_case_id"]
        assert row["rag_updated_at"] == detail["rag_updated_at"]
        return row

    state("not_indexed")
    response = ctx.client.patch(path, headers=ctx.admin, json={"status": "approved"})
    assert response.status_code == 200
    case_id = response.json()["rag_case_id"]
    assert state("indexed")["status"] == "approved"
    post(ctx, f"/cases/{case_id}/deprecate", {"reason": "核验待复查"})
    row = state("deprecated")
    assert row["status"] == "approved" and row["rag_updated_at"]
    post(ctx, f"/cases/{case_id}/reindex")
    assert state("indexed")["status"] == "approved"
    database = ctx.app.state.rag_database
    try:
        ctx.app.state.rag_database = None
        assert state("unavailable")["status"] == "approved"
    finally:
        ctx.app.state.rag_database = database
    assert ctx.client.get(listing).status_code == 401


def test_text_only_feedback_requires_verified_published_word(rag):
    ctx = rag
    path, _, _ = feedback_fixture(ctx, character_id=False)
    assert ctx.client.patch(path, headers=ctx.admin, json={"status": "approved"}).status_code == 422
    draft = ctx.character(status="draft")
    assert (
        ctx.client.patch(
            path, headers=ctx.admin, json={"status": "approved", "character_id": draft["id"]}
        ).status_code
        == 404
    )
    corrected = ctx.character()
    response = ctx.client.patch(
        path,
        headers=ctx.admin,
        json={"status": "approved", "character_id": corrected["id"], "review_note": "核验来源"},
    )
    assert response.status_code == 200 and response.json()["character_id"] == corrected["id"]
    assert post(ctx, "/search", {"text": "房屋"})["items"][0]["character_id"] == corrected["id"]


def test_orphaned_rag_write_is_not_searchable_and_retry_recovers(rag, monkeypatch):
    from backend.app.business import api as business_api

    ctx = rag
    path, feedback, _ = feedback_fixture(ctx)
    original_audit = business_api.audit

    def fail_audit(*args, **kwargs):
        raise RuntimeError("synthetic business transaction failure")

    monkeypatch.setattr(business_api, "audit", fail_audit)
    with pytest.raises(RuntimeError, match="synthetic business transaction failure"):
        ctx.client.patch(path, headers=ctx.admin, json={"status": "approved"})
    with ctx.app.state.database.session() as session:
        assert session.get(Feedback, feedback["id"]).status == "pending"
    assert ctx.client.get(PREFIX + "/cases", headers=ctx.admin).json()["total"] == 1
    assert post(ctx, "/search", {"text": "房屋"})["items"] == []
    orphan = ctx.client.get(PREFIX + "/cases", headers=ctx.admin).json()["items"][0]
    post(ctx, f"/cases/{orphan['id']}/reindex", expected=409)
    monkeypatch.setattr(business_api, "audit", original_audit)
    response = ctx.client.patch(path, headers=ctx.admin, json={"status": "approved"})
    assert response.status_code == 200
    assert ctx.client.get(PREFIX + "/cases", headers=ctx.admin).json()["total"] == 1
    assert len(post(ctx, "/search", {"text": "房屋"})["items"]) == 1


def test_case_image_uses_business_sample_database(rag):
    ctx = rag
    sample = upload(ctx)
    row = case(ctx, sample_id=sample["id"])
    path = PREFIX + f"/cases/{row['id']}/image"
    response = ctx.client.get(path, headers=ctx.admin)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "image/png"
    assert (
        ctx.client.delete(f"/api/v1/admin/samples/{sample['id']}", headers=ctx.admin).status_code
        == 200
    )
    assert ctx.client.get(path, headers=ctx.admin).status_code == 404


def test_recognition_uses_reviewed_memory_and_falls_back_when_unavailable(rag):
    ctx = rag
    character = ctx.character()
    row = case(ctx, character)
    post(ctx, f"/cases/{row['id']}/review", {"status": "approved"})
    provider = FixtureProvider(
        ProviderResult(model_version="synthetic", candidates=[], observed_text="房屋")
    )
    dictionary = CharacterDictionary([fixture_character(character["id"])])
    settings = ctx.app.state.settings

    def run():
        return asyncio.run(
            recognize(
                image=image_bytes(),
                media_type="image/png",
                request_id="test",
                provider=provider,
                dictionary=dictionary,
                settings=settings,
                rag_database=ctx.app.state.rag_database,
            )
        )

    result = run()
    assert result.status == "NEED_USER_CONFIRM" and result.rag_applied
    assert result.candidates[0].character_id == character["id"]
    assert result.candidates[0].provider_score is None
    assert set(result.rag_hits[0]) == {"id", "character_id", "score", "matched_terms"}
    # A fixture proves orchestration, not real model accuracy.
    RagBase.metadata.drop_all(ctx.app.state.rag_database.engine)
    result = run()
    assert result.status == "UNKNOWN" and not result.rag_applied and not result.rag_hits


def test_limit_counts_only_returned_hits_and_keeps_first_character_rank(rag):
    ctx = rag
    character = ctx.character()
    rows = [case(ctx, character, text=f"房屋 {i}") for i in range(3)]
    for row in rows:
        post(ctx, f"/cases/{row['id']}/review", {"status": "approved"})
    assert post(ctx, "/search", {"text": "房屋", "limit": 1})["total"] == 1
    with ctx.app.state.rag_database.session() as session:
        assert sum(session.get(RagCase, row["id"]).retrieval_count for row in rows) == 1
    characters = [fixture_character(f"TEST_{i}") for i in range(7)]
    dictionary = CharacterDictionary(characters)
    hits = [{"character_id": character.character_id} for character in characters]
    hits.append(hits[0])
    candidates, applied = apply_hits([], hits, dictionary)
    assert applied and len(candidates) == 5
    assert candidates[0].character_id == "TEST_0"
    assert text_terms("房屋 roof") == ["房", "屋", "roof"]


def test_http_recognition_persists_memory_hits_and_allows_user_confirmation(rag):
    ctx = rag
    character = ctx.character()
    row = case(ctx, character)
    post(ctx, f"/cases/{row['id']}/review", {"status": "approved"})
    _, headers = ctx.actor()
    settings = ctx.app.state.settings.model_copy(
        update={
            "auto_create_schema": False,
            "quality_checks_enabled": False,
            "rag_database_url": ctx.app.state.rag_database.engine.url.render_as_string(
                hide_password=False
            ),
        }
    )
    provider = FixtureProvider(
        ProviderResult(model_version="synthetic", candidates=[], observed_text="房屋")
    )
    with TestClient(create_app(settings=settings, provider=provider)) as client:
        response = client.post(
            "/api/v1/recognize",
            headers=headers,
            files={"image": ("fixture.png", image_bytes(), "image/png")},
        )
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["status"] == "NEED_USER_CONFIRM" and result["rag_applied"]
        assert result["candidates"][0]["character_id"] == character["id"]
        with ctx.app.state.database.session() as session:
            record = session.get(RecognitionRecord, result["request_id"])
            assert record.observed_text == "房屋"
            assert record.rag_hits == result["rag_hits"]
        confirmation = client.post(
            f"/api/v1/recognize/{result['request_id']}/confirm",
            headers=headers,
            json={"character_id": character["id"]},
        )
        assert confirmation.status_code == 200, confirmation.text


def test_configured_rag_starts_and_optional_production_config():
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url="sqlite:///:memory:",
        rag_database_url="sqlite:///:memory:",
    )
    app = create_app(settings=settings)
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert inspect(app.state.rag_database.engine).get_table_names() == ["rag_cases"]
    Settings(
        _env_file=None,
        environment="production",
        auto_create_schema=False,
        setup_enabled=False,
        public_base_url="https://example.invalid",
        rag_database_url="",
    )
    with pytest.raises(ValidationError, match="separate database"):
        Settings(
            _env_file=None,
            database_url="mysql+pymysql://one@localhost/db",
            rag_database_url="mysql+pymysql://two@127.0.0.1/db",
        )


def test_unavailable_optional_schema_does_not_block_startup(monkeypatch):
    def unavailable(_self):
        raise OperationalError("synthetic", {}, Exception("synthetic"))

    monkeypatch.setattr(RagDatabase, "create_schema", unavailable)
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url="sqlite:///:memory:",
        rag_database_url="sqlite:///:memory:",
    )
    with TestClient(create_app(settings=settings)) as client:
        assert client.get("/health").status_code == 200
