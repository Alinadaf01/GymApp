import uuid

import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.models import ActivityLog, Exercise, Program


@pytest.fixture()
def student(auth_client):
    return auth_client.post("/api/students", json={"first_name": "علی", "last_name": "رضایی"}).json()


WORKOUT = {
    "title": "برنامه ماه اول",
    "program_type": "workout",
    "start_date": "2026-10-23",
    "notes": "گرم کردن ۱۰ دقیقه",
    "sessions": [
        {
            "title": "سینه و پشت بازو",
            "exercises": [
                {"name": "پرس بالا سینه دمبل", "sets": 4, "reps": "15"},
                {"name": "پرس سینه دستگاه", "sets": 3, "reps": "12", "weight_value": 40, "weight_unit": "kg",
                 "rest_seconds": 60},
            ],
        },
        {"title": "پا", "notes": "کنترل‌شده", "exercises": [{"name": "اسکوات", "sets": 4}]},
    ],
}


def create(client, student, body=None):
    r = client.post(f"/api/students/{student['id']}/programs", json=body or WORKOUT)
    assert r.status_code == 201, r.text
    return r.json()


def actions():
    with SessionLocal() as s:
        return [a.action for a in s.scalars(select(ActivityLog).order_by(ActivityLog.created_at))]


def test_requires_auth(client):
    pid = uuid.uuid4()
    assert client.get(f"/api/programs/{pid}").status_code == 401
    assert client.get("/api/programs").status_code == 401
    assert client.get(f"/api/pdfs/{pid}/download").status_code == 401


def test_create_workout_as_draft_with_order_and_nulls(auth_client, student):
    p = create(auth_client, student)
    assert p["status"] == "draft" and p["approved_at"] is None
    assert p["period_number"] == 1
    assert [s["title"] for s in p["sessions"]] == ["سینه و پشت بازو", "پا"]
    ex = p["sessions"][0]["exercises"]
    assert [e["sort_order"] for e in ex] == [0, 1]
    assert ex[0]["weight_value"] is None and ex[0]["rest_seconds"] is None  # no guessing
    squat = p["sessions"][1]["exercises"][0]
    assert squat["sets"] == 4 and squat["reps"] is None
    assert "program.created" in actions()


def test_period_number_auto_increments_per_type(auth_client, student):
    create(auth_client, student)
    assert create(auth_client, student)["period_number"] == 2
    meal = {"title": "رژیم", "program_type": "nutrition", "meals": [{"title": "صبحانه", "content": "تخم‌مرغ"}]}
    assert create(auth_client, student, meal)["period_number"] == 1
    r = auth_client.get(f"/api/students/{student['id']}/programs/next-period?type=workout")
    assert r.json() == {"period_number": 3}


def test_content_must_match_type(auth_client, student):
    body = {"title": "x", "program_type": "nutrition", "sessions": [{"title": "s", "exercises": []}]}
    r = auth_client.post(f"/api/students/{student['id']}/programs", json=body)
    assert r.status_code == 422


@pytest.mark.parametrize(
    "patch",
    [
        {"title": " "},
        {"start_date": "2026-10-10", "end_date": "2026-10-01"},
        {"sessions": [{"title": "s", "exercises": [{"name": "x", "sets": 0}]}]},
        {"sessions": [{"title": "s", "exercises": [{"name": "x", "rest_seconds": -1}]}]},
        {"sessions": [{"title": "s", "exercises": [{"name": ""}]}]},
    ],
)
def test_validation(auth_client, student, patch):
    r = auth_client.post(f"/api/students/{student['id']}/programs", json={**WORKOUT, **patch})
    assert r.status_code == 422


def test_cannot_create_for_archived_student(auth_client, student):
    auth_client.delete(f"/api/students/{student['id']}")
    r = auth_client.post(f"/api/students/{student['id']}/programs", json=WORKOUT)
    assert r.status_code == 409


def test_put_replaces_content(auth_client, student):
    p = create(auth_client, student)
    body = {k: v for k, v in WORKOUT.items() if k != "program_type"}
    body["sessions"] = [{"title": "فقط پا", "exercises": [{"name": "پرس پا", "sets": 5, "reps": "10"}]}]
    r = auth_client.put(f"/api/programs/{p['id']}", json=body)
    assert r.status_code == 200
    out = r.json()
    assert len(out["sessions"]) == 1 and out["sessions"][0]["exercises"][0]["name"] == "پرس پا"
    with SessionLocal() as s:
        assert s.scalar(select(Exercise).where(Exercise.name == "اسکوات")) is None  # orphans removed


def test_approve_flow_and_idempotency(auth_client, student):
    p = create(auth_client, student)
    r1 = auth_client.post(f"/api/programs/{p['id']}/approve")
    assert r1.status_code == 200 and r1.json()["status"] == "approved"
    r2 = auth_client.post(f"/api/programs/{p['id']}/approve")
    assert r2.json()["approved_at"] == r1.json()["approved_at"]
    assert actions().count("program.approved") == 1


def test_approve_requires_content(auth_client, student):
    empty = create(auth_client, student, {"title": "خالی", "program_type": "workout"})
    assert auth_client.post(f"/api/programs/{empty['id']}/approve").status_code == 422
    no_ex = create(auth_client, student, {"title": "x", "program_type": "workout",
                                          "sessions": [{"title": "s", "exercises": []}]})
    r = auth_client.post(f"/api/programs/{no_ex['id']}/approve")
    assert r.status_code == 422 and "حرکت" in r.json()["detail"]


def test_duplicate_keeps_source_untouched(auth_client, student):
    p = create(auth_client, student)
    auth_client.post(f"/api/programs/{p['id']}/approve")
    before = auth_client.get(f"/api/programs/{p['id']}").json()
    r = auth_client.post(f"/api/programs/{p['id']}/duplicate")
    assert r.status_code == 201
    copy = r.json()
    assert copy["id"] != p["id"] and copy["status"] == "draft"
    assert copy["period_number"] == 2 and copy["start_date"] is None and copy["approved_at"] is None
    assert [e["name"] for e in copy["sessions"][0]["exercises"]] == ["پرس بالا سینه دمبل", "پرس سینه دستگاه"]
    src_ids = {e["id"] for s in before["sessions"] for e in s["exercises"]}
    copy_ids = {e["id"] for s in copy["sessions"] for e in s["exercises"]}
    assert src_ids.isdisjoint(copy_ids)
    # edit the copy; source must not change
    body = {k: v for k, v in WORKOUT.items() if k != "program_type"}
    body["sessions"][0]["exercises"][0]["sets"] = 5
    auth_client.put(f"/api/programs/{copy['id']}", json=body)
    after = auth_client.get(f"/api/programs/{p['id']}").json()
    assert after["sessions"] == before["sessions"] and after["updated_at"] == before["updated_at"]


def test_archive_locks_editing(auth_client, student):
    p = create(auth_client, student)
    assert auth_client.post(f"/api/programs/{p['id']}/archive").json()["status"] == "archived"
    body = {k: v for k, v in WORKOUT.items() if k != "program_type"}
    assert auth_client.put(f"/api/programs/{p['id']}", json=body).status_code == 409
    assert auth_client.post(f"/api/programs/{p['id']}/approve").status_code == 409
    sid = p["sessions"][0]["id"]
    assert auth_client.post(f"/api/sessions/{sid}/exercises", json={"name": "x"}).status_code == 409


def test_only_drafts_can_be_deleted(auth_client, student):
    d = create(auth_client, student)
    assert auth_client.delete(f"/api/programs/{d['id']}").status_code == 204
    assert auth_client.get(f"/api/programs/{d['id']}").status_code == 404
    a = create(auth_client, student)
    auth_client.post(f"/api/programs/{a['id']}/approve")
    assert auth_client.delete(f"/api/programs/{a['id']}").status_code == 409


def test_new_program_does_not_touch_previous(auth_client, student):
    first = create(auth_client, student)
    auth_client.post(f"/api/programs/{first['id']}/approve")
    snapshot = auth_client.get(f"/api/programs/{first['id']}").json()
    create(auth_client, student)
    assert auth_client.get(f"/api/programs/{first['id']}").json() == snapshot


def test_editing_approved_logs_and_bumps_updated_at(auth_client, student):
    p = create(auth_client, student)
    approved = auth_client.post(f"/api/programs/{p['id']}/approve").json()
    body = {k: v for k, v in WORKOUT.items() if k != "program_type"}
    body["title"] = "عنوان جدید"
    out = auth_client.put(f"/api/programs/{p['id']}", json=body).json()
    assert out["status"] == "approved" and out["updated_at"] > approved["updated_at"]
    assert "program.updated" in actions()


def test_draft_edits_are_not_logged(auth_client, student):
    p = create(auth_client, student)
    body = {k: v for k, v in WORKOUT.items() if k != "program_type"}
    auth_client.put(f"/api/programs/{p['id']}", json=body)
    assert "program.updated" not in actions()


# ---- granular endpoints ---------------------------------------------------------------


def test_granular_session_and_exercise_endpoints(auth_client, student):
    p = create(auth_client, student)
    pid = p["id"]
    r = auth_client.post(f"/api/programs/{pid}/sessions", json={"title": "سرشانه", "sort_order": 0})
    assert r.status_code == 201
    titles = [s["title"] for s in auth_client.get(f"/api/programs/{pid}/sessions").json()]
    assert titles == ["سرشانه", "سینه و پشت بازو", "پا"]
    sid = r.json()["id"]

    ex = auth_client.post(f"/api/sessions/{sid}/exercises", json={"name": "نشر از جانب", "sets": 3}).json()
    ex2 = auth_client.post(f"/api/sessions/{sid}/exercises",
                           json={"name": "پرس سرشانه", "sort_order": 0}).json()
    s = auth_client.get(f"/api/programs/{pid}/sessions").json()[0]
    assert [e["name"] for e in s["exercises"]] == ["پرس سرشانه", "نشر از جانب"]

    r = auth_client.put(f"/api/exercises/{ex['id']}", json={"name": "نشر از جانب", "sets": 4, "reps": "۱۲"})
    assert r.json()["sets"] == 4 and r.json()["reps"] == "12"
    assert auth_client.delete(f"/api/exercises/{ex2['id']}").status_code == 204
    s = auth_client.get(f"/api/programs/{pid}/sessions").json()[0]
    assert [(e["name"], e["sort_order"]) for e in s["exercises"]] == [("نشر از جانب", 0)]

    r = auth_client.put(f"/api/sessions/{sid}", json={"title": "سرشانه و شکم", "sort_order": 2})
    assert [x["title"] for x in auth_client.get(f"/api/programs/{pid}/sessions").json()] == [
        "سینه و پشت بازو", "پا", "سرشانه و شکم"]
    assert auth_client.delete(f"/api/sessions/{sid}").status_code == 204
    assert len(auth_client.get(f"/api/programs/{pid}/sessions").json()) == 2


def test_granular_nutrition_and_supplements(auth_client, student):
    n = create(auth_client, student, {"title": "رژیم", "program_type": "nutrition"})
    m = auth_client.post(f"/api/programs/{n['id']}/nutrition",
                         json={"title": "صبحانه", "time_text": "08:00", "content": "تخم‌مرغ و نان"})
    assert m.status_code == 201
    r = auth_client.put(f"/api/nutrition/{m.json()['id']}", json={"title": "صبحانه", "content": "جو دوسر"})
    assert r.json()["content"] == "جو دوسر" and r.json()["time_text"] is None
    # wrong type
    assert auth_client.post(f"/api/programs/{n['id']}/supplements", json={"name": "x"}).status_code == 422

    v = create(auth_client, student, {"title": "ویتامین", "program_type": "vitamin"})
    x = auth_client.post(f"/api/programs/{v['id']}/supplements",
                         json={"name": "ویتامین D", "amount_text": "۱ عدد", "timing_text": "بعد از ناهار"})
    assert x.status_code == 201
    assert auth_client.get(f"/api/programs/{v['id']}/supplements").json()[0]["name"] == "ویتامین D"
    assert auth_client.delete(f"/api/supplements/{x.json()['id']}").status_code == 204


# ---- list ------------------------------------------------------------------------------


def test_program_list_filters(auth_client, student):
    other = auth_client.post("/api/students", json={"first_name": "مریم", "last_name": "کریمی"}).json()
    a = create(auth_client, student)
    auth_client.post(f"/api/programs/{a['id']}/approve")
    create(auth_client, other, {"title": "رژیم مریم", "program_type": "nutrition",
                                "meals": [{"title": "ناهار", "content": "برنج"}]})
    c = create(auth_client, student)
    auth_client.post(f"/api/programs/{c['id']}/archive")

    def titles(qs):
        r = auth_client.get(f"/api/programs?{qs}")
        assert r.status_code == 200
        return sorted(i["title"] for i in r.json()["items"])

    assert len(titles("")) == 2  # archived hidden
    assert titles("status=archived") == ["برنامه ماه اول"]
    assert titles("type=nutrition") == ["رژیم مریم"]
    assert titles("q=کریمی") == ["رژیم مریم"]       # by student name
    assert titles("q=رژیم") == ["رژیم مریم"]        # by title
    assert titles(f"student_id={student['id']}&status=all") == ["برنامه ماه اول", "برنامه ماه اول"]
    assert titles("status=approved") == ["برنامه ماه اول"]


def test_free_text_keeps_persian_digits_but_unifies_letters(auth_client, student):
    body = {"title": "برنامه دوره ۲", "program_type": "workout",
            "sessions": [{"title": "جلسه ۱ — پا", "exercises": [{"name": "اسكوات ۳ ثانيه مكث", "reps": "۱۰"}]}]}
    p = create(auth_client, student, body)
    assert p["title"] == "برنامه دوره ۲"
    assert p["sessions"][0]["title"] == "جلسه ۱ — پا"
    ex = p["sessions"][0]["exercises"][0]
    assert ex["name"] == "اسکوات ۳ ثانیه مکث"  # Arabic kaf/yeh unified, digits kept
    assert ex["reps"] == "10"  # structured field: ASCII digits

    def titles(q):
        return [i["title"] for i in auth_client.get("/api/programs", params={"q": q}).json()["items"]]

    assert titles("دوره ۲") == ["برنامه دوره ۲"]
    assert titles("دوره 2") == ["برنامه دوره ۲"]
