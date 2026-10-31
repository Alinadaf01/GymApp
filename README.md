# Basharnia Coach CRM

CRM سبک تک‌مربی برای مجموعه ورزشی Basharnia: پرونده دائمی شاگرد، ثبت برنامه با ویس فارسی تلگرام
(Faster-Whisper محلی + Parser فارسی) و PDF فارسی آماده چاپ.

- سند مرجع نیازمندی‌ها: [`PROJECT_SPEC.md`](PROJECT_SPEC.md)
- وضعیت پیاده‌سازی و نتایج تست: [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md)
- **استقرار روی VPS و Vercel:** [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)
- **بکاپ و بازیابی:** [`docs/BACKUP_RESTORE.md`](docs/BACKUP_RESTORE.md)
- **امنیت:** [`docs/SECURITY.md`](docs/SECURITY.md)
- **گزارش تست‌های پذیرش:** [`docs/ACCEPTANCE.md`](docs/ACCEPTANCE.md)

## ساختار

```text
apps/web/       پنل Next.js (TypeScript, Tailwind) — میزبانی روی Vercel
apps/backend/   FastAPI + SQLAlchemy 2 + Alembic — اجرا روی VPS
infra/nginx/    قالب Nginx (TLS، reverse proxy، هدرهای امنیتی، rate limit)
infra/scripts/  آماده‌سازی و ایمن‌سازی VPS، گواهی SSL
infra/backup/   بکاپ رمزگذاری‌شده، بازیابی، تمرین بازیابی
infra/systemd/  تایمر بکاپ روزانه
infra/tests/    تست‌های nginx، Stack کامل Docker و بکاپ/بازیابی
docs/           راهنماهای استقرار، بکاپ، امنیت و گزارش پذیرش
docker-compose.yml  پشته VPS: db، migrate، api، worker، nginx
```

## اجرای محلی (توسعه)

پیش‌نیاز: Python 3.12+، Node 22+، PostgreSQL 16.

```bash
# دیتابیس توسعه و تست (یک‌بار)
sudo -u postgres psql -c "CREATE USER basharnia WITH PASSWORD 'devpass' CREATEDB;"
sudo -u postgres psql -c "CREATE DATABASE basharnia_dev OWNER basharnia;"
sudo -u postgres psql -c "CREATE DATABASE basharnia_test OWNER basharnia;"
```

```bash
cd apps/backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
export DATABASE_URL=postgresql+psycopg://basharnia:devpass@localhost:5432/basharnia_dev
alembic upgrade head
python -m app.cli create-admin               # ساخت حساب مربی (یک‌بار؛ رمز پرسیده می‌شود)
uvicorn app.main:app --reload --port 8000    # http://localhost:8000/api/health
python -m pytest                              # از basharnia_test استفاده می‌کند
# تست واقعی Whisper (اختیاری؛ مدل و espeak-ng لازم است):
WHISPER_TEST_MODEL_DIR=./data/models python -m pytest tests/test_whisper_integration.py
```

```bash
cd apps/web
cp .env.example .env.local
npm ci && npm run dev                         # http://localhost:3000
```

رمز `devpass` فقط برای دیتابیس محلی توسعه است و نباید در Production استفاده شود.

تست End-to-End (با API و پنل در حال اجرا):

```bash
cd apps/web
E2E_USERNAME=coach E2E_PASSWORD='...' node e2e/phase2.smoke.mjs
E2E_USERNAME=coach E2E_PASSWORD='...' node e2e/phase3.smoke.mjs   # روی دیتابیس توسعه؛ رکورد تستی می‌سازد
E2E_USERNAME=coach E2E_PASSWORD='...' node e2e/phase4.smoke.mjs   # برنامه‌ها و PDF
E2E_USERNAME=coach E2E_PASSWORD='...' node e2e/phase5.smoke.mjs   # فرهنگ لغت و برنامه از ویس
E2E_USERNAME=coach E2E_PASSWORD='...' node e2e/phase6.smoke.mjs   # عکس پیشرفت، اندازه‌ها، نمودار
E2E_USERNAME=coach E2E_PASSWORD='...' node e2e/mobile-overflow.smoke.mjs   # همه صفحات در عرض ۳۹۰px
```

## ربات تلگرام و تبدیل ویس

معماری: Webhook تلگرام در خود API است (`POST /api/telegram/webhook`). سرویس جداگانه `worker` (همان image با دستور `python -m app.worker`) ویس را دانلود می‌کند، با FFmpeg تبدیل می‌کند، با **Faster-Whisper محلی** به متن تبدیل می‌کند (بدون هیچ API پولی) و با Parser فارسی ساختاردهی می‌کند. صف کارها در PostgreSQL است و با Restart از بین نمی‌رود.

راه‌اندازی (یک‌بار):

1. در تلگرام با [@BotFather](https://t.me/BotFather) ربات بسازید و Token را در `TELEGRAM_BOT_TOKEN` بگذارید.
2. شناسه عددی تلگرام مربی را (مثلاً با ربات @userinfobot) در `TELEGRAM_ALLOWED_USER_ID` بگذارید. Username به‌تنهایی مجوز حساب نمی‌شود.
3. یک Secret تصادفی ۲۴+ کاراکتری در `TELEGRAM_WEBHOOK_SECRET` بگذارید.
4. مدل Whisper را یک‌بار در Volume دائمی دانلود کنید (حدود ۴۶۰ مگابایت برای `small`):

```bash
docker compose run --rm worker python -m app.cli download-whisper-model
```

5. پس از فعال شدن HTTPS روی `API_BASE_URL`، Webhook را ثبت کنید:

```bash
docker compose run --rm api python -m app.cli set-webhook
```

```bash
docker compose run --rm api python -m app.cli webhook-info
```

نکات:
- صوت خام به‌طور پیش‌فرض بلافاصله پس از پردازش حذف می‌شود (`AUDIO_RETAIN_HOURS=0`). متن خام Whisper همیشه در `voice_records` نگه داشته می‌شود.
- `WHISPER_VOCAB_HINT` به‌طور پیش‌فرض خاموش است (توضیح در `IMPLEMENTATION_STATUS.md`، فاز ۵).
- آزمون محلی بدون تلگرام واقعی (فقط توسعه): `scripts/fake_telegram_api.py` و `scripts/e2e_telegram_flow.py`.

## حساب مربی

- فقط یک حساب مدیریتی وجود دارد و رمز پیش‌فرض ندارد.
- ساخت: `python -m app.cli create-admin` (از `ADMIN_USERNAME` و `INITIAL_ADMIN_PASSWORD` یا ورودی تعاملی). بعد از ساخت، `INITIAL_ADMIN_PASSWORD` را از `.env` حذف کنید.
- فراموشی رمز: `python -m app.cli reset-password` (همه نشست‌ها باطل می‌شوند).
- روی VPS: `docker compose run --rm api python -m app.cli create-admin`

## احراز هویت (خلاصه)

- Session سمت سرور در جدول `auth_sessions`؛ Cookie از نوع HttpOnly، `SameSite=Lax` و در Production `Secure` با پیشوند `__Host-`. فقط hash توکن ذخیره می‌شود.
- رمزها با Argon2id هش می‌شوند.
- محدودیت ورود: ۵ تلاش ناموفق برای هر نام کاربری و ۲۰ تلاش برای هر IP در ۱۵ دقیقه (ذخیره در دیتابیس) و یک limit دیگر در Nginx.
- CSRF: درخواست‌های تغییر‌دهنده باید هدر `X-Requested-With: fetch` داشته باشند و Origin، اگر فرستاده شود، باید دامنه پنل باشد.
- پنل و API باید زیر یک دامنه اصلی باشند (مثلاً `coach.example.com` و `api.example.com`) تا Cookie با `SameSite=Lax` کار کند.

## Health check

| مسیر | معنا |
|---|---|
| `GET /api/health` | سرویس بالا است |
| `GET /api/health/ready` | اتصال دیتابیس برقرار است (در خطا 503، بدون افشای جزئیات) |

## استقرار

راهنمای کامل گام‌به‌گام: **[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)** (آماده‌سازی و ایمن‌سازی VPS، `.env`، SSL، اجرای سرویس‌ها، حساب مربی، مدل Whisper و ربات، Vercel، بکاپ و چک‌لیست نهایی).

خلاصه روی VPS (پس از `infra/scripts/setup-vps.sh` و پر کردن `.env`):

```bash
docker compose build && docker compose up -d
```

فایل‌های خصوصی در `STORAGE_HOST_PATH` (پیش‌فرض `/data/basharnia`) ذخیره می‌شوند و کانتینرها با کاربر غیر root (UID `10001`) اجرا می‌شوند؛ اسکریپت آماده‌سازی مجوزها را تنظیم می‌کند.
