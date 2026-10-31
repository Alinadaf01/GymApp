import enum

from sqlalchemy import Enum


def str_enum(enum_cls: type[enum.Enum], name: str) -> Enum:
    """Store enums as VARCHAR + CHECK (no native PG enum) to keep migrations simple."""
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
    )


class StudentStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    archived = "archived"


class Gender(str, enum.Enum):
    male = "male"
    female = "female"
    other = "other"


class ProgramType(str, enum.Enum):
    workout = "workout"
    nutrition = "nutrition"
    supplement = "supplement"
    vitamin = "vitamin"


class ProgramStatus(str, enum.Enum):
    draft = "draft"
    approved = "approved"
    archived = "archived"


class ExecutionType(str, enum.Enum):
    reps = "reps"
    time = "time"
    distance = "distance"
    combined = "combined"
    free = "free"


class PhotoView(str, enum.Enum):
    front = "front"
    back = "back"
    side = "side"


class VoiceStatus(str, enum.Enum):
    received = "received"
    downloading = "downloading"
    queued = "queued"
    transcribing = "transcribing"
    parsing = "parsing"
    awaiting_review = "awaiting_review"
    approved = "approved"
    cancelled = "cancelled"
    failed = "failed"
