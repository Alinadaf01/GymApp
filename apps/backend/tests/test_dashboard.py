from datetime import UTC, datetime, timedelta

from app.database import SessionLocal
from app.models import Program, Student
from app.models.enums import ProgramStatus, ProgramType, StudentStatus
from app.services.activity import log_activity
from app.services.dates import current_jalali_month_bounds


def test_dashboard_requires_auth(client):
    assert client.get("/api/dashboard/summary").status_code == 401
    assert client.get("/api/dashboard/recent-activity").status_code == 401


def test_summary_empty(auth_client):
    r = auth_client.get("/api/dashboard/summary")
    assert r.status_code == 200
    assert r.json() == {
        "total_students": 0,
        "active_students": 0,
        "total_programs": 0,
        "programs_this_month": 0,
        "recent_students": [],
        "recent_programs": [],
    }


def test_summary_counts(auth_client):
    month_start, _ = current_jalali_month_bounds()
    with SessionLocal() as s:
        a = Student(first_name="علی", last_name="رضایی", status=StudentStatus.active)
        b = Student(first_name="سارا", last_name="محمدی", status=StudentStatus.inactive)
        c = Student(first_name="آرش", last_name="کاظمی", status=StudentStatus.archived)
        s.add_all([a, b, c])
        s.flush()
        s.add_all([
            Program(student_id=a.id, title="ماه اول", program_type=ProgramType.workout,
                    status=ProgramStatus.approved, approved_at=month_start + timedelta(hours=1)),
            Program(student_id=a.id, title="قدیمی", program_type=ProgramType.nutrition,
                    status=ProgramStatus.archived, approved_at=month_start - timedelta(days=40)),
            Program(student_id=b.id, title="پیش‌نویس", program_type=ProgramType.workout,
                    status=ProgramStatus.draft),
        ])
        s.commit()

    d = auth_client.get("/api/dashboard/summary").json()
    assert d["total_students"] == 2  # archived excluded
    assert d["active_students"] == 1
    assert d["total_programs"] == 2  # drafts excluded
    assert d["programs_this_month"] == 1
    assert {x["full_name"] for x in d["recent_students"]} == {"علی رضایی", "سارا محمدی"}
    assert len(d["recent_programs"]) == 3


def test_recent_activity(auth_client, admin):
    with SessionLocal() as s:
        st = Student(first_name="مینا", last_name="کریمی")
        s.add(st)
        s.flush()
        log_activity(s, action="student.created", entity_type="student", entity_id=st.id,
                     student_id=st.id, actor_user_id=admin.id)
        s.commit()
    r = auth_client.get("/api/dashboard/recent-activity")
    assert r.status_code == 200
    item = r.json()[0]
    assert item["action"] == "student.created" and item["student_name"] == "مینا کریمی"


def test_jalali_month_bounds():
    # 2026-10-31 12:00 UTC is 9 Aban 1405 in Tehran; Aban 1405 = 2026-10-23 .. 2026-11-21
    start, end = current_jalali_month_bounds(datetime(2026, 10, 31, 12, tzinfo=UTC))
    assert start == datetime(2026, 10, 22, 20, 30, tzinfo=UTC)  # 2026-10-23 00:00 Tehran (+03:30)
    assert end == datetime(2026, 11, 21, 20, 30, tzinfo=UTC)
    # Esfand -> next year's Farvardin
    start, end = current_jalali_month_bounds(datetime(2027, 3, 1, tzinfo=UTC))
    assert end == datetime(2027, 3, 20, 20, 30, tzinfo=UTC)
