import pytest
from sqlalchemy import select

from app import cli
from app.auth.passwords import verify_password
from app.database import SessionLocal
from app.models import User


def test_create_admin_from_env(monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "Coach")
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "a-strong-password")
    cli.main(["create-admin"])
    with SessionLocal() as s:
        user = s.scalar(select(User))
    assert user.username == "coach"
    assert verify_password(user.password_hash, "a-strong-password")


def test_create_admin_only_once(monkeypatch, admin):
    monkeypatch.setenv("ADMIN_USERNAME", "second")
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "a-strong-password")
    with pytest.raises(SystemExit):
        cli.main(["create-admin"])


def test_create_admin_rejects_weak_password(monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "coach")
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "123")
    with pytest.raises(SystemExit):
        cli.main(["create-admin"])
    with SessionLocal() as s:
        assert s.scalar(select(User)) is None


def test_reset_password(monkeypatch, admin):
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "recovered-password")
    cli.main(["reset-password"])
    with SessionLocal() as s:
        assert verify_password(s.scalar(select(User)).password_hash, "recovered-password")


def test_export_voice_eval(capsys, admin, client):
    import json

    from app.models import Program, Student, VoiceRecord
    from app.models.enums import ProgramType, VoiceStatus
    from app.models import WorkoutSession, Exercise

    with SessionLocal() as db:
        s = Student(first_name="علی", last_name="رضایی")
        db.add(s)
        db.flush()
        p = Program(student_id=s.id, title="برنامه", program_type=ProgramType.workout)
        p.sessions.append(WorkoutSession(title="جلسه اول", sort_order=0,
                                         exercises=[Exercise(name="اسکوات", sets=4, reps="12", sort_order=0)]))
        db.add(p)
        db.flush()
        db.add(VoiceRecord(student_id=s.id, program_id=p.id, program_type="workout", session_title="جلسه اول",
                           transcript_raw="اسکوات چار ست", corrected_text="اسکوات چهار ست دوازده تایی",
                           parsed_payload={"exercises": [{"name": "اسکوات", "sets": 4, "reps": None}]},
                           processing_status=VoiceStatus.approved))
        db.commit()
    cli.main(["export-voice-eval"])
    data = json.loads(capsys.readouterr().out)
    (v,) = data["voices"]
    assert data["count"] == 1 and v["transcript_raw"] == "اسکوات چار ست"
    assert v["corrected_text"] == "اسکوات چهار ست دوازده تایی"
    assert v["parsed"]["exercises"][0]["reps"] is None
    assert v["final_program"]["sessions"][0]["exercises"][0]["reps"] == "12"  # ground truth after review
