"""DATA-01/03/04, FEEDBACK-01 and PRIVACY-01; synthetic images, not AI accuracy."""

import json
from datetime import UTC, datetime, timedelta
from io import BytesIO
from zipfile import ZipFile

import pytest
from PIL import Image, ImageDraw

from backend.app.business.models import Entity, EntityRevision, RecognitionRecord, Sample
from backend.app.business.samples import delete_samples, sample_path, store_recognition_sample
from backend.app.maintenance import purge_expired
from backend.tests.test_business_api import context  # noqa: F401


def picture(color="navy"):
    image = Image.new("RGB", (256, 256), "white")
    ImageDraw.Draw(image).rectangle((40, 40, 216, 216), fill=color)
    output = BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


def upload(ctx, endpoint="/api/v1/admin/samples/upload", color="navy"):
    response = ctx.client.post(
        endpoint, headers=ctx.admin, files={"file": ("synthetic.png", picture(color), "image/png")}
    )
    assert response.status_code == 200, response.text
    return response.json()


def retained(ctx, user, character):
    recognition_id = ctx.record(user["id"], character["id"])
    return store_recognition_sample(
        ctx.app.state.database,
        ctx.app.state.business_settings,
        recognition_id=recognition_id,
        user_id=user["id"],
        content=picture(),
        scene="paper",
        consent_version="test-only",
    )


def assert_gone(ctx, row):
    settings = ctx.app.state.business_settings
    path = sample_path(settings, row["image_uri"])
    assert not path.exists()
    assert not path.with_suffix(".png.json").exists()
    with ctx.app.state.database.session() as session:
        assert session.get(Sample, row["id"]) is None
    assert (
        ctx.client.get(f"/api/v1/admin/samples/{row['id']}/image", headers=ctx.admin).status_code
        == 404
    )


def test_clear_history_removes_own_samples_and_files_only(context):  # noqa: F811
    ctx = context
    character = ctx.character()
    owner, headers = ctx.actor()
    other, other_headers = ctx.actor()
    own = retained(ctx, owner, character)
    unrelated = retained(ctx, other, character)
    source = upload(ctx)
    assert (
        ctx.client.get(f"/api/v1/me/samples/{own['id']}/image", headers=headers).status_code == 200
    )
    assert (
        ctx.client.get(f"/api/v1/me/samples/{own['id']}/image", headers=other_headers).status_code
        == 404
    )
    response = ctx.client.delete("/api/v1/me/history", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json() == {"deleted": 1}
    assert_gone(ctx, own)
    assert ctx.client.get("/api/v1/me/history", headers=headers).json()["total"] == 0
    assert ctx.client.get("/api/v1/me/samples", headers=headers).json()["total"] == 0
    for row in (unrelated, source):
        assert sample_path(ctx.app.state.business_settings, row["image_uri"]).exists()
    assert ctx.client.delete("/api/v1/me/history", headers=headers).json() == {"deleted": 0}


def test_retention_deletes_expired_recognition_or_sample_not_operator_sources(context):  # noqa: F811
    ctx = context
    user, _ = ctx.actor()
    character = ctx.character()
    rows = [retained(ctx, user, character) for _ in range(3)]
    source = upload(ctx)
    settings = ctx.app.state.business_settings
    current = datetime.now(UTC)
    old = (current - timedelta(days=settings.retention_days + 1)).isoformat()
    with ctx.app.state.database.write() as session:
        session.get(RecognitionRecord, rows[0]["recognition_id"]).created_at = old
        session.get(Sample, rows[1]["id"]).created_at = old
        session.get(Sample, source["id"]).created_at = old
    source_path = sample_path(settings, source["image_uri"])
    metadata_path = source_path.with_suffix(".png.json")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["created_at"] = old
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    preview = purge_expired(ctx.app.state.database, settings, current_time=current, dry_run=True)
    assert preview["samples"] == 2
    assert preview["recognitions"] == 1
    assert preview["media"] == 0
    for row in (*rows, source):
        assert sample_path(settings, row["image_uri"]).exists()
    result = purge_expired(ctx.app.state.database, settings, current_time=current)
    assert result == preview
    for row in rows[:2]:
        assert_gone(ctx, row)
    for row in (rows[2], source):
        assert sample_path(settings, row["image_uri"]).exists()
    with ctx.app.state.database.session() as session:
        assert session.get(RecognitionRecord, rows[0]["recognition_id"]) is None
        assert session.get(RecognitionRecord, rows[1]["recognition_id"]) is not None
    assert purge_expired(ctx.app.state.database, settings, current_time=current)["samples"] == 0


def test_sample_file_delete_waits_for_commit(context):  # noqa: F811
    ctx = context
    user, _ = ctx.actor()
    row = retained(ctx, user, ctx.character())
    settings = ctx.app.state.business_settings
    with pytest.raises(RuntimeError, match="rollback"):
        with ctx.app.state.database.write() as session:
            assert delete_samples(session, settings, recognition_ids=[row["recognition_id"]]) == 1
            session.flush()
            assert sample_path(settings, row["image_uri"]).exists()
            raise RuntimeError("rollback")
    with ctx.app.state.database.session() as session:
        assert session.get(Sample, row["id"]) is not None
    assert sample_path(settings, row["image_uri"]).exists()


def test_revisions_keep_old_text_glyphs_sources_and_review_after_retention(context):  # noqa: F811
    ctx = context
    old_image = upload(ctx, "/api/v1/media")["url"]
    old_variant = upload(ctx, "/api/v1/media", "green")["url"]
    character = ctx.create(
        "characters",
        {
            "cn_name": "Synthetic old text",
            "culture_summary": "Old reviewed summary",
            "culture_detail": "Old story",
            "source_ref": "synthetic:old",
            "source_no": 42,
            "alias": ["Old alias"],
            "keywords": ["keyword"],
            "commercial_tags": ["tag"],
            "image_url": old_image,
            "variants": [{"image_url": old_variant, "source_ref": "synthetic:variant"}],
            "status": "published",
        },
    )
    path = f"/api/v1/admin/characters/{character['id']}"
    new_image = upload(ctx, "/api/v1/media", "red")["url"]
    updated = ctx.client.patch(
        path,
        headers=ctx.admin,
        json={
            "cn_name": "Synthetic new text",
            "culture_summary": "New summary",
            "culture_detail": "New story",
            "source_ref": "synthetic:new",
            "image_url": new_image,
            "variants": [],
            "status": "draft",
        },
    )
    assert updated.status_code == 200, updated.text
    revisions = ctx.client.get(path + "/revisions", headers=ctx.admin).json()
    assert revisions["total"] == 2
    assert [row["version"] for row in revisions["items"]] == [2, 1]
    assert revisions["items"][1]["snapshot"] == character
    assert revisions["items"][1]["snapshot"]["reviewed_by"] == ctx.admin_user["id"]
    _, visitor = ctx.actor()
    assert ctx.client.get(path + "/revisions", headers=visitor).status_code == 403
    settings = ctx.app.state.business_settings
    old = (datetime.now(UTC) - timedelta(days=settings.retention_days + 1)).isoformat()
    for uri in (old_image, old_variant):
        asset = sample_path(settings, uri)
        metadata_path = asset.with_suffix(".png.json")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["created_at"] = old
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    purge_expired(ctx.app.state.database, settings)
    assert ctx.client.get(path + "/revisions", headers=ctx.admin).json() == revisions
    for uri in (old_image, old_variant):
        assert ctx.client.get(uri, headers=ctx.admin).status_code == 200
        assert ctx.client.get(uri).status_code == 401
        assert ctx.client.get(uri, headers=visitor).status_code == 403


def test_legacy_entity_gets_one_honest_baseline(context):  # noqa: F811
    ctx = context
    with ctx.app.state.database.write() as session:
        session.add(
            Entity(id="legacy", kind="characters", status="draft", data={"cn_name": "Legacy"})
        )
    endpoint = "/api/v1/admin/characters/legacy/revisions"
    first = ctx.client.get(endpoint, headers=ctx.admin).json()
    assert first["total"] == 1
    assert first["items"][0]["action"] == "baseline"
    assert first["items"][0]["actor_id"] is None
    assert first["items"][0]["snapshot"]["cn_name"] == "Legacy"
    assert ctx.client.get(endpoint, headers=ctx.admin).json() == first
    with ctx.app.state.database.session() as session:
        assert session.get(EntityRevision, first["items"][0]["id"]) is not None


def test_sample_review_export_and_correction_never_approve_automatically(context):  # noqa: F811
    ctx = context
    character = ctx.character()
    user, headers = ctx.actor()
    sample = retained(ctx, user, character)
    confirmed = ctx.client.post(
        f"/api/v1/recognize/{sample['recognition_id']}/confirm",
        headers=headers,
        json={"character_id": character["id"], "comment": "Synthetic correction"},
    )
    assert confirmed.status_code == 200, confirmed.text
    row = ctx.client.get("/api/v1/admin/samples", headers=ctx.admin).json()["items"][0]
    assert row["character_id"] == character["id"]
    assert row["label_source"] == "user_correction" and row["review_status"] == "pending"
    endpoint = f"/api/v1/admin/samples/{sample['id']}"
    assert (
        ctx.client.patch(
            endpoint, headers=ctx.admin, json={"review_status": "approved"}
        ).status_code
        == 422
    )
    assert (
        ctx.client.patch(endpoint, headers=ctx.admin, json={"bbox": [250, 0, 20, 20]}).status_code
        == 422
    )
    approved = ctx.client.patch(
        endpoint,
        headers=ctx.admin,
        json={
            "source_ref": "synthetic:review",
            "review_status": "approved",
            "bbox": [0, 0, 256, 256],
            "dataset_version": "test-v1",
            "dataset_split": "test",
        },
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["reviewed_by"] == ctx.admin_user["id"]
    assert ctx.client.get(sample["image_uri"]).status_code == 401
    archive = ctx.client.post(
        "/api/v1/admin/samples/export", headers=ctx.admin, json={"dataset_version": "test-v1"}
    )
    assert archive.status_code == 200, archive.text if archive.status_code != 200 else ""
    with ZipFile(BytesIO(archive.content)) as zipped:
        manifest = json.loads(zipped.read("manifest.json"))
        assert manifest["total"] == 1
        exported = manifest["items"][0]
        assert exported["approved_ground_truth"] is True
        assert zipped.read(exported["image_uri"]).startswith(b"\x89PNG")
    assert (
        ctx.client.post(
            f"/api/v1/recognize/{sample['recognition_id']}/confirm",
            headers=headers,
            json={"character_id": None, "comment": "Changed tourist suggestion"},
        ).status_code
        == 200
    )
    row = ctx.client.get("/api/v1/admin/samples", headers=ctx.admin).json()["items"][0]
    assert row["character_id"] == character["id"] and row["review_status"] == "approved"
    changed = ctx.client.patch(
        endpoint, headers=ctx.admin, json={"source_ref": "synthetic:changed"}
    )
    assert changed.json()["review_status"] == "pending"
    assert changed.json()["reviewed_by"] is None
    assert (
        ctx.client.delete(f"/api/v1/me/samples/{sample['id']}", headers=headers).status_code == 200
    )
    assert_gone(ctx, sample)


def test_recognition_requires_separate_consent_and_never_fakes_provider_success(context):  # noqa: F811
    ctx = context
    _, headers = ctx.actor()
    ctx.app.state.business_settings.quality_checks_enabled = False
    for consent in (False, True):
        response = ctx.client.post(
            "/api/v1/recognize",
            headers=headers,
            files={"image": ("synthetic.png", picture(), "image/png")},
            data={"sample_consent": str(consent).lower(), "sample_scene": "paper"},
        )
        assert response.status_code == 503, response.text
        samples = ctx.client.get("/api/v1/me/samples", headers=headers).json()
        assert samples["total"] == int(consent)
    assert samples["items"][0]["recognition_id"] == response.json()["request_id"]
    invalid = ctx.client.post(
        "/api/v1/recognize",
        headers=headers,
        files={"image": ("broken.png", b"broken", "image/png")},
        data={"sample_consent": "true"},
    )
    assert invalid.status_code == 400
    assert ctx.client.get("/api/v1/me/samples", headers=headers).json()["total"] == 1
