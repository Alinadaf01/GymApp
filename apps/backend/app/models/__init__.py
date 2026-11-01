"""Import all models so Alembic autogenerate sees the full metadata."""
from app.models.auth import AuthSession, LoginAttempt
from app.models.misc import ActivityLog, ExerciseDictionaryEntry, GeneratedPdf, Setting, TelegramConversation
from app.models.program import Exercise, NutritionMeal, Program, Supplement, WorkoutSession
from app.models.progress import BodyMeasurement, ProgressPhoto
from app.models.student import Student
from app.models.user import User
from app.models.voice import VoiceRecord

__all__ = [
    "ActivityLog",
    "AuthSession",
    "LoginAttempt",
    "BodyMeasurement",
    "Exercise",
    "ExerciseDictionaryEntry",
    "GeneratedPdf",
    "NutritionMeal",
    "Program",
    "ProgressPhoto",
    "Setting",
    "Student",
    "Supplement",
    "TelegramConversation",
    "User",
    "VoiceRecord",
    "WorkoutSession",
]
