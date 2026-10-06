"""DATA-03 / FEEDBACK-01: explicitly consented, private correction attachments."""

import pytest

from backend.tests.test_business_api import context  # noqa: F401
from backend.tests.test_data_foundation import assert_gone, picture


def attach(ctx, recognition_id, headers, *, consent="true", content=None):
    return ctx.client.post(
        f"/api/v1/recognize/{recognition_id}/image",
        headers=headers,
        data={"sample_consent": consent},
        files={"image": ("synthetic.png", picture() if content is None else content, "image/png")},
    )


def test_correction_image_is_retained_and_visible_only_to_authorized_viewers(context):  # noqa: F811
    ctx = context
    owner, headers = ctx.actor()
    _, other_headers = ctx.actor()
    word = ctx.character()
    recognition_id = ctx.record(owner["id"], word["id"])
    response = attach(ctx, recognition_id, headers)
    assert response.status_code == 200, response.text
    sample = response.json()
    assert sample["label_source"] == "user_correction"
    assert sample["consent_version"] == ctx.app.state.business_settings.privacy_version
    feedback = ctx.client.post(
        f"/api/v1/recognize/{recognition_id}/confirm",
        headers=headers,
        json={"character_id": word["id"], "comment": "Synthetic correction"},
    )
    assert feedback.status_code == 200, feedback.text
    detail = ctx.client.get(f"/api/v1/admin/feedback/{feedback.json()['id']}", headers=ctx.admin)
    assert detail.status_code == 200
    assert detail.json()["sample"]["id"] == sample["id"]
    assert detail.json()["sample"]["character_id"] == word["id"]
    image_url = f"/api/v1/admin/samples/{sample['id']}/image"
    image = ctx.client.get(image_url, headers=ctx.admin)
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/png"
    assert image.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert ctx.client.get(image_url).status_code == 401
    assert ctx.client.get(image_url, headers=other_headers).status_code == 403
    own_url = f"/api/v1/me/samples/{sample['id']}/image"
    assert ctx.client.get(own_url, headers=headers).status_code == 200
    assert ctx.client.get(own_url, headers=other_headers).status_code == 404
    assert ctx.client.get(sample["image_uri"]).status_code != 200
    retry = attach(ctx, recognition_id, headers, content=picture("red"))
    assert retry.status_code == 200
    assert retry.json()["id"] == sample["id"]
    assert ctx.client.get(image_url, headers=ctx.admin).content == image.content
    assert ctx.client.delete("/api/v1/me/history", headers=headers).status_code == 200
    assert_gone(ctx, sample)
    assert attach(ctx, recognition_id, headers).status_code == 404


def test_correction_image_needs_consent_owner_and_valid_image(context):  # noqa: F811
    ctx = context
    owner, headers = ctx.actor()
    _, other_headers = ctx.actor()
    recognition_id = ctx.record(owner["id"], ctx.character()["id"])
    assert attach(ctx, recognition_id, {}).status_code == 401
    response = attach(ctx, recognition_id, headers, consent="false")
    assert response.status_code == 422
    assert response.json()["code"] == "SAMPLE_CONSENT_REQUIRED"
    assert attach(ctx, recognition_id, other_headers).status_code == 404
    assert attach(ctx, recognition_id, headers, content=b"not an image").status_code == 400
    assert ctx.client.get("/api/v1/me/samples", headers=headers).json()["total"] == 0


@pytest.mark.parametrize("status", ["approved", "rejected"])
def test_reviewed_feedback_evidence_cannot_be_added_or_replaced(context, status):  # noqa: F811
    from backend.app.business.models import Feedback

    ctx = context
    owner, headers = ctx.actor()
    recognition_id = ctx.record(owner["id"], ctx.character()["id"])
    with ctx.app.state.database.write() as session:
        session.add(Feedback(recognition_id=recognition_id, user_id=owner["id"], status=status))
    response = attach(ctx, recognition_id, headers)
    assert response.status_code == 409
    assert response.json()["code"] == "FEEDBACK_REVIEWED"
    assert ctx.client.get("/api/v1/me/samples", headers=headers).json()["total"] == 0
