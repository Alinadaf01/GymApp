from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import ActivityLog, Program, Student
from app.models.enums import ProgramStatus, StudentStatus
from app.schemas.dashboard import ActivityOut, DashboardSummary, ProgramBrief, StudentBrief
from app.services.dates import current_jalali_month_bounds

router = APIRouter(prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(get_current_user)])

# A program counts as "registered" once the coach has approved it (drafts are not final)
REGISTERED = (ProgramStatus.approved, ProgramStatus.archived)


def _full_name(s: Student) -> str:
    return f"{s.first_name} {s.last_name}"


@router.get("/summary", response_model=DashboardSummary)
def summary(db: Session = Depends(get_db)) -> DashboardSummary:
    not_archived = Student.status != StudentStatus.archived
    month_start, month_end = current_jalali_month_bounds()

    total_students = db.scalar(select(func.count()).select_from(Student).where(not_archived))
    active_students = db.scalar(
        select(func.count()).select_from(Student).where(Student.status == StudentStatus.active)
    )
    total_programs = db.scalar(select(func.count()).select_from(Program).where(Program.status.in_(REGISTERED)))
    programs_this_month = db.scalar(
        select(func.count())
        .select_from(Program)
        .where(
            Program.status.in_(REGISTERED),
            Program.approved_at >= month_start,
            Program.approved_at < month_end,
        )
    )

    students = db.scalars(select(Student).where(not_archived).order_by(Student.created_at.desc()).limit(5)).all()
    programs = db.execute(
        select(Program, Student)
        .join(Student, Student.id == Program.student_id)
        .order_by(Program.updated_at.desc())
        .limit(5)
    ).all()

    return DashboardSummary(
        total_students=total_students,
        active_students=active_students,
        total_programs=total_programs,
        programs_this_month=programs_this_month,
        recent_students=[
            StudentBrief(
                id=s.id,
                full_name=_full_name(s),
                phone=s.phone,
                status=s.status,
                current_weight_kg=s.current_weight_kg,
                start_date=s.start_date,
                created_at=s.created_at,
            )
            for s in students
        ],
        recent_programs=[
            ProgramBrief(
                id=p.id,
                title=p.title,
                program_type=p.program_type,
                status=p.status,
                student_id=s.id,
                student_name=_full_name(s),
                approved_at=p.approved_at,
                created_at=p.created_at,
            )
            for p, s in programs
        ],
    )


@router.get("/recent-activity", response_model=list[ActivityOut])
def recent_activity(limit: int = Query(default=10, ge=1, le=50), db: Session = Depends(get_db)) -> list[ActivityOut]:
    rows = db.execute(
        select(ActivityLog, Student)
        .outerjoin(Student, Student.id == ActivityLog.student_id)
        .order_by(ActivityLog.created_at.desc())
        .limit(limit)
    ).all()
    return [
        ActivityOut(
            id=a.id,
            action=a.action,
            entity_type=a.entity_type,
            entity_id=a.entity_id,
            student_id=a.student_id,
            student_name=_full_name(s) if s else None,
            meta=a.meta,
            created_at=a.created_at,
        )
        for a, s in rows
    ]
