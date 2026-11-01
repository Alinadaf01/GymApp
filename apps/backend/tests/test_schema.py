import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.models import Exercise, Program, Student, WorkoutSession
from app.models.enums import ProgramStatus, ProgramType

EXPECTED_TABLES = {
    "users", "students", "programs", "workout_sessions", "exercises", "nutrition_meals",
    "supplements", "progress_photos", "body_measurements", "voice_records", "generated_pdfs",
    "exercise_dictionary", "activity_logs", "settings", "telegram_conversations",
}


def test_all_spec_tables_exist(db):
    tables = set(inspect(db.get_bind()).get_table_names())
    assert EXPECTED_TABLES <= tables


def test_models_match_migrations():
    """Alembic autogenerate must detect no drift between models and migrations."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from app.database import engine
    from app.database.base import Base

    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata)
    assert diff == []


def test_timestamps_are_utc(db):
    s = Student(first_name="تست", last_name="شاگرد")
    db.add(s)
    db.flush()
    db.refresh(s)
    assert s.created_at.utcoffset().total_seconds() == 0
    assert db.execute(text("SHOW timezone")).scalar().lower() == "utc"


def test_exercise_unspecified_values_stay_null(db):
    s = Student(first_name="علی", last_name="احمدی")
    db.add(s)
    db.flush()
    p = Program(student_id=s.id, title="برنامه", program_type=ProgramType.workout)
    sess = WorkoutSession(title="جلسه اول", sort_order=1)
    sess.exercises.append(Exercise(name="اسکوات", sets=4, sort_order=1))
    p.sessions.append(sess)
    db.add(p)
    db.flush()
    db.refresh(p)
    ex = p.sessions[0].exercises[0]
    assert ex.sets == 4
    assert ex.reps is None and ex.weight_value is None and ex.rest_seconds is None
    assert p.status == ProgramStatus.draft


def test_student_with_programs_cannot_be_hard_deleted(db):
    s = Student(first_name="رضا", last_name="کریمی")
    db.add(s)
    db.flush()
    db.add(Program(student_id=s.id, title="برنامه", program_type=ProgramType.nutrition))
    db.flush()
    with pytest.raises(IntegrityError):
        db.execute(text("DELETE FROM students WHERE id = :id"), {"id": s.id})
        db.flush()


def test_phone_is_not_unique(db):
    db.add_all([
        Student(first_name="الف", last_name="ب", phone="09120000000"),
        Student(first_name="ج", last_name="د", phone="09120000000"),
    ])
    db.flush()


def test_invalid_enum_rejected_by_db(db):
    with pytest.raises(IntegrityError):
        db.execute(text("INSERT INTO students (id, first_name, last_name, status) "
                        "VALUES (gen_random_uuid(), 'x', 'y', 'bogus')"))
