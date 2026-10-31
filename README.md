# Basharnia Coach CRM

CRM سبک تک‌مربی برای مجموعه ورزشی Basharnia: پرونده دائمی شاگرد، ثبت برنامه با ویس فارسی تلگرام
(Faster-Whisper محلی + Parser فارسی) و PDF فارسی آماده چاپ.

- سند مرجع نیازمندی‌ها: [`PROJECT_SPEC.md`](PROJECT_SPEC.md)
- وضعیت پیاده‌سازی و نتایج تست: [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md)

## ساختار

```text
apps/web/       پنل Next.js (TypeScript, Tailwind) — میزبانی روی Vercel
apps/backend/   FastAPI + SQLAlchemy 2 + Alembic — اجرا روی VPS
infra/nginx/    قالب Nginx (TLS، reverse proxy، هدرهای امنیتی)
infra/scripts/  اسکریپت‌های نصب/بکاپ (فازهای بعد)
docker-compose.yml  پشته VPS: db، migrate، api، nginx
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
```

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

`.env.example` را به `.env` کپی و مقادیر را پر کنید، سپس:

```bash
docker compose up -d --build
```

نکات فعلی:

- فایل‌های خصوصی (تصاویر و بعداً PDF) در `STORAGE_HOST_PATH` (پیش‌فرض `/data/basharnia`) ذخیره می‌شوند. کانتینر API با کاربر غیر root (UID `10001`) اجرا می‌شود، پس:

```bash
sudo mkdir -p /data/basharnia && sudo chown -R 10001:10001 /data/basharnia && sudo chmod 750 /data/basharnia
```

- PDF با Chromium (Playwright) داخل کانتینر API ساخته می‌شود. Chromium هنگام build image نصب می‌شود (`playwright install --with-deps chromium`) و نسخه‌اش با پکیج `playwright` در `requirements.txt` قفل است. در توسعه محلی یک‌بار `python -m playwright install chromium` را اجرا کنید. برای تست‌های PDF، ابزار `pdftotext` (بسته `poppler-utils`) لازم است.
- جستجو به افزونه `pg_trgm` و مرتب‌سازی فارسی به collation `fa-x-icu` نیاز دارد. هر دو در image رسمی `postgres:16` موجودند و migration افزونه را فعال می‌کند.

راهنمای کامل VPS، SSL، Vercel، بکاپ و Restore در فاز ۷ نوشته می‌شود.
