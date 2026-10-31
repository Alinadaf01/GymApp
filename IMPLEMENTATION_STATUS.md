# IMPLEMENTATION_STATUS

## نقشه اجرایی

| فاز | محتوا | وضعیت |
|---|---|---|
| ۱ | اسکلت Monorepo، Backend/Frontend، Docker Compose، PostgreSQL، Alembic، Env، Health check، README | ✅ انجام و تست‌شده |
| ۲ | حساب تک‌مربی (bootstrap CLI، Argon2id)، Login/Logout با Cookie HttpOnly، Rate limit، Layout/Sidebar، داشبورد | ⏳ بعدی |
| ۳ | CRUD شاگرد، جستجو/فیلتر/مرتب‌سازی، پرونده با تب‌ها، آرشیو، Activity Log | — |
| ۴ | برنامه‌ها (تمرینی/غذایی/مکمل/ویتامین)، جلسات و حرکات، Duplicate، تأیید، PDF با Playwright، نسخه‌بندی PDF | — |
| ۵ | ربات تلگرام (Webhook + secret، محدودیت User ID)، worker صوت با job در DB، FFmpeg، Faster-Whisper، Parser فارسی، فرهنگ لغت | — |
| ۶ | عکس پیشرفت (خصوصی، حذف EXIF)، مقایسه دو تاریخ، اندازه‌ها و نمودار | — |
| ۷ | استقرار VPS/Vercel، SSL، تست امنیت، بکاپ رمزگذاری‌شده خارج از VPS و تست Restore، مستندات نهایی | — |

---

## فاز ۱ — اسکلت و زیرساخت (۱۴۰۵/۰۸/۰۹)

### چه چیزی ساخته شد
- **Backend (FastAPI)**: ساختار ماژولار طبق بخش ۱۸ سند؛ تنظیمات فقط از Environment (`app/config.py`) با بررسی اجباری `APP_SECRET_KEY` در Production؛ CORS فقط برای `FRONTEND_URL`؛ مستندات OpenAPI در Production غیرفعال.
- **Health check**: `/api/health` (liveness) و `/api/health/ready` (اتصال دیتابیس، 503 بدون افشای جزئیات).
- **مدل داده کامل** (۱۵ جدول بخش ۱۳) با SQLAlchemy 2: شناسه UUID، timestamp با timezone و اتصال در UTC، تاریخ‌های تقویمی `DATE`، enumها به‌صورت VARCHAR + CHECK، ایندکس نام/موبایل/وضعیت، موبایل غیر unique.
  - `programs.student_id` و `generated_pdfs` با `ON DELETE RESTRICT` تا برنامه/PDF تأییدشده با حذف شاگرد پاک نشود (حذف شاگرد soft/archive خواهد بود).
  - فیلدهای عددی حرکت همه nullable (قانون «حدس ممنوع»).
- **Alembic**: migration اولیه؛ URL از `DATABASE_URL` خوانده می‌شود (در `alembic.ini` هاردکد نیست).
- **Frontend (Next.js 16.4.3 + Tailwind 4 + TypeScript)**: `lang="fa" dir="rtl"`، فونت Vazirmatn محلی (بدون CDN)، توکن‌های رنگ، ابزار تاریخ شمسی و ارقام فارسی، صفحه اولیه با وضعیت سرور/دیتابیس (متن + نماد، نه فقط رنگ).
- **زیرساخت**: `Dockerfile` مشترک (کاربر غیر root، FFmpeg)، `docker-compose.yml` (db، migrate، api، nginx؛ فقط nginx پورت عمومی دارد؛ متغیرهای ضروری اجباری)، قالب Nginx (HTTP→HTTPS، ACME، TLS 1.2/1.3، هدرهای امنیتی، محدودیت حجم آپلود، timeout).
- `.env.example` (ریشه و web)، `.gitignore` (شامل `.env` و `data/`)، `README.md`، `PROJECT_SPEC.md`.

### فایل‌ها
`apps/backend/{app/**, migrations/**, tests/**, alembic.ini, requirements*.txt, Dockerfile, pytest.ini}`،
`apps/web/{app/**, components/**, lib/**, tests/**, package.json, tsconfig.json, ...}`،
`docker-compose.yml`، `infra/nginx/default.conf.template`، `.env.example`، `.gitignore`، `README.md`، `IMPLEMENTATION_STATUS.md`، `PROJECT_SPEC.md`.

### Migrationها
- `20261031_679f817aa0bf_initial_schema` — همه ۱۵ جدول. FK دوطرفه `programs.source_voice_record_id → voice_records` پس از ساخت هر دو جدول اضافه می‌شود.

### تست‌های اجراشده و نتیجه
| تست | نتیجه |
|---|---|
| `pytest` (Backend، PostgreSQL 16 واقعی) — ۱۳ تست: health، readiness و عدم افشای خطا، CORS مجاز/غیرمجاز، وجود همه جداول، عدم drift بین مدل و migration، UTC بودن timestamp، null ماندن ست/تکرار نامشخص، جلوگیری از حذف سخت شاگرد دارای برنامه، غیر unique بودن موبایل، رد enum نامعتبر، الزام Secret در Production | ✅ ۱۳/۱۳ |
| `alembic upgrade head` → `downgrade base` → `upgrade head` و `alembic check` | ✅ |
| Frontend `npm test` (تاریخ شمسی، ارقام فارسی، تبدیل UTC به وقت تهران) | ✅ ۴/۴ |
| `npm run typecheck`، `npm run lint`، `npm run build` | ✅ |
| تست مرورگر (Playwright/Chromium) با Backend و Frontend در حال اجرا: `dir=rtl`، فونت Vazirmatn، اتصال به `/api/health/ready`، نبود اسکرول افقی در عرض ۳۹۰ و ۱۲۸۰ | ✅ |
| `docker compose config` (با مقادیر نمونه) | ✅ |

### ناقص / تست‌نشده
- **Docker build و اجرای Compose** و **پیکربندی Nginx** در این محیط تست نشدند (Docker daemon و nginx در دسترس نبودند). باید روی VPS با `docker compose up` و `nginx -t` بررسی شوند.
- رنگ‌های برند موقت‌اند؛ باید از سربرگ رسمی Basharnia استخراج و تأیید شوند (بخش ۲۲). املای فارسی نام «Basharnia» نیز تأیید نشده و فعلاً لاتین نمایش داده می‌شود.
- shadcn/ui هنوز اضافه نشده؛ همراه با فرم‌ها و Layout در فاز ۲ اضافه می‌شود.
- سرویس‌های `bot` و `worker` در Compose در فاز ۵ اضافه می‌شوند.

### تصمیم‌های فنی قابل توجه
- `exercises.reps` از نوع متن است (نه عدد) تا مقادیری مثل «۱۲-۱۰-۸» یا «تا ناتوانی» بدون تغییر معنا ثبت شوند؛ `sets` عددی است.
- `voice_records` ستون‌های `attempts` و `telegram_chat_id` علاوه بر سند دارد تا job صوتی با Restart قابل retry باشد.
- `telegram_conversations.telegram_user_id` یکتا است (یک مکالمه فعال برای هر کاربر).

### گام بعدی
فاز ۲: ساخت حساب مدیر با CLI، احراز هویت با Session/Cookie HttpOnly، Rate limit ورود، Layout و Sidebar فارسی، داشبورد.
