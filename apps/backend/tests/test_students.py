import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.models import ActivityLog, Program, Student
from app.models.enums import ProgramStatus, ProgramType, StudentStatus


def create(client, **kw):
    body = {"first_name": "علی", "last_name": "رضایی", **kw}
    r = client.post("/api/students", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def actions(student_id):
    with SessionLocal() as s:
        return [
            a.action
            for a in s.scalars(
                select(ActivityLog).where(ActivityLog.student_id == uuid.UUID(student_id)).order_by(ActivityLog.created_at)
            )
        ]


def test_requires_auth(client):
    sid = uuid.uuid4()
    assert client.get("/api/students").status_code == 401
    assert client.get(f"/api/students/{sid}").status_code == 401
    assert client.post("/api/students", json={"first_name": "a", "last_name": "b"},
                       headers={"X-Requested-With": "fetch"}).status_code == 401
    assert client.get(f"/api/students/{sid}/profile-photo").status_code == 401


def test_create_minimal_only_names_required(auth_client):
    s = create(auth_client)
    assert s["full_name"] == "علی رضایی"
    assert s["status"] == "active"
    assert s["phone"] is None and s["height_cm"] is None and s["last_program"] is None
    assert actions(s["id"]) == ["student.created"]


def test_create_full_and_normalization(auth_client):
    s = create(
        auth_client,
        first_name="  علي ",  # Arabic yeh
        last_name="كريمي",     # Arabic kaf/yeh
        phone="۰۹۱۲-۱۲۳ ۴۵۶۷",
        birth_date="1995-05-01",
        gender="male",
        height_cm=180.5,
        initial_weight_kg="85",
        current_weight_kg=82.4,
        training_history="  ۲ سال بدنسازی ",
        goal="کاهش چربی",
        limitations_notes="",
        start_date="2026-09-01",
        coach_notes="—",
    )
    assert s["first_name"] == "علی" and s["last_name"] == "کریمی"
    assert s["phone"] == "09121234567"
    assert s["height_cm"] == "180.5" and s["current_weight_kg"] == "82.4"
    assert s["training_history"] == "۲ سال بدنسازی"
    assert s["limitations_notes"] is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("first_name", ""),
        ("first_name", "   "),
        ("last_name", "x" * 101),
        ("phone", "123"),
        ("height_cm", 400),
        ("current_weight_kg", 5),
        ("birth_date", (date.today() + timedelta(days=1)).isoformat()),
        ("gender", "unknown"),
    ],
)
def test_validation(auth_client, field, value):
    body = {"first_name": "علی", "last_name": "رضایی", field: value}
    r = auth_client.post("/api/students", json=body)
    assert r.status_code == 422


def test_phone_not_unique(auth_client):
    create(auth_client, phone="09120000000")
    create(auth_client, first_name="مریم", phone="09120000000")


def test_get_and_404(auth_client):
    s = create(auth_client)
    assert auth_client.get(f"/api/students/{s['id']}").json()["id"] == s["id"]
    assert auth_client.get(f"/api/students/{uuid.uuid4()}").status_code == 404
    assert auth_client.get("/api/students/not-a-uuid").status_code == 422


def test_update_logs_changed_fields_only(auth_client):
    s = create(auth_client, phone="09121111111")
    body = {"first_name": "علی", "last_name": "رضایی", "phone": "09121111111", "goal": "افزایش حجم",
            "status": "active"}
    r = auth_client.put(f"/api/students/{s['id']}", json=body)
    assert r.status_code == 200 and r.json()["goal"] == "افزایش حجم"
    with SessionLocal() as db:
        log = db.scalars(select(ActivityLog).where(ActivityLog.action == "student.updated")).one()
    assert log.meta == {"fields": ["goal"]}
    # no-op update logs nothing new
    auth_client.put(f"/api/students/{s['id']}", json=body)
    assert actions(s["id"]).count("student.updated") == 1


def test_put_replaces_optional_fields(auth_client):
    s = create(auth_client, phone="09121111111", goal="هدف")
    r = auth_client.put(f"/api/students/{s['id']}", json={"first_name": "علی", "last_name": "رضایی"})
    assert r.json()["phone"] is None and r.json()["goal"] is None


def test_archive_restore_and_deactivate(auth_client):
    s = create(auth_client)
    sid = s["id"]
    r = auth_client.delete(f"/api/students/{sid}")
    assert r.status_code == 200 and r.json()["status"] == "archived" and r.json()["archived_at"]
    # Still retrievable — soft delete
    assert auth_client.get(f"/api/students/{sid}").status_code == 200
    base = {"first_name": "علی", "last_name": "رضایی"}
    r = auth_client.put(f"/api/students/{sid}", json={**base, "status": "active"})
    assert r.json()["status"] == "active" and r.json()["archived_at"] is None
    auth_client.put(f"/api/students/{sid}", json={**base, "status": "inactive"})
    assert actions(sid) == ["student.created", "student.archived", "student.restored", "student.deactivated"]


def test_archive_keeps_programs(auth_client):
    s = create(auth_client)
    with SessionLocal() as db:
        db.add(Program(student_id=uuid.UUID(s["id"]), title="برنامه", program_type=ProgramType.workout,
                       status=ProgramStatus.approved, approved_at=datetime.now(UTC)))
        db.commit()
    auth_client.delete(f"/api/students/{s['id']}")
    progs = auth_client.get(f"/api/students/{s['id']}/programs").json()
    assert len(progs) == 1 and progs[0]["title"] == "برنامه"


# ---- list / search / filter / sort / pagination ---------------------------


@pytest.fixture()
def roster(auth_client):
    a = create(auth_client, first_name="علی", last_name="رضایی", phone="09121234567", current_weight_kg=80,
               start_date="2026-01-10")
    b = create(auth_client, first_name="مریم", last_name="کریمی", phone="09359876543", current_weight_kg=60,
               start_date="2026-05-01")
    c = create(auth_client, first_name="رضا", last_name="احمدی", start_date="2025-12-01")
    d = create(auth_client, first_name="سارا", last_name="یوسفی")
    base = {"first_name": "سارا", "last_name": "یوسفی"}
    auth_client.put(f"/api/students/{d['id']}", json={**base, "status": "inactive"})
    auth_client.delete(f"/api/students/{c['id']}")
    return {"a": a, "b": b, "c": c, "d": d}


def names(r):
    assert r.status_code == 200, r.text
    return [i["full_name"] for i in r.json()["items"]]


def test_default_list_hides_archived(auth_client, roster):
    r = auth_client.get("/api/students")
    assert set(names(r)) == {"علی رضایی", "مریم کریمی", "سارا یوسفی"}
    assert r.json()["total"] == 3


def test_status_filters(auth_client, roster):
    assert names(auth_client.get("/api/students?status=archived")) == ["رضا احمدی"]
    assert names(auth_client.get("/api/students?status=inactive")) == ["سارا یوسفی"]
    assert len(names(auth_client.get("/api/students?status=all"))) == 4
    assert len(names(auth_client.get("/api/students?status=active"))) == 2


def test_search_by_name_partial_and_full(auth_client, roster):
    assert names(auth_client.get("/api/students", params={"q": "کری"})) == ["مریم کریمی"]
    assert names(auth_client.get("/api/students", params={"q": "مریم کریمی"})) == ["مریم کریمی"]
    # "رضا" matches رضایی (substring); archived رضا احمدی hidden by default
    assert names(auth_client.get("/api/students", params={"q": "رضا"})) == ["علی رضایی"]


def test_search_normalizes_arabic_letters_and_digits(auth_client, roster):
    assert names(auth_client.get("/api/students", params={"q": "كريمي"})) == ["مریم کریمی"]
    assert names(auth_client.get("/api/students", params={"q": "۹۸۷۶"})) == ["مریم کریمی"]
    assert names(auth_client.get("/api/students", params={"q": "0912"})) == ["علی رضایی"]


def test_search_wildcards_are_literal(auth_client, roster):
    assert names(auth_client.get("/api/students", params={"q": "%"})) == []
    assert names(auth_client.get("/api/students", params={"q": "_"})) == []


def test_sorting(auth_client, roster):
    r = auth_client.get("/api/students?sort=current_weight&order=desc")
    assert names(r) == ["علی رضایی", "مریم کریمی", "سارا یوسفی"]  # nulls last
    r = auth_client.get("/api/students?sort=start_date&order=asc&status=all")
    assert names(r)[:3] == ["رضا احمدی", "علی رضایی", "مریم کریمی"]
    r = auth_client.get("/api/students?sort=name&order=asc")
    assert names(r) == ["علی رضایی", "مریم کریمی", "سارا یوسفی"]  # by last name


def test_pagination(auth_client, roster):
    r1 = auth_client.get("/api/students?page=1&page_size=2&sort=created_at&order=asc").json()
    r2 = auth_client.get("/api/students?page=2&page_size=2&sort=created_at&order=asc").json()
    assert r1["total"] == r2["total"] == 3
    assert len(r1["items"]) == 2 and len(r2["items"]) == 1
    assert {i["id"] for i in r1["items"]}.isdisjoint({i["id"] for i in r2["items"]})
    assert auth_client.get("/api/students?page_size=1000").status_code == 422


def test_last_program_is_latest_non_draft(auth_client):
    s = create(auth_client)
    sid = uuid.UUID(s["id"])
    now = datetime.now(UTC)
    with SessionLocal() as db:
        db.add_all([
            Program(student_id=sid, title="قدیمی", program_type=ProgramType.workout,
                    status=ProgramStatus.archived, approved_at=now - timedelta(days=30)),
            Program(student_id=sid, title="جدید", program_type=ProgramType.nutrition,
                    status=ProgramStatus.approved, approved_at=now - timedelta(days=1)),
            Program(student_id=sid, title="پیش‌نویس", program_type=ProgramType.workout,
                    status=ProgramStatus.draft),
        ])
        db.commit()
    item = auth_client.get("/api/students").json()["items"][0]
    assert item["last_program"]["title"] == "جدید"
    assert auth_client.get(f"/api/students/{sid}").json()["last_program"]["title"] == "جدید"


def test_student_activity_endpoint(auth_client):
    s = create(auth_client)
    r = auth_client.get(f"/api/students/{s['id']}/activity")
    assert r.status_code == 200 and r.json()[0]["action"] == "student.created"


def test_name_sort_uses_persian_alphabet(auth_client):
    for last in ["گلی", "زارع", "پارسا", "چمران", "ژیان", "بهرامی"]:
        create(auth_client, first_name="الف", last_name=last)
    r = auth_client.get("/api/students?sort=name&order=asc")
    assert [n.split(" ", 1)[1] for n in names(r)] == ["بهرامی", "پارسا", "چمران", "زارع", "ژیان", "گلی"]
