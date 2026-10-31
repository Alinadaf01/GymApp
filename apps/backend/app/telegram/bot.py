"""Coach Telegram bot: conversation flow (spec §7).

/start -> student -> program type -> (workout: session) -> voice -> processing
(worker) -> review -> approve / correct / re-record / review in panel / cancel.
Nothing becomes a final program before the coach's explicit approval.
"""
import logging
import uuid

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.sessions import now_utc
from app.config import get_settings
from app.models import (
    Exercise,
    GeneratedPdf,
    NutritionMeal,
    Program,
    Student,
    Supplement,
    VoiceRecord,
    WorkoutSession,
)
from app.models.enums import ProgramStatus, ProgramType, StudentStatus, VoiceStatus
from app.parsers.service import (
    load_dictionary,
    meals_from_payload,
    parse_text,
    session_from_payload,
    supplements_from_payload,
)
from app.pdf.service import generate_pdf
from app.schemas.program import MealWrite, SessionWrite, SupplementWrite
from app.services.activity import log_activity
from app.services.programs import content_problem, load_program, next_period_number, touch
from app.services.students import apply_search, full_name
from app.storage import files
from app.telegram import conversation as cv
from app.telegram.client import Bot, TelegramError, keyboard
from app.telegram.render import TYPE_LABELS, e, fa, review_text

log = logging.getLogger("app.telegram")

ORDINALS = ["اول", "دوم", "سوم", "چهارم", "پنجم", "ششم", "هفتم", "هشتم"]
DENIED = "⛔️ این ربات فقط برای مربی مجموعه است."
HELP = (
    "راهنمای ربات مربی:\n"
    "۱. /start را بزنید و شاگرد را انتخاب کنید (یا نامش را بنویسید).\n"
    "۲. نوع برنامه و برای برنامه تمرینی، جلسه را انتخاب کنید.\n"
    "۳. ویس برنامه را بفرستید. متن و ساختار پیشنهادی را می‌بینید.\n"
    "۴. تأیید، اصلاح متنی، ارسال دوباره یا بازبینی در پنل را انتخاب کنید.\n"
    "تا تأیید شما چیزی نهایی نمی‌شود.\n\n"
    "/start شروع · /cancel لغو · /help راهنما"
)
CANCEL_ROW = [("❌ لغو", "cx")]


def panel_url(path: str) -> str:
    return get_settings().frontend_url.rstrip("/") + path


# ---- entry point ---------------------------------------------------------------------


def handle_update(db: Session, update: dict, bot: Bot) -> None:
    s = get_settings()
    msg = update.get("message")
    cb = update.get("callback_query")
    source = msg or cb or {}
    user = source.get("from") or {}
    chat = (msg or {}).get("chat") or ((cb or {}).get("message") or {}).get("chat") or {}
    chat_id = chat.get("id")

    allowed = s.telegram_allowed_user_id
    # Authorization is by numeric user id only (username is not authentication)
    if allowed is None or user.get("id") != allowed or chat.get("type") not in (None, "private"):
        log.warning("telegram: rejected update from user_id=%s", user.get("id"))
        if cb:
            bot.answer_callback(cb["id"], DENIED)
        elif chat_id and chat.get("type") == "private":
            bot.send_message(chat_id, DENIED)
        return

    conv = cv.get_conversation(db, user["id"])
    if cb:
        bot.answer_callback(cb["id"])
        _on_callback(db, bot, conv, chat_id, cb.get("data") or "")
    elif msg:
        _on_message(db, bot, conv, chat_id, msg)
    db.commit()


# ---- messages ------------------------------------------------------------------------------


def _on_message(db, bot, conv, chat_id, msg):
    text = (msg.get("text") or "").strip()
    if text.startswith("/start"):
        return _start(db, bot, conv, chat_id)
    if text.startswith("/cancel"):
        return _cancel(db, bot, conv, chat_id)
    if text.startswith("/help"):
        return bot.send_message(chat_id, HELP)

    audio = msg.get("voice") or msg.get("audio")
    doc = msg.get("document")
    if not audio and doc and str(doc.get("mime_type", "")).startswith("audio/"):
        audio = doc
    if audio:
        return _on_voice(db, bot, conv, chat_id, audio)

    if not text:
        return bot.send_message(chat_id, "فقط متن یا ویس پشتیبانی می‌شود. /help")
    if conv.state == cv.CHOOSING_STUDENT:
        return _search_students(db, bot, conv, chat_id, text)
    if conv.state == cv.CHOOSING_SESSION:
        return _choose_session(bot, conv, chat_id, text[:200])
    if conv.state in (cv.REVIEWING, cv.CORRECTING):
        return _apply_correction(db, bot, conv, chat_id, text)
    if conv.state == cv.AWAITING_VOICE:
        return bot.send_message(chat_id, "منتظر ویس هستم 🎙 (برای لغو /cancel)")
    if conv.state == cv.PROCESSING:
        return bot.send_message(chat_id, "⏳ ویس قبلی در حال پردازش است…")
    bot.send_message(chat_id, "برای ثبت برنامه /start را بزنید. /help")


def _student_keyboard(students: list[Student]) -> dict:
    rows = [[(full_name(s), f"st:{s.id}")] for s in students]
    return keyboard(rows + [CANCEL_ROW])


def _start(db, bot, conv, chat_id):
    _cleanup_pending_voice(db, conv)
    cv.reset(conv)
    cv.set_state(conv, cv.CHOOSING_STUDENT)
    recent = db.scalars(
        select(Student).where(Student.status == StudentStatus.active).order_by(Student.updated_at.desc()).limit(8)
    ).all()
    if not recent:
        return bot.send_message(chat_id, "هنوز شاگرد فعالی در پنل ثبت نشده است. ابتدا از پنل شاگرد اضافه کنید.")
    bot.send_message(chat_id, "👤 شاگرد را انتخاب کنید، یا نام/موبایل او را بنویسید:", _student_keyboard(recent))


def _search_students(db, bot, conv, chat_id, text):
    stmt = apply_search(select(Student).where(Student.status != StudentStatus.archived), text)
    found = db.scalars(stmt.order_by(Student.last_name).limit(8)).all()
    if not found:
        return bot.send_message(chat_id, f"شاگردی با «{e(text)}» پیدا نشد. دوباره بنویسید یا /cancel")
    bot.send_message(chat_id, "نتیجه جستجو:", _student_keyboard(found))


def _choose_session(bot, conv, chat_id, title):
    cv.set_state(conv, cv.AWAITING_VOICE, session_title=title)
    bot.send_message(chat_id, f"🎙 ویس «{e(title)}» را بفرستید.", keyboard([CANCEL_ROW]))


def _on_voice(db, bot, conv, chat_id, audio):
    s = get_settings()
    if conv.state != cv.AWAITING_VOICE or not conv.payload.get("student_id"):
        return bot.send_message(chat_id, "ابتدا با /start شاگرد و نوع برنامه را انتخاب کنید.")
    duration = int(audio.get("duration") or 0)
    if duration > s.audio_max_duration_seconds:
        return bot.send_message(
            chat_id, f"⚠️ ویس طولانی است (حداکثر {fa(s.audio_max_duration_seconds // 60)} دقیقه). آن را کوتاه‌تر بفرستید."
        )
    if (audio.get("file_size") or 0) > 20 * 1024 * 1024:
        return bot.send_message(chat_id, "⚠️ حجم فایل بیش از ۲۰ مگابایت است.")
    voice = VoiceRecord(
        student_id=uuid.UUID(conv.payload["student_id"]),
        program_id=uuid.UUID(conv.payload["program_id"]) if conv.payload.get("program_id") else None,
        telegram_file_id=audio["file_id"],
        telegram_chat_id=chat_id,
        program_type=conv.payload["program_type"],
        session_title=conv.payload.get("session_title"),
        duration_seconds=duration or None,
        processing_status=VoiceStatus.received,
    )
    db.add(voice)
    db.flush()
    cv.set_state(conv, cv.PROCESSING, voice_id=str(voice.id))
    bot.send_message(chat_id, "⏳ ویس دریافت شد و در حال تبدیل به متن است… نتیجه را همین‌جا می‌فرستم.")


def _apply_correction(db, bot, conv, chat_id, text):
    voice = _current_voice(db, conv, lock=True)
    if voice is None or voice.processing_status != VoiceStatus.awaiting_review:
        return bot.send_message(chat_id, "موردی برای اصلاح نیست. /start")
    voice.corrected_text = text[:5000]
    try:
        voice.parsed_payload = parse_text(text, voice.program_type, load_dictionary(db), voice.session_title)
    except Exception:  # parser must never break the conversation
        log.exception("parser failed on correction")
        voice.parsed_payload = None
    cv.set_state(conv, cv.REVIEWING)
    send_review(db, bot, voice)


# ---- callbacks ------------------------------------------------------------------------------------


def _on_callback(db, bot, conv, chat_id, data):
    action, _, arg = data.partition(":")
    handlers = {
        "st": _cb_student, "ty": _cb_type, "se": _cb_session, "ok": _cb_approve, "ed": _cb_edit,
        "re": _cb_rerecord, "pn": _cb_panel, "nx": _cb_next_session, "fin": _cb_finish, "rt": _cb_retry,
        "cx": lambda db, bot, conv, chat_id, arg: _cancel(db, bot, conv, chat_id),
    }
    handler = handlers.get(action)
    if handler is None:
        return
    try:
        handler(db, bot, conv, chat_id, arg)
    except ValueError:  # malformed UUID in callback data
        bot.send_message(chat_id, "درخواست نامعتبر بود. /start")


def _cb_student(db, bot, conv, chat_id, arg):
    student = db.get(Student, uuid.UUID(arg))
    if student is None or student.status == StudentStatus.archived:
        return bot.send_message(chat_id, "این شاگرد در دسترس نیست. /start")
    cv.reset(conv)
    cv.set_state(conv, cv.CHOOSING_TYPE, student_id=str(student.id), student_name=full_name(student))
    bot.send_message(
        chat_id,
        f"👤 {e(full_name(student))}\nنوع برنامه را انتخاب کنید:",
        keyboard([[("🏋️ تمرینی", "ty:workout"), ("🥗 غذایی", "ty:nutrition")],
                  [("💊 مکمل", "ty:supplement"), ("🍊 ویتامین", "ty:vitamin")], CANCEL_ROW]),
    )


def _session_keyboard(start: int) -> dict:
    labels = [f"جلسه {ORDINALS[i]}" for i in range(start, min(start + 4, len(ORDINALS)))]
    rows = [[(lbl, f"se:{start + i}") for i, lbl in enumerate(labels[j:j + 2], j)] for j in (0, 2)]
    return keyboard([r for r in rows if r] + [CANCEL_ROW])


def _cb_type(db, bot, conv, chat_id, arg):
    if arg not in TYPE_LABELS or not conv.payload.get("student_id"):
        return bot.send_message(chat_id, "ابتدا شاگرد را انتخاب کنید. /start")
    if arg == "workout":
        cv.set_state(conv, cv.CHOOSING_SESSION, program_type=arg)
        return bot.send_message(
            chat_id, "جلسه را انتخاب کنید، یا عنوان جلسه را بنویسید (مثلاً «سینه و پشت بازو»):",
            _session_keyboard(conv.payload.get("sessions_added", 0)),
        )
    cv.set_state(conv, cv.AWAITING_VOICE, program_type=arg, session_title=None)
    bot.send_message(chat_id, f"🎙 ویس برنامه {TYPE_LABELS[arg]} را بفرستید.", keyboard([CANCEL_ROW]))


def _cb_session(db, bot, conv, chat_id, arg):
    if conv.payload.get("program_type") != "workout":
        return bot.send_message(chat_id, "ابتدا نوع برنامه را انتخاب کنید. /start")
    idx = int(arg) if arg.isdigit() else 0
    _choose_session(bot, conv, chat_id, f"جلسه {ORDINALS[min(idx, len(ORDINALS) - 1)]}")


def _cb_edit(db, bot, conv, chat_id, arg):
    voice = _voice_for_action(db, conv, arg)
    if voice is None or voice.processing_status != VoiceStatus.awaiting_review:
        return bot.send_message(chat_id, "این مورد دیگر قابل اصلاح نیست.")
    cv.set_state(conv, cv.CORRECTING)
    current = voice.corrected_text or voice.transcript_raw or ""
    bot.send_message(
        chat_id,
        "✏️ متن اصلاح‌شده را کامل بفرستید (می‌توانید متن زیر را کپی و ویرایش کنید):\n\n"
        f"<code>{e(current)}</code>",
    )


def _cb_rerecord(db, bot, conv, chat_id, arg):
    voice = _voice_for_action(db, conv, arg)
    if voice and voice.processing_status in (VoiceStatus.awaiting_review, VoiceStatus.failed):
        _discard_voice(voice)
    cv.set_state(conv, cv.AWAITING_VOICE, voice_id=None)
    bot.send_message(chat_id, "🎙 ویس جدید را بفرستید.", keyboard([CANCEL_ROW]))


def _cb_retry(db, bot, conv, chat_id, arg):
    voice = _voice_for_action(db, conv, arg)
    if voice is None or voice.processing_status != VoiceStatus.failed:
        return bot.send_message(chat_id, "موردی برای تلاش دوباره نیست.")
    voice.processing_status = VoiceStatus.queued
    voice.attempts = 0
    voice.error_message = None
    cv.set_state(conv, cv.PROCESSING, voice_id=str(voice.id))
    bot.send_message(chat_id, "🔁 دوباره در صف پردازش قرار گرفت…")


def _cb_next_session(db, bot, conv, chat_id, arg):
    if not conv.payload.get("program_id"):
        return bot.send_message(chat_id, "برنامه‌ای در جریان نیست. /start")
    cv.set_state(conv, cv.CHOOSING_SESSION, session_title=None, voice_id=None)
    bot.send_message(
        chat_id, "جلسه بعد را انتخاب کنید یا عنوانش را بنویسید:",
        _session_keyboard(conv.payload.get("sessions_added", 0)),
    )


# ---- approval ------------------------------------------------------------------------------------


class ContentError(ValueError):
    pass


def _validated_session(voice: VoiceRecord) -> dict:
    payload = voice.parsed_payload
    if not payload or not payload.get("exercises"):
        raise ContentError("هیچ حرکتی تشخیص داده نشده است. متن اصلاح‌شده بفرستید یا در پنل بازبینی کنید.")
    fallback = voice.session_title or "جلسه"
    data = session_from_payload(payload, fallback)
    if voice.session_title and not payload.get("session_title"):
        data["title"] = voice.session_title
    try:
        return SessionWrite.model_validate(data).model_dump()
    except ValidationError as ex:
        raise ContentError("بخشی از مقادیر معتبر نیست؛ در پنل بازبینی کنید.") from ex


def _validated_items(voice: VoiceRecord) -> tuple[list[dict], list[dict]]:
    payload = voice.parsed_payload or {}
    try:
        if voice.program_type == "nutrition":
            meals = [MealWrite.model_validate(m).model_dump() for m in meals_from_payload(payload)]
            if not meals:
                raise ContentError("وعده‌ای تشخیص داده نشد. متن اصلاح‌شده بفرستید.")
            return meals, []
        items = [SupplementWrite.model_validate(x).model_dump() for x in supplements_from_payload(payload)]
        if not items:
            raise ContentError("قلمی تشخیص داده نشد. متن اصلاح‌شده بفرستید.")
        return [], items
    except ValidationError as ex:
        raise ContentError("بخشی از مقادیر معتبر نیست؛ در پنل بازبینی کنید.") from ex


def _new_program(db, voice: VoiceRecord, user_id=None) -> Program:
    ptype = ProgramType(voice.program_type)
    period = next_period_number(db, voice.student_id, ptype)
    program = Program(
        student_id=voice.student_id,
        title=f"برنامه {TYPE_LABELS[ptype.value]} دوره {fa(period)}",
        program_type=ptype,
        period_number=period,
        status=ProgramStatus.draft,
        source_voice_record_id=voice.id,
    )
    db.add(program)
    db.flush()
    log_activity(db, action="program.created", entity_type="program", entity_id=program.id,
                 student_id=program.student_id, meta={"source": "telegram"})
    return program


def _append_session(db, conv, voice: VoiceRecord, session: dict) -> Program:
    program = None
    if conv.payload.get("program_id"):
        program = load_program(db, uuid.UUID(conv.payload["program_id"]), for_update=True)
        if program.status != ProgramStatus.draft:
            program = None
    if program is None:
        program = _new_program(db, voice)
        program = load_program(db, program.id, for_update=True)
    ws = WorkoutSession(title=session["title"], notes=session["notes"], sort_order=len(program.sessions))
    for i, ex in enumerate(session["exercises"]):
        ws.exercises.append(Exercise(**ex, sort_order=i))
    program.sessions.append(ws)
    touch(program)
    voice.program_id = program.id
    return program


def _approve_voice(voice: VoiceRecord) -> None:
    voice.processing_status = VoiceStatus.approved
    voice.processed_at = voice.processed_at or now_utc()


def _cb_approve(db, bot, conv, chat_id, arg):
    voice = _voice_for_action(db, conv, arg)
    # Idempotency: only a voice still awaiting review can be approved (row is locked)
    if voice is None or voice.processing_status != VoiceStatus.awaiting_review:
        return bot.send_message(chat_id, "ℹ️ این مورد قبلاً ثبت یا لغو شده است.")
    try:
        if voice.program_type == "workout":
            session = _validated_session(voice)
            program = _append_session(db, conv, voice, session)
            _approve_voice(voice)
            added = conv.payload.get("sessions_added", 0) + 1
            cv.set_state(conv, cv.SESSION_ADDED, program_id=str(program.id), sessions_added=added, voice_id=None)
            return bot.send_message(
                chat_id,
                f"✅ «{e(session['title'])}» به پیش‌نویس «{e(program.title)}» اضافه شد "
                f"({fa(added)} جلسه).\nبرنامه هنوز پیش‌نویس است تا «پایان» را بزنید.",
                keyboard([[("➕ جلسه بعد", "nx"), ("🏁 پایان: تأیید و PDF", f"fin:{program.id}")],
                          [("🖥 مشاهده در پنل", f"url:{panel_url(f'/programs/{program.id}/edit')}")]]),
            )
        meals, items = _validated_items(voice)
    except ContentError as ex:
        return bot.send_message(chat_id, f"⚠️ {e(ex)}")

    program = _new_program(db, voice)
    program = load_program(db, program.id, for_update=True)
    for i, m in enumerate(meals):
        program.meals.append(NutritionMeal(**m, sort_order=i))
    for i, x in enumerate(items):
        program.supplements.append(Supplement(**x, sort_order=i))
    voice.program_id = program.id
    _approve_voice(voice)
    db.flush()
    _finalize_and_send(db, bot, conv, chat_id, program)


def _finalize_and_send(db, bot, conv, chat_id, program: Program):
    """Approve the program, make a PDF and send it. Commits."""
    problem = content_problem(program)
    if problem:
        return bot.send_message(chat_id, f"⚠️ {e(problem)}")
    if program.status == ProgramStatus.draft:
        program.status = ProgramStatus.approved
        program.approved_at = now_utc()
        log_activity(db, action="program.approved", entity_type="program", entity_id=program.id,
                     student_id=program.student_id, meta={"source": "telegram"})
    cv.reset(conv)
    db.flush()
    try:
        pdf = generate_pdf(db, program, None)
    except Exception:
        log.exception("telegram: PDF generation failed")
        db.commit()
        return bot.send_message(
            chat_id, "✅ برنامه تأیید و ثبت شد، اما ساخت PDF ناموفق بود. از پنل «ساخت PDF» را بزنید.",
            keyboard([[("🖥 باز کردن در پنل", f"url:{panel_url(f'/programs/{program.id}')}")]]),
        )
    db.commit()
    _send_pdf(db, bot, chat_id, program, pdf)


def _send_pdf(db, bot, chat_id, program: Program, pdf: GeneratedPdf):
    student = db.get(Student, program.student_id)
    try:
        data = files.resolve(pdf.file_path).read_bytes()
        bot.send_document(
            chat_id, f"{full_name(student)} - {program.title}.pdf", data,
            caption=f"✅ {program.title} — {full_name(student)} (نسخه {fa(pdf.version)})",
        )
    except (TelegramError, OSError):
        log.exception("telegram: sending PDF failed")
        bot.send_message(chat_id, "✅ برنامه ثبت شد. ارسال PDF ناموفق بود؛ از پنل دانلود کنید.",
                         keyboard([[("🖥 باز کردن در پنل", f"url:{panel_url(f'/programs/{program.id}')}")]]))


def _cb_finish(db, bot, conv, chat_id, arg):
    program_id = uuid.UUID(arg)
    if conv.payload.get("program_id") != str(program_id):
        # Already finished (double tap) or from an old conversation
        return bot.send_message(chat_id, "ℹ️ این برنامه قبلاً نهایی شده است.")
    program = load_program(db, program_id, for_update=True)
    if program.status == ProgramStatus.archived:
        return bot.send_message(chat_id, "این برنامه بایگانی شده است.")
    _finalize_and_send(db, bot, conv, chat_id, program)


def _cb_panel(db, bot, conv, chat_id, arg):
    """Move the parsed content into a draft and continue editing in the panel."""
    voice = _voice_for_action(db, conv, arg)
    if voice is None or voice.processing_status != VoiceStatus.awaiting_review:
        return bot.send_message(chat_id, "ℹ️ این مورد قبلاً ثبت یا لغو شده است.")
    payload = voice.parsed_payload or {}
    if voice.program_type == "workout":
        data = session_from_payload(payload, voice.session_title or "جلسه")
        try:
            session = SessionWrite.model_validate(data).model_dump()
        except ValidationError:
            session = {"title": data["title"][:200] or "جلسه", "notes": None, "exercises": []}
        program = _append_session(db, conv, voice, session)
    else:
        program = _new_program(db, voice)
        try:
            meals, items = _validated_items(voice)
        except ContentError:
            meals, items = [], []
        program = load_program(db, program.id, for_update=True)
        for i, m in enumerate(meals):
            program.meals.append(NutritionMeal(**m, sort_order=i))
        for i, x in enumerate(items):
            program.supplements.append(Supplement(**x, sort_order=i))
        voice.program_id = program.id
    _approve_voice(voice)  # content moved to a DRAFT program; finalized in the panel
    cv.reset(conv)
    bot.send_message(
        chat_id,
        f"🖥 پیش‌نویس «{e(program.title)}» ساخته شد. در پنل بازبینی و تأیید کنید.",
        keyboard([[("باز کردن در پنل", f"url:{panel_url(f'/programs/{program.id}/edit')}")]]),
    )


# ---- cancel / helpers --------------------------------------------------------------------------------


def _cancel(db, bot, conv, chat_id):
    _cleanup_pending_voice(db, conv)
    program_id = conv.payload.get("program_id")
    cv.reset(conv)
    text = "❌ لغو شد."
    markup = None
    if program_id:
        text += "\nجلسه‌های تأییدشده در یک پیش‌نویس باقی مانده‌اند و از پنل قابل ادامه‌اند."
        markup = keyboard([[("باز کردن پیش‌نویس", f"url:{panel_url(f'/programs/{program_id}/edit')}")]])
    bot.send_message(chat_id, text + "\nبرای شروع دوباره /start", markup)


def _discard_voice(voice: VoiceRecord) -> None:
    voice.processing_status = VoiceStatus.cancelled
    _delete_audio(voice)


def _delete_audio(voice: VoiceRecord) -> None:
    if voice.audio_path:
        files.delete(voice.audio_path)
        voice.audio_path = None
        voice.deleted_at = now_utc()


def _cleanup_pending_voice(db, conv) -> None:
    voice = _current_voice(db, conv, lock=True)
    if voice and voice.processing_status not in (VoiceStatus.approved, VoiceStatus.cancelled):
        _discard_voice(voice)


def _current_voice(db, conv, lock=False) -> VoiceRecord | None:
    vid = conv.payload.get("voice_id")
    if not vid:
        return None
    stmt = select(VoiceRecord).where(VoiceRecord.id == uuid.UUID(vid))
    return db.scalar(stmt.with_for_update() if lock else stmt)


def _voice_for_action(db, conv, arg) -> VoiceRecord | None:
    return db.scalar(select(VoiceRecord).where(VoiceRecord.id == uuid.UUID(arg)).with_for_update())


# ---- shared with the worker ------------------------------------------------------------------------


def review_keyboard(voice_id) -> dict:
    return keyboard([
        [("✅ تأیید", f"ok:{voice_id}"), ("✏️ اصلاح متنی", f"ed:{voice_id}")],
        [("🎙 ارسال دوباره", f"re:{voice_id}"), ("🖥 بازبینی در پنل", f"pn:{voice_id}")],
        [("❌ لغو", "cx")],
    ])


def send_review(db, bot: Bot, voice: VoiceRecord) -> None:
    student = db.get(Student, voice.student_id)
    text = review_text(full_name(student), voice.program_type, voice.session_title, voice.transcript_raw,
                       voice.corrected_text, voice.parsed_payload)
    bot.send_message(voice.telegram_chat_id, text, review_keyboard(voice.id))


def send_failure(bot: Bot, voice: VoiceRecord, message: str, retry: bool) -> None:
    rows = [[("🔁 تلاش دوباره", f"rt:{voice.id}"), ("🎙 ارسال دوباره", f"re:{voice.id}")]] if retry else \
        [[("🎙 ارسال دوباره", f"re:{voice.id}")]]
    bot.send_message(voice.telegram_chat_id, f"⚠️ {e(message)}", keyboard(rows + [CANCEL_ROW]))
