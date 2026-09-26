"""GOV-01/DATA-01: additive SIT import through real app APIs, SQLite and MySQL."""

from backend.tests.test_business_api import context  # noqa: F401
from scripts.seed_sit import Runner


def test_tc_seed_int_001_import_verify_and_repeat_preserve_existing_data(context):  # noqa: F811
    ctx = context
    original = ctx.character()
    ctx.client.headers.update(ctx.admin)
    first = Runner(ctx.client)
    first.seed()
    first.verify()
    assert len(first.created) == 53
    assert not first.existing
    assert all(check["status"] != "FAIL" for check in first.checks), first.checks
    assert any(check["id"] == "TC-REV-001" and check["status"] == "PASS" for check in first.checks)
    before = ctx.client.get("/api/v1/admin/audit").json()["total"]
    second = Runner(ctx.client)
    second.seed()
    assert not second.created
    assert len(second.existing) == 53
    after = ctx.client.get("/api/v1/admin/audit").json()["total"]
    assert before == after, "Re-import must not edit existing records"
    assert ctx.client.get(f"/api/v1/characters/{original['id']}").json() == original
