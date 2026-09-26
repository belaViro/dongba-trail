"""Explicit, additive SIT fixtures for DATA/merchant/coupon/quest acceptance.

No real cultural material or recognition-accuracy claims. Default is a dry run.
"""

import argparse
import json
import sys
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

import httpx
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SUITE = "SIT_V1"
NOTICE = "软件测试专用合成资料，不是真实东巴字、商户或文化解释，不可用于运营或识别准确率评测。"
SOURCE = "synthetic:SIT_V1; software acceptance only; not cultural authority"


def fixture_id(module, number):
    return f"{SUITE}_{module}_{number:03d}"


def display_name(module, number, scenario):
    return f"【SIT-{module}-{number:03d}】{scenario}"


def catalog(instant=None):
    instant = instant or datetime.now(UTC)
    rows = []

    def period(start=-1, end=90):
        return {
            "start_at": (instant + timedelta(days=start)).isoformat(),
            "end_at": (instant + timedelta(days=end)).isoformat(),
        }

    def add(resource, module, number, scenario, **fields):
        key = (
            "cn_name" if resource == "characters" else "title" if resource == "coupons" else "name"
        )
        rows.append(
            (
                resource,
                {
                    "id": fixture_id(module, number),
                    key: display_name(module, number, scenario),
                    "status": "published",
                    **fields,
                },
            )
        )

    names = [
        "基础单字展示",
        "多字释义展示",
        "别名检索",
        "关键词检索",
        "商业标签检索",
        "同字异形展示",
        "长文本排版",
        "历史版本回看",
        "草稿不可公开",
        "待补充资料",
        "已审核未发布",
        "停用不可公开",
    ]
    for number, name in enumerate(names, 1):
        add(
            "characters",
            "DCT",
            number,
            name,
            source_no=910000 + number,
            alias=[f"测试别名{number:02d}"],
            keywords=[f"测试关键词{number:02d}"],
            commercial_tags=["SIT测试标签"],
            category_l1="软件测试（合成）",
            category_l2="功能验收",
            culture_summary=NOTICE,
            culture_detail=(NOTICE + "\n段落用于验证换行与文本显示。") * (20 if number == 7 else 1),
            source_ref=SOURCE,
            tags=["SIT_V1", "合成测试"],
            status="draft"
            if number in (9, 10)
            else "reviewed"
            if number == 11
            else "disabled"
            if number == 12
            else "published",
        )
    for number, name in enumerate(
        [
            "关联商户甲",
            "关联商户乙",
            "无文化关联商户",
            "长名称与地址排版商户",
            "草稿门店",
            "停用门店",
        ],
        1,
    ):
        add(
            "merchants",
            "MCH",
            number,
            name,
            description=NOTICE,
            address=f"测试地址（非真实门店）第{number:02d}号",
            latitude=26.87 + number / 1000,
            longitude=100.23 + number / 1000,
            opening_hours="09:00–18:00（测试配置）",
            character_ids=[] if number == 3 else [fixture_id("DCT", 1)],
            tags=["SIT_V1"],
            status="draft" if number == 5 else "disabled" if number == 6 else "published",
        )
    for number in range(1, 7):
        add(
            "pois",
            "POI",
            number,
            ["文化场所", "景点", "关联门店", "无商户点位", "草稿点位", "停用点位"][number - 1],
            description=NOTICE,
            latitude=26.87 + number / 2000,
            longitude=100.23 + number / 2000,
            poi_type=["culture", "attraction", "merchant"][(number - 1) % 3],
            merchant_id=fixture_id("MCH", 1) if number == 3 else None,
            character_ids=[fixture_id("DCT", 1)],
            status="draft" if number == 5 else "disabled" if number == 6 else "published",
        )
    for number, price in enumerate([29.90, 0, 0.01, 9999.99, 10, 18.50, 28, 38], 1):
        add(
            "products",
            "PRD",
            number,
            [
                "常规价格商品",
                "零价格边界",
                "最小货币单位",
                "大金额排版",
                "商户乙商品",
                "草稿商品",
                "停用商品",
                "停用商户关联商品",
            ][number - 1],
            merchant_id=fixture_id("MCH", 2 if number == 5 else 6 if number == 8 else 1),
            description=NOTICE,
            price=price,
            character_ids=[fixture_id("DCT", 1)],
            status="draft" if number == 6 else "disabled" if number == 7 else "published",
        )
    for number, name in enumerate(
        [
            "有效单人限领券",
            "零库存券",
            "已过期券",
            "未开始券",
            "多次限领券",
            "草稿券",
            "停用券",
            "商户乙核销券",
        ],
        1,
    ):
        dates = period(-90, -1) if number == 3 else period(30, 90) if number == 4 else period()
        add(
            "coupons",
            "CPN",
            number,
            name,
            merchant_id=fixture_id("MCH", 2 if number == 8 else 1),
            rule="仅软件测试，无实际优惠或兑付义务。",
            stock=0 if number == 2 else 100,
            per_user_limit=3 if number == 5 else 1,
            **dates,
            status="draft" if number == 6 else "disabled" if number == 7 else "published",
        )
    for number, name in enumerate(
        ["有效活动", "未开始活动", "已结束活动", "草稿活动", "停用活动"], 1
    ):
        dates = period(30, 90) if number == 2 else period(-90, -1) if number == 3 else period()
        add(
            "activities",
            "ACT",
            number,
            name,
            description=NOTICE,
            merchant_id=fixture_id("MCH", 1),
            capacity=20,
            **dates,
            status="draft" if number == 4 else "disabled" if number == 5 else "published",
        )
    for number, name in enumerate(["五类任务联调路线", "未开始路线", "草稿路线"], 1):
        add(
            "quests",
            "QST",
            number,
            name,
            description=NOTICE,
            area="测试区域（禁止实际导航）",
            **(period(30, 90) if number == 2 else period()),
            status="draft" if number == 3 else "published",
        )
    for number, (condition, name) in enumerate(
        [
            ("recognition", "识别确认节点"),
            ("qr", "扫码节点"),
            ("geofence", "围栏节点"),
            ("coupon", "核销节点"),
            ("manual", "人工确认节点"),
        ],
        1,
    ):
        add(
            "quest-nodes",
            "NOD",
            number,
            name,
            quest_id=fixture_id("QST", 1),
            condition=condition,
            sequence=number,
            **({"character_id": fixture_id("DCT", 1)} if condition == "recognition" else {}),
            **({"poi_id": fixture_id("POI", 1)} if condition == "geofence" else {}),
            **({"merchant_id": fixture_id("MCH", 1)} if condition == "coupon" else {}),
        )
    return rows


def test_image(label, variant=0):
    image = Image.new("RGB", (640, 400), "#eef4f3")
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 620, 380), outline="#176b63", width=5)
    draw.text((40, 40), "SYNTHETIC SOFTWARE TEST - NOT A REAL GLYPH", fill="#162b29")
    draw.text((40, 70), label, fill="#162b29")
    draw.text((40, 345), f"SIT_V1 / TEST ONLY / VERSION {variant + 1}", fill="#162b29")
    if variant:
        draw.ellipse((220, 130, 420, 315), outline="#ab5430", width=16)
    else:
        draw.rectangle((220, 130, 420, 315), outline="#176b63", width=16)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def check_target(base):
    parsed = urlparse(base)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost"}
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ValueError("Only a credential-free loopback HTTP origin is allowed")


class Runner:
    def __init__(self, client):
        self.client = client
        self.created, self.existing, self.checks = [], [], []

    def request(self, method, path, **kwargs):
        for attempt in range(3):
            response = self.client.request(method, path, **kwargs)
            if response.status_code != 429 or attempt == 2:
                return response
            time.sleep(61)
        raise AssertionError("unreachable")

    def json(self, method, path, **kwargs):
        response = self.request(method, path, **kwargs)
        if response.status_code != 200:
            raise RuntimeError(f"{method} {path}: HTTP {response.status_code}")
        return response.json()

    def check(self, case, passed, detail=""):
        self.checks.append({"id": case, "status": "PASS" if passed else "FAIL", "detail": detail})

    def upload(self, label, variant=0):
        return self.json(
            "POST",
            "/api/v1/media",
            files={"file": (f"{label}.png", test_image(label, variant), "image/png")},
        )["url"]

    def seed(self):
        for resource, payload in catalog():
            key = (
                "cn_name"
                if resource == "characters"
                else "title"
                if resource == "coupons"
                else "name"
            )
            marker = payload[key].split("】")[0] + "】"
            listing = self.json("GET", f"/api/v1/admin/{resource}", params={"q": marker})
            existing = next((row for row in listing["items"] if row["id"] == payload["id"]), None)
            if existing:
                self.existing.append(payload["id"])
                continue
            if resource in {"characters", "merchants", "products"}:
                payload["image_url"] = self.upload(payload["id"])
            if payload["id"] == fixture_id("DCT", 6):
                payload["variants"] = [
                    {"image_url": self.upload(payload["id"], 1), "source_ref": SOURCE}
                ]
            row = self.json("POST", f"/api/v1/admin/{resource}", json=payload)
            self.created.append({"resource": resource, "id": row["id"]})
            print(f"CREATED {resource} {row['id']}", flush=True)
            if row["id"] == fixture_id("DCT", 8):
                self.json(
                    "PATCH",
                    f"/api/v1/admin/characters/{row['id']}",
                    json={
                        "culture_detail": NOTICE + "\n版本2：用于与版本1的文本和图片进行对照。",
                        "image_url": self.upload(row["id"], 1),
                    },
                )

    def verify(self):
        for number, (resource, _) in enumerate(dict(catalog()).items(), 1):
            # One collection assertion per module; all pages are checked explicitly.
            rows = self.json(
                "GET", f"/api/v1/admin/{resource}", params={"q": "【SIT-", "limit": 100}
            )
            expected = {p["id"] for r, p in catalog() if r == resource}
            actual = {p["id"] for p in rows["items"]}
            self.check(
                f"TC-SEED-{number:03d}", expected <= actual, f"{resource}: {len(expected)} expected"
            )
        for number, status in [(1, 200), (9, 404), (11, 404), (12, 404)]:
            response = self.request("GET", f"/api/v1/characters/{fixture_id('DCT', number)}")
            self.check(
                f"TC-DCT-{number:03d}",
                response.status_code == status,
                f"HTTP {response.status_code}; expected {status}",
            )
        rows = self.json(
            "GET", "/api/v1/admin/characters", params={"q": "【SIT-DCT-", "limit": 100}
        )
        for number, row in enumerate(rows["items"], 1):
            response = self.request("GET", row["image_url"])
            valid = response.status_code == 200 and response.content.startswith(
                b"\x89PNG\r\n\x1a\n"
            )
            self.check(f"TC-IMG-{number:03d}", valid, row["id"])
        response = self.request("GET", f"/api/v1/admin/characters/{fixture_id('DCT', 8)}/revisions")
        if response.status_code == 404:
            self.checks.append(
                {"id": "TC-REV-001", "status": "BLOCKED", "detail": "Revision route unavailable"}
            )
        else:
            snapshots = [r["snapshot"] for r in response.json().get("items", [])]
            self.check(
                "TC-REV-001",
                response.status_code == 200
                and len({r.get("image_url") for r in snapshots}) >= 2
                and len({r.get("culture_detail") for r in snapshots}) >= 2,
                "Two distinct text and image snapshots",
            )
        invalid = [
            ("TC-VAL-001", "characters", {"cn_name": ""}),
            ("TC-VAL-002", "characters", {"cn_name": "X" * 101}),
            ("TC-VAL-003", "characters", {"source_no": -1}),
            ("TC-VAL-004", "merchants", {"latitude": 91}),
            ("TC-VAL-005", "pois", {"longitude": 181}),
            ("TC-VAL-006", "products", {"price": -0.01}),
            ("TC-VAL-007", "coupons", {"stock": -1}),
            ("TC-VAL-008", "coupons", {"per_user_limit": 0}),
            ("TC-VAL-009", "activities", {"capacity": 0}),
            ("TC-VAL-010", "quest-nodes", {"radius_m": 9}),
        ]
        for case, resource, change in invalid:
            original = next(p for r, p in catalog() if r == resource)
            path = f"/api/v1/admin/{resource}/{original['id']}"
            before = self.json(
                "GET",
                f"/api/v1/admin/{resource}",
                params={"q": original.get("cn_name", original.get("title", original.get("name")))},
            )
            response = self.request("PATCH", path, json=change)
            after = self.json(
                "GET",
                f"/api/v1/admin/{resource}",
                params={"q": original.get("cn_name", original.get("title", original.get("name")))},
            )
            self.check(
                case,
                response.status_code == 422 and before == after,
                f"HTTP {response.status_code}; rejected without mutation",
            )
        response = self.request("GET", "/api/v1/admin/samples", params={"limit": 1})
        self.checks.append(
            {
                "id": "TC-SMP-001",
                "status": "NOT_RUN" if response.status_code == 200 else "BLOCKED",
                "detail": f"Sample route HTTP {response.status_code}; no fabricated samples",
            }
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8010")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--allow-published-test-data", action="store_true")
    parser.add_argument("--confirm-database")
    parser.add_argument("--report", type=Path, default=ROOT / "runtime/sit-v1/report.json")
    args = parser.parse_args()
    check_target(args.base)
    counts = dict(Counter(resource for resource, _ in catalog()))
    if not args.apply:
        print(
            json.dumps(
                {
                    "mode": "DRY_RUN",
                    "suite": SUITE,
                    "counts": counts,
                    "total": sum(counts.values()),
                    "notice": NOTICE,
                },
                ensure_ascii=False,
            )
        )
        return
    if not args.allow_published_test_data or not args.confirm_database:
        raise SystemExit("Explicit synthetic-publication approval and database name required")
    from sqlalchemy import delete, select
    from sqlalchemy.engine import make_url

    from backend.app.business.auth import digest, token_response
    from backend.app.business.database import Database
    from backend.app.business.models import Audit, SessionToken, User
    from backend.app.config import Settings

    settings = Settings()
    if make_url(settings.database_url).database != args.confirm_database:
        raise SystemExit("Database confirmation mismatch; no changes made")
    if not settings.database_url.startswith("mysql+pymysql://"):
        raise SystemExit("Live seeding requires MySQL")
    database = Database(settings.database_url)
    token = None
    report = {"suite": SUITE, "started_at": datetime.now(UTC).isoformat(), "counts": counts}
    runner = None
    try:
        with database.write() as session:
            actor_id = session.scalar(
                select(User.id).where(User.role == "admin", User.status == "active")
            )
            if actor_id is None:
                raise RuntimeError("No active administrator; no account will be created or reset")
            # Load only public identity fields, not stored passwords or other credentials.
            identity = session.execute(
                select(
                    User.id,
                    User.username,
                    User.display_name,
                    User.role,
                    User.merchant_id,
                    User.status,
                    User.created_at,
                ).where(User.id == actor_id)
            ).one()
            from types import SimpleNamespace

            actor = SimpleNamespace(**identity._mapping)
            token = token_response(session, actor, SimpleNamespace(session_hours=1))["access_token"]
            session.add(
                Audit(
                    user_id=actor_id,
                    action="seed_sit",
                    entity_type="test_suite",
                    entity_id=SUITE,
                    detail={"synthetic": True, "additive_only": True},
                )
            )
        with httpx.Client(
            base_url=args.base,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
            trust_env=False,
        ) as client:
            runner = Runner(client)
            me = runner.json("GET", "/api/v1/auth/me")
            if me["id"] != actor_id:
                raise RuntimeError("API/database identity mismatch")
            runner.seed()
            runner.verify()
    except Exception as exc:
        # Never serialize library exception strings: they may include connection credentials.
        report["error_type"] = type(exc).__name__
        print(f"STOPPED {type(exc).__name__}; inspect scoped report, rerun is additive", flush=True)
    finally:
        if token:
            with database.write() as session:
                session.execute(
                    delete(SessionToken).where(SessionToken.token_hash == digest(token))
                )
        database.engine.dispose()
        if runner:
            report.update(created=runner.created, existing=runner.existing, checks=runner.checks)
        report["finished_at"] = datetime.now(UTC).isoformat()
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            json.dumps(
                {
                    "created": len(report.get("created", [])),
                    "existing": len(report.get("existing", [])),
                    "checks": dict(Counter(c["status"] for c in report.get("checks", []))),
                    "error_type": report.get("error_type"),
                },
                ensure_ascii=False,
            )
        )
    if report.get("error_type") or any(c["status"] == "FAIL" for c in report.get("checks", [])):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
