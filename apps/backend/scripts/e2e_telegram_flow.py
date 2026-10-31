"""DEVELOPMENT/TEST ONLY — drive the real webhook + real worker through a
complete coach conversation against scripts/fake_telegram_api.py.

Requires: API on :8000 and worker running with TELEGRAM_API_BASE pointing to
the fake API, TELEGRAM_ALLOWED_USER_ID=111, and an active student in the DB.
"""
import json
import os
import sys
import time
import urllib.request

API = os.environ.get("E2E_API_URL", "http://localhost:8000")
FAKE = os.environ.get("E2E_FAKE_TG", "http://localhost:8081")
SECRET = os.environ["TELEGRAM_WEBHOOK_SECRET"]
COACH = int(os.environ.get("TELEGRAM_ALLOWED_USER_ID", "111"))
STUDENT = os.environ["E2E_STUDENT_NAME"]
uid = 1000


def post(update: dict) -> int:
    global uid
    uid += 1
    update["update_id"] = uid
    req = urllib.request.Request(f"{API}/api/telegram/webhook", data=json.dumps(update).encode(),
                                 headers={"Content-Type": "application/json",
                                          "X-Telegram-Bot-Api-Secret-Token": SECRET})
    return urllib.request.urlopen(req).status


def msg(text=None, voice=None, user=COACH):
    m = {"message_id": uid, "from": {"id": user}, "chat": {"id": user, "type": "private"}}
    if text:
        m["text"] = text
    if voice:
        m["voice"] = voice
    return {"message": m}


def cb(data):
    return {"callback_query": {"id": f"c{uid}", "data": data, "from": {"id": COACH},
                               "message": {"message_id": 1, "chat": {"id": COACH, "type": "private"}}}}


def calls():
    return json.load(urllib.request.urlopen(f"{FAKE}/_calls"))


def messages():
    return [c["data"] for c in calls() if c["method"] == "sendMessage"]


def button(label_part, m=None):
    m = m or messages()[-1]
    for row in (m.get("reply_markup") or {}).get("inline_keyboard", []):
        for b in row:
            if label_part in b["text"]:
                return b.get("callback_data") or b.get("url")
    sys.exit(f"button {label_part!r} not found in: {m.get('text', '')[:200]}")


def wait_for(predicate, timeout=120, what="condition"):
    end = time.time() + timeout
    while time.time() < end:
        if predicate():
            return
        time.sleep(1)
    sys.exit(f"timeout waiting for {what}")


def step(t):
    print(f"✓ {t}", flush=True)


assert post(msg("/start", user=999)) == 200
assert "فقط برای مربی" in messages()[-1]["text"]
step("stranger rejected")

post(msg("/start"))
post(cb(button(STUDENT)))
post(cb("ty:workout"))
post(cb(button("جلسه اول")))
assert "ویس" in messages()[-1]["text"]
post(msg(voice={"file_id": "REAL-VOICE", "duration": 4, "file_size": 9000}))
step("voice accepted, waiting for the worker (real Whisper)…")

wait_for(lambda: "متن ویس" in messages()[-1].get("text", ""), what="review message")
review = messages()[-1]
print("   transcript+structure:\n   " + review["text"].replace("\n", "\n   ")[:700])
assert any(c["method"] == "getFile" for c in calls())
step("worker downloaded the voice, transcribed it locally and sent the review")

post(cb(button("اصلاح متنی", review)))
post(msg("پرس بالا سینه دمبل چهار ست پانزده تایی، اسکوات چهار ست."))
fixed = messages()[-1]
assert "متن اصلاح‌شده" in fixed["text"] and "تعداد تکرار گفته نشده" in fixed["text"]
step("text correction re-parsed (missing reps flagged, not guessed)")

ok = button("تأیید", fixed)
post(cb(ok))
added = messages()[-1]
assert "اضافه شد" in added["text"]
post(cb(ok))
assert "قبلاً" in messages()[-1]["text"]
step("approved once; duplicate approval ignored")

fin = button("پایان", added)
post(cb(fin))
wait_for(lambda: any(c["method"] == "sendDocument" for c in calls()), timeout=60, what="PDF")
doc = [c for c in calls() if c["method"] == "sendDocument"][-1]["data"]
assert doc["is_pdf"] and doc["multipart_bytes"] > 10000
post(cb(fin))
assert sum(c["method"] == "sendDocument" for c in calls()) == 1
step(f"program approved and PDF sent to Telegram ({doc['multipart_bytes']} bytes); double tap ignored")
print("ALL PASSED")
