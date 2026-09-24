from datetime import UTC, datetime, timedelta
from io import BytesIO

import pytest
from PIL import Image, ImageDraw
from sqlalchemy import select

from backend.app.business.models import Entity, Event, Feedback, RecognitionRecord
from backend.app.config import Settings
from backend.app.errors import ApiError
from backend.app.maintenance import purge_expired
from backend.app.media import referenced_asset_names, save_asset
from backend.app.recognition import assess_image_quality
from backend.tests.test_integration import system  # noqa: F401


@pytest.mark.parametrize(
    ("color", "size", "code"),
    [
        ("gray", (32, 32), "IMAGE_TOO_SMALL"),
        ("black", (256, 256), "IMAGE_TOO_DARK"),
        ("white", (256, 256), "IMAGE_OVEREXPOSED"),
        ("gray", (256, 256), "IMAGE_BLURRY"),
    ],
)
def test_quality_rejects_unusable_images(color, size, code):
    output = BytesIO()
    Image.new("RGB", size, color).save(output, "PNG")
    with pytest.raises(ApiError) as exc:
        assess_image_quality(output.getvalue(), Settings(_env_file=None))
    assert exc.value.code == code


def test_quality_preserves_image_with_detail():
    image = Image.new("RGB", (256, 256), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((50, 50, 200, 200), fill="black")
    output = BytesIO()
    image.save(output, "PNG")
    assess_image_quality(output.getvalue(), Settings(_env_file=None))


def test_failed_image_validation_is_in_owner_history(system):  # noqa: F811
    client, _, users, settings = system
    settings.quality_checks_enabled = True
    failed = client.post(
        "/api/v1/recognize", headers=users[0], files={"image": ("bad.png", b"broken", "image/png")}
    )
    assert failed.status_code == 400
    history = client.get("/api/v1/me/history", headers=users[0]).json()
    assert history["items"][0]["error_code"] == "INVALID_IMAGE"
    assert history["items"][0]["request_id"] == failed.json()["request_id"]
    assert client.get("/api/v1/me/history", headers=users[1]).json()["total"] == 0


def test_media_publication_requires_exact_typed_reference():
    settings = Settings(_env_file=None)
    name = "a" * 32 + ".png"
    assert referenced_asset_names(settings, [{"description": name}]) == set()
    assert (
        referenced_asset_names(settings, [{"image_url": f"https://evil.invalid/{name}"}]) == set()
    )
    assert referenced_asset_names(
        settings, [{"variants": [{"image_url": f"/api/v1/media/{name}"}]}]
    ) == {name}


def test_retention_deletes_old_personal_data_and_preserves_content(system):  # noqa: F811
    client, _, users, settings = system
    user_id = client.get("/api/v1/auth/me", headers=users[0]).json()["id"]
    database = client.app.state.database
    now = datetime.now(UTC)
    old = (now - timedelta(days=settings.retention_days + 2)).isoformat()
    with database.write() as session:
        session.add(
            RecognitionRecord(
                request_id="expired",
                user_id=user_id,
                status="UNKNOWN",
                provider="test",
                model="test",
                created_at=old,
            )
        )
        session.add(
            RecognitionRecord(
                request_id="recent",
                user_id=user_id,
                status="UNKNOWN",
                provider="test",
                model="test",
            )
        )
        session.flush()
        session.add(Feedback(recognition_id="expired", user_id=user_id, created_at=old))
        session.add(
            Event(
                event_id="recent-event",
                user_id=user_id,
                event="character_detail",
                recognition_id="expired",
            )
        )
        session.add(Event(event_id="old-event", user_id=user_id, event="home_view", created_at=old))
    poster = save_asset(settings, Image.new("RGB", (32, 32)), user_id, "poster")
    glyph = save_asset(settings, Image.new("RGB", (32, 32)), user_id, "content")
    with database.write() as session:
        session.add(
            Entity(
                id="retained",
                kind="characters",
                status="draft",
                data={"image_url": f"/api/v1/media/{glyph}"},
            )
        )
    future = now + timedelta(days=settings.retention_days + 1)
    preview = purge_expired(database, settings, current_time=future, dry_run=True)
    assert preview["media"] == 1
    assert (settings.media_directory / poster).exists()
    counts = purge_expired(database, settings, current_time=now)
    assert counts["recognitions"] == 1
    assert counts["feedback"] == 1
    assert counts["events"] == 1
    with database.session() as session:
        assert session.get(RecognitionRecord, "expired") is None
        assert session.get(RecognitionRecord, "recent") is not None
        assert session.scalar(select(Event)).recognition_id is None
    purge_expired(database, settings, current_time=future)
    assert not (settings.media_directory / poster).exists()
    assert (settings.media_directory / glyph).exists()
