import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.auth.sessions import now_utc
from app.database import SessionLocal
from app.models import ExerciseDictionaryEntry, GeneratedPdf, Program, Student, TelegramConversation, VoiceRecord
from app.models.enums import ProgramStatus, StudentStatus, VoiceStatus
from app.telegram.client import TelegramError, set_bot
from app.worker import run_once
from tests.telegram_fakes import (
    COACH,
    SECRET,
    FakeBot,
    FakeTranscriber,
    callback_update,
    text_update,
    voice_update,
)

WORKOUT_TEXT = "پرس بالا سینه دمبل چهار ست پانزده تایی، اسکوات چهار ست."


@pytest.fixture()
def bot():
    b = FakeBot()
    set_bot(b)
    yield b
    set_bot(None)


@pytest.fixture()
def transcriber():
    return FakeTranscriber(WORKOUT_TEXT)


@pytest.fixture()
def student():
    with SessionLocal() as db:
        s = Student(first_name="سینا", last_name="کاظمی")
        db.add(s)
        db.add_all([ExerciseDictionaryEntry(canonical_name="پرس بالا سینه دمبل", aliases=[]),
                    ExerciseDictionaryEntry(canonical_name="اسکوات", aliases=["اسکات"])])
        db.commit()
        return s


def send(client, update, secret=SECRET):
    headers = {"X-Telegram-Bot-Api-Secret-Token": secret} if secret else {}
    return client.post("/api/telegram/webhook", json=update, headers=headers)


def conversation():
    with SessionLocal() as db:
        return db.scalar(select(TelegramConversation).where(TelegramConversation.telegram_user_id == COACH))


def voices():
    with SessionLocal() as db:
        return db.scalars(select(VoiceRecord).order_by(VoiceRecord.created_at)).all()


def work(bot, transcriber):
    assert run_once(bot, transcriber) is True


def to_voice(client, bot, student, ptype="workout", session_button="جلسه اول"):
    send(client, text_update("/start"))
    send(client, callback_update(bot.callback(student.first_name)))
    send(client, callback_update(f"ty:{ptype}"))
    if ptype == "workout":
        send(client, callback_update(bot.callback(session_button)))
    send(client, voice_update())


# ---- security ---------------------------------------------------------------------------


def test_webhook_requires_secret(client, bot):
    assert send(client, text_update("/start"), secret=None).status_code == 401
    assert send(client, text_update("/start"), secret="wrong").status_code == 401
    assert bot.sent == []


def test_unauthorized_user_rejected(client, bot, student):
    r = send(client, text_update("/start", user_id=999))
    assert r.status_code == 200
    assert "فقط برای مربی" in bot.last["text"]
    assert conversation() is None  # no state for strangers
    send(client, callback_update(f"st:{student.id}", user_id=999))
    assert bot.answers[-1][1] and "فقط برای مربی" in bot.answers[-1][1]


def test_group_chat_rejected_even_for_coach(client, bot):
    send(client, text_update("/start", chat_type="group"))
    assert bot.sent == [] and conversation() is None


def test_start_without_students(client, bot):
    send(client, text_update("/start"))
    assert "شاگرد فعالی" in bot.last["text"]


# ---- full workout flow ---------------------------------------------------------------


def test_full_workout_flow(client, bot, transcriber, student):
    to_voice(client, bot, student)
    (v,) = voices()
    assert v.processing_status == VoiceStatus.received and v.session_title == "جلسه اول"
    assert conversation().state == "processing"
    assert "در حال تبدیل" in bot.last["text"]

    work(bot, transcriber)
    (v,) = voices()
    assert v.processing_status == VoiceStatus.awaiting_review
    assert v.transcript_raw == WORKOUT_TEXT
    assert v.audio_path is None and v.deleted_at is not None  # temp audio removed
    prompt = transcriber.prompts[0]  # vocabulary hint is on by default
    assert prompt.endswith("پلانک، سه ست، یک دقیقه.") and "پرس بالا سینه دمبل" in prompt
    review = bot.last
    assert "پرس بالا سینه دمبل" in review["text"] and "۴ ست" in review["text"]
    assert "تعداد تکرار گفته نشده" in review["text"]  # squat reps not guessed
    assert conversation().state == "reviewing"
    with SessionLocal() as db:
        assert db.scalars(select(Program)).all() == []  # nothing saved before approval

    ok = bot.callback("تأیید", review)
    send(client, callback_update(ok))
    with SessionLocal() as db:
        (p,) = db.scalars(select(Program)).all()
        assert p.status == ProgramStatus.draft and p.source_voice_record_id == v.id
        assert len(p.sessions) == 1 and p.sessions[0].title == "جلسه اول"
        squat = p.sessions[0].exercises[1]
        assert (squat.name, squat.sets, squat.reps) == ("اسکوات", 4, None)
        assert squat.raw_text
    # double tap on approve: no duplicate
    send(client, callback_update(ok))
    assert "قبلاً" in bot.last["text"]
    with SessionLocal() as db:
        assert len(db.scalars(select(Program)).one().sessions) == 1

    # second session
    added_msg = bot.sent[-2]
    send(client, callback_update(bot.callback("جلسه بعد", added_msg)))
    send(client, callback_update(bot.callback("جلسه دوم")))
    send(client, voice_update(file_id="VOICE2"))
    transcriber.text = "اسکوات چهار ست دوازده تایی"
    work(bot, transcriber)
    send(client, callback_update(bot.callback("تأیید")))
    finish = bot.callback("پایان")
    send(client, callback_update(finish))
    with SessionLocal() as db:
        p = db.scalars(select(Program)).one()
        assert p.status == ProgramStatus.approved and p.approved_at is not None
        assert [s.title for s in p.sessions] == ["جلسه اول", "جلسه دوم"]
        assert len(db.scalars(select(GeneratedPdf)).all()) == 1
    assert len(bot.documents) == 1 and bot.documents[0]["filename"].endswith(".pdf")
    assert conversation().state == "idle"
    # double tap on finish: no second PDF
    send(client, callback_update(finish))
    assert len(bot.documents) == 1 and "قبلاً" in bot.last["text"]


def test_conversation_state_survives_restart(client, bot, student):
    send(client, text_update("/start"))
    send(client, callback_update(bot.callback(student.first_name)))
    send(client, callback_update("ty:workout"))
    # Simulate a process restart: a brand-new bot instance, state comes from the DB
    set_bot(FakeBot())
    from app.telegram import client as tc
    new_bot = tc.get_bot()
    send(client, text_update("سینه و پشت بازو"))  # typed session title
    c = conversation()
    assert c.state == "awaiting_voice" and c.payload["session_title"] == "سینه و پشت بازو"
    assert c.payload["student_id"] == str(student.id)
    assert "سینه و پشت بازو" in new_bot.last["text"]


def test_text_correction_keeps_raw_transcript(client, bot, transcriber, student):
    to_voice(client, bot, student)
    work(bot, transcriber)
    send(client, callback_update(bot.callback("اصلاح متنی")))
    assert conversation().state == "correcting" and "<code>" in bot.last["text"]
    send(client, text_update("اسکوات سه ست ده تایی"))
    (v,) = voices()
    assert v.transcript_raw == WORKOUT_TEXT and v.corrected_text == "اسکوات سه ست ده تایی"
    assert "متن اصلاح‌شده" in bot.last["text"]
    send(client, callback_update(bot.callback("تأیید")))
    with SessionLocal() as db:
        (ex,) = db.scalars(select(Program)).one().sessions[0].exercises
        assert (ex.name, ex.sets, ex.reps) == ("اسکوات", 3, "10")


def test_rerecord_and_cancel(client, bot, transcriber, student):
    to_voice(client, bot, student)
    work(bot, transcriber)
    send(client, callback_update(bot.callback("ارسال دوباره")))
    assert voices()[0].processing_status == VoiceStatus.cancelled
    assert conversation().state == "awaiting_voice"
    send(client, voice_update(file_id="VOICE2"))
    assert voices()[1].processing_status == VoiceStatus.received
    send(client, text_update("/cancel"))
    assert voices()[1].processing_status == VoiceStatus.cancelled
    assert conversation().state == "idle" and "لغو شد" in bot.last["text"]
    # a cancelled job is never processed
    assert run_once(bot, transcriber) is False


def test_cancel_while_processing_drops_result(client, bot, transcriber, student):
    to_voice(client, bot, student)
    with SessionLocal() as db:
        from app.services.voice_jobs import claim_next, process
        voice = claim_next(db)
        send(client, text_update("/cancel"))  # coach cancels while the worker runs
        before = len(bot.sent)
        process(db, voice, bot, transcriber)
    assert voices()[0].processing_status == VoiceStatus.cancelled
    assert len(bot.sent) == before  # no review sent for a cancelled voice


def test_review_in_panel_creates_draft(client, bot, transcriber, student):
    to_voice(client, bot, student)
    work(bot, transcriber)
    send(client, callback_update(bot.callback("بازبینی در پنل")))
    with SessionLocal() as db:
        p = db.scalars(select(Program)).one()
        assert p.status == ProgramStatus.draft and len(p.sessions[0].exercises) == 2
    url = bot.callback("پنل")
    assert url == f"http://localhost:3000/programs/{p.id}/edit"
    assert voices()[0].processing_status == VoiceStatus.approved


def test_nutrition_flow_approves_and_sends_pdf(client, bot, student):
    to_voice(client, bot, student, ptype="nutrition")
    work(bot, FakeTranscriber("صبحانه ساعت هشت دو عدد تخم مرغ، ناهار برنج و مرغ"))
    assert "صبحانه" in bot.last["text"] and "۰۸:۰۰" in bot.last["text"]
    send(client, callback_update(bot.callback("تأیید")))
    with SessionLocal() as db:
        p = db.scalars(select(Program)).one()
        assert p.status == ProgramStatus.approved and [m.title for m in p.meals] == ["صبحانه", "ناهار"]
    assert len(bot.documents) == 1


def test_supplement_flow(client, bot, student):
    to_voice(client, bot, student, ptype="vitamin")
    work(bot, FakeTranscriber("ویتامین دی هزار واحد بعد از ناهار"))
    send(client, callback_update(bot.callback("تأیید")))
    with SessionLocal() as db:
        p = db.scalars(select(Program)).one()
        assert p.program_type.value == "vitamin" and p.supplements[0].amount_text == "۱۰۰۰ واحد"


def test_unparseable_text_cannot_be_approved(client, bot, student):
    to_voice(client, bot, student)
    work(bot, FakeTranscriber("."))
    send(client, callback_update(bot.callback("تأیید")))
    assert "هیچ حرکتی" in bot.last["text"]
    with SessionLocal() as db:
        assert db.scalars(select(Program)).all() == []


# ---- input validation ------------------------------------------------------------------


def test_voice_before_start_is_refused(client, bot):
    send(client, voice_update())
    assert "/start" in bot.last["text"] and voices() == []


def test_too_long_voice_rejected(client, bot, student):
    send(client, text_update("/start"))
    send(client, callback_update(bot.callback(student.first_name)))
    send(client, callback_update("ty:nutrition"))
    send(client, voice_update(duration=3600))
    assert "طولانی" in bot.last["text"] and voices() == []


def test_student_search_by_text(client, bot, student):
    send(client, text_update("/start"))
    send(client, text_update("کاظمی"))
    assert ("سینا کاظمی", f"st:{student.id}") in bot.buttons()
    send(client, text_update("ناشناس"))
    assert "پیدا نشد" in bot.last["text"]


def test_archived_student_not_selectable(client, bot, student):
    with SessionLocal() as db:
        db.get(Student, student.id).status = StudentStatus.archived
        db.commit()
    send(client, text_update("/start"))
    send(client, callback_update(f"st:{student.id}"))
    assert "در دسترس نیست" in bot.last["text"]


def test_malformed_callback_is_harmless(client, bot):
    send(client, text_update("/start"))
    r = send(client, callback_update("ok:not-a-uuid"))
    assert r.status_code == 200 and "نامعتبر" in bot.last["text"]


# ---- worker robustness --------------------------------------------------------------------


def test_download_failure_retries_then_fails(client, bot, transcriber, student):
    to_voice(client, bot, student)
    bot.download_error = TelegramError("network")
    for _ in range(3):
        work(bot, transcriber)
    (v,) = voices()
    assert v.processing_status == VoiceStatus.failed and v.attempts == 3
    assert "ناموفق" in bot.last["text"]
    retry = bot.callback("تلاش دوباره")
    bot.download_error = None
    send(client, callback_update(retry))
    assert voices()[0].processing_status == VoiceStatus.queued
    work(bot, transcriber)
    assert voices()[0].processing_status == VoiceStatus.awaiting_review


def test_whisper_error_is_retried(client, bot, student):
    to_voice(client, bot, student)
    t = FakeTranscriber(WORKOUT_TEXT)
    t.error = RuntimeError("model crashed")
    work(bot, t)
    assert voices()[0].processing_status == VoiceStatus.queued
    t.error = None
    work(bot, t)
    assert voices()[0].processing_status == VoiceStatus.awaiting_review


def test_silence_fails_without_retry(client, bot, student):
    to_voice(client, bot, student)
    work(bot, FakeTranscriber("   "))
    assert voices()[0].processing_status == VoiceStatus.failed
    assert "گفتاری" in bot.last["text"]
    assert all("تلاش دوباره" not in t for t, _ in bot.buttons())


def test_stale_job_is_recovered_after_crash(client, bot, transcriber, student):
    to_voice(client, bot, student)
    with SessionLocal() as db:
        v = db.scalars(select(VoiceRecord)).one()
        v.processing_status = VoiceStatus.transcribing  # worker died mid-job
        v.processing_started_at = now_utc() - timedelta(hours=1)
        v.attempts = 1
        db.commit()
    work(bot, transcriber)
    assert voices()[0].processing_status == VoiceStatus.awaiting_review


def test_recent_in_progress_job_is_not_stolen(client, bot, transcriber, student):
    to_voice(client, bot, student)
    with SessionLocal() as db:
        v = db.scalars(select(VoiceRecord)).one()
        v.processing_status = VoiceStatus.transcribing
        v.processing_started_at = now_utc()
        db.commit()
    assert run_once(bot, transcriber) is False


def test_html_in_transcript_is_escaped(client, bot, student):
    to_voice(client, bot, student)
    work(bot, FakeTranscriber("<b>اسکوات</b> چهار ست ده تایی"))
    assert "<b>اسکوات</b>" not in bot.last["text"].replace("<b>جلسه اول</b>", "")
    assert "&lt;b&gt;" in bot.last["text"]
