"""OPS-01 / AUTH-02 / DATA-04: synthetic one-step publication regressions."""

import pytest
from sqlalchemy import select

from backend.app.business.models import Audit, Entity, EntityRevision
from backend.tests.test_business_api import context  # noqa: F401


@pytest.mark.parametrize("role", ["admin", "operator"])
def test_publish_records_reviewer_audit_and_revision(context, role):  # noqa: F811
    ctx = context
    user, headers = (ctx.admin_user, ctx.admin) if role == "admin" else ctx.actor(role)
    row = ctx.character("draft")
    response = ctx.client.patch(
        f"/api/v1/admin/characters/{row['id']}", headers=headers, json={"status": "published"}
    )
    assert response.status_code == 200, response.text
    published = response.json()
    assert published["status"] == "published"
    assert published["reviewed_by"] == user["id"] and published["reviewed_at"]
    assert ctx.client.get(f"/api/v1/characters/{row['id']}").status_code == 200
    with ctx.app.state.database.session() as session:
        audit = session.scalar(
            select(Audit).where(Audit.entity_id == row["id"], Audit.action == "review_publish")
        )
        assert audit.user_id == user["id"] and audit.detail["status"] == "published"
        revision = session.scalar(
            select(EntityRevision).where(
                EntityRevision.entity_id == row["id"], EntityRevision.action == "publish"
            )
        )
        assert revision.actor_id == user["id"]
        assert revision.snapshot["reviewed_by"] == user["id"]


@pytest.mark.parametrize("field", ["source_ref", "culture_summary", "image_url"])
def test_combined_publish_keeps_validation_and_draft_on_failure(context, field):  # noqa: F811
    ctx = context
    _, operator = ctx.actor("operator")
    row = ctx.character("draft")
    path = f"/api/v1/admin/characters/{row['id']}"
    assert ctx.client.patch(path, headers=ctx.admin, json={field: ""}).status_code == 200
    response = ctx.client.patch(path, headers=operator, json={"status": "published"})
    assert response.status_code == 422
    assert ctx.client.get(f"/api/v1/characters/{row['id']}").status_code == 404
    with ctx.app.state.database.session() as session:
        stored = session.get(Entity, row["id"])
        assert stored.status == "draft" and stored.reviewed_by is None
        assert (
            session.scalar(
                select(Audit).where(Audit.entity_id == row["id"], Audit.action == "review_publish")
            )
            is None
        )


def test_merchants_cannot_publish_via_either_workspace(context):  # noqa: F811
    ctx = context
    merchant = ctx.merchant()
    _, owner = ctx.actor("merchant", merchant["id"])
    product = ctx.create(
        "products", {"merchant_id": merchant["id"], "name": "Synthetic product", "status": "draft"}
    )
    for workspace in ("merchant", "admin"):
        response = ctx.client.patch(
            f"/api/v1/{workspace}/products/{product['id']}",
            headers=owner,
            json={"status": "published"},
        )
        assert response.status_code == 403
    with ctx.app.state.database.session() as session:
        assert session.get(Entity, product["id"]).status == "draft"


def test_legacy_reviewed_content_remains_private(context):  # noqa: F811
    row = context.character("reviewed")
    assert context.client.get(f"/api/v1/characters/{row['id']}").status_code == 404
    with context.app.state.database.session() as session:
        assert session.get(Entity, row["id"]).status == "reviewed"
