import io
from datetime import date, timedelta
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import select

from app.database import SessionLocal
from app.models import ActivityLog, ProgressPhoto, Student
from tests.conftest import TEST_STORAGE


def jpeg(w=2400, h=3200, gps=True) -> bytes:
    img = Image.new("RGB", (w, h), (120, 90, 60))
    exif = Image.Exif()
    exif[0x010F] = "PhoneMaker"
    if gps:
        exif[0x8825] = {1: "N", 2: (35.0, 41.0, 0.0), 3: "E", 4: (51.0, 25.0, 0.0)}
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif.tobytes())
    return buf.getvalue()


@pytest.fixture()
def student(auth_client):
    return auth_client.post("/api/students", json={"first_name": "علی", "last_name": "رضایی"}).json()


def upload(client, sid, view="front", day="2026-09-01", consent=True, data=None, name="p.jpg", ctype="image/jpeg"):
    return client.post(f"/api/students/{sid}/photos",
                       files={"file": (name, data or jpeg(), ctype)},
                       data={"view_type": view, "capture_date": day, "consent": str(consent).lower(),
                             "notes": "قبل از شروع"})


def stored(photo_id) -> Path:
    with SessionLocal() as db:
        return Path(TEST_STORAGE) / db.get(ProgressPhoto, photo_id).file_path


# ---- photos -----------------------------------------------------------------------------


def test_photos_require_auth(client):
    import uuid
    assert client.get(f"/api/students/{uuid.uuid4()}/photos").status_code == 401
    assert client.get(f"/api/photos/{uuid.uuid4()}/file").status_code == 401


def test_upload_requires_consent(auth_client, student):
    assert upload(auth_client, student["id"], consent=False).status_code == 422


def test_upload_three_views_private_sanitized(auth_client, student):
    sid = student["id"]
    ids = {}
    for view in ("side", "front", "back"):
        r = upload(auth_client, sid, view=view)
        assert r.status_code == 201, r.text
        ids[view] = r.json()["id"]
    listed = auth_client.get(f"/api/students/{sid}/photos").json()
    assert [p["view_type"] for p in listed] == ["front", "back", "side"]  # stable view order
    p = listed[0]
    assert p["url"] == f"/api/photos/{p['id']}/file" and p["thumb_url"].endswith("?size=thumb")

    path = stored(ids["front"])
    assert path.is_file() and "progress" in str(path) and len(path.stem) >= 40
    assert b"PhoneMaker" not in path.read_bytes()
    with Image.open(path) as im:
        assert max(im.size) == 1600 and not im.getexif()
    thumb = path.with_name(path.stem + ".thumb.jpg")
    with Image.open(thumb) as im:
        assert max(im.size) == 480

    full = auth_client.get(p["url"])
    assert full.status_code == 200 and full.headers["content-type"] == "image/jpeg"
    assert "private" in full.headers["cache-control"]
    small = auth_client.get(p["thumb_url"])
    assert len(small.content) < len(full.content)
    auth_client.cookies.clear()
    assert auth_client.get(p["url"]).status_code == 401


def test_one_photo_per_view_and_date(auth_client, student):
    assert upload(auth_client, student["id"], view="front").status_code == 201
    r = upload(auth_client, student["id"], view="front")
    assert r.status_code == 409 and "روبه‌رو" in r.json()["detail"]
    assert upload(auth_client, student["id"], view="front", day="2026-10-01").status_code == 201


def test_views_are_optional(auth_client, student):
    assert upload(auth_client, student["id"], view="side").status_code == 201
    assert len(auth_client.get(f"/api/students/{student['id']}/photos").json()) == 1


@pytest.mark.parametrize("day", [(date.today() + timedelta(days=1)).isoformat(), "1999-01-01"])
def test_photo_date_validated(auth_client, student, day):
    assert upload(auth_client, student["id"], day=day).status_code == 422


def test_invalid_file_rejected(auth_client, student):
    r = upload(auth_client, student["id"], data=b"not an image", name="x.jpg")
    assert r.status_code == 422
    with SessionLocal() as db:
        assert db.scalars(select(ProgressPhoto)).all() == []


def test_delete_removes_record_and_files(auth_client, student):
    pid = upload(auth_client, student["id"]).json()["id"]
    path = stored(pid)
    thumb = path.with_name(path.stem + ".thumb.jpg")
    assert auth_client.delete(f"/api/photos/{pid}").status_code == 204
    assert not path.exists() and not thumb.exists()
    assert auth_client.get(f"/api/photos/{pid}/file").status_code == 404
    with SessionLocal() as db:
        actions = [a.action for a in db.scalars(select(ActivityLog).order_by(ActivityLog.created_at))]
    assert "photo.uploaded" in actions and "photo.deleted" in actions


def test_archived_student_cannot_get_new_photos(auth_client, student):
    auth_client.delete(f"/api/students/{student['id']}")
    assert upload(auth_client, student["id"]).status_code == 409


# ---- measurements ---------------------------------------------------------------------


def measure(client, sid, **kw):
    return client.post(f"/api/students/{sid}/measurements", json={"measured_at": "2026-09-01", **kw})


def current_weight(sid):
    with SessionLocal() as db:
        return db.get(Student, sid).current_weight_kg


def test_measurement_validation(auth_client, student):
    sid = student["id"]
    assert measure(auth_client, sid).status_code == 422  # nothing measured
    assert measure(auth_client, sid, weight_kg=5).status_code == 422
    assert measure(auth_client, sid, waist_cm=500).status_code == 422
    future = (date.today() + timedelta(days=1)).isoformat()
    assert auth_client.post(f"/api/students/{sid}/measurements",
                            json={"measured_at": future, "weight_kg": 80}).status_code == 422


def test_measurements_crud_sorted_and_only_given_values(auth_client, student):
    sid = student["id"]
    b = measure(auth_client, sid, measured_at="2026-10-01", weight_kg=82.4, waist_cm=90).json()
    a = measure(auth_client, sid, measured_at="2026-09-01", weight_kg=85, arm_cm=36.5, notes="شروع").json()
    rows = auth_client.get(f"/api/students/{sid}/measurements").json()
    assert [r["id"] for r in rows] == [a["id"], b["id"]]  # chronological
    assert rows[1]["arm_cm"] is None and rows[0]["waist_cm"] is None  # nothing invented
    r = auth_client.put(f"/api/measurements/{a['id']}", json={"measured_at": "2026-09-02", "weight_kg": 84.6})
    assert r.status_code == 200 and r.json()["arm_cm"] is None
    assert auth_client.delete(f"/api/measurements/{a['id']}").status_code == 204
    assert len(auth_client.get(f"/api/students/{sid}/measurements").json()) == 1


def test_current_weight_follows_latest_measurement(auth_client, student):
    sid = student["id"]
    auth_client.put(f"/api/students/{sid}", json={"first_name": "علی", "last_name": "رضایی",
                                                  "current_weight_kg": 90})
    old = measure(auth_client, sid, measured_at="2026-08-01", weight_kg=88).json()
    assert float(current_weight(sid)) == 88
    new = measure(auth_client, sid, measured_at="2026-10-01", weight_kg=84).json()
    assert float(current_weight(sid)) == 84
    # an older-dated entry added later does not override the latest
    measure(auth_client, sid, measured_at="2026-09-01", weight_kg=86)
    assert float(current_weight(sid)) == 84
    # a measurement without weight does not touch it
    measure(auth_client, sid, measured_at="2026-10-15", waist_cm=88)
    assert float(current_weight(sid)) == 84
    auth_client.delete(f"/api/measurements/{new['id']}")
    assert float(current_weight(sid)) == 86
    auth_client.put(f"/api/measurements/{old['id']}", json={"measured_at": "2026-10-20", "weight_kg": 83})
    assert float(current_weight(sid)) == 83


def test_deleting_all_measurements_keeps_manual_weight(auth_client, student):
    sid = student["id"]
    m = measure(auth_client, sid, weight_kg=80).json()
    auth_client.delete(f"/api/measurements/{m['id']}")
    assert float(current_weight(sid)) == 80  # no fabricated value, last known kept
