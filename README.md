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
uvicorn app.main:app --reload --port 8000    # http://localhost:8000/api/health
python -m pytest                              # از basharnia_test استفاده می‌کند
```

```bash
cd apps/web
cp .env.example .env.local
npm ci && npm run dev                         # http://localhost:3000
```

رمز `devpass` فقط برای دیتابیس محلی توسعه است و نباید در Production استفاده شود.

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

راهنمای کامل VPS، SSL، Vercel، بکاپ و Restore در فاز ۷ نوشته می‌شود.
