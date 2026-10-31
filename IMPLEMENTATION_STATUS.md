# IMPLEMENTATION_STATUS

## نقشه اجرایی

| فاز | محتوا | وضعیت |
|---|---|---|
| ۱ | اسکلت Monorepo، Backend/Frontend، Docker Compose، PostgreSQL، Alembic، Env، Health check، README | ✅ انجام و تست‌شده |
| ۲ | حساب تک‌مربی (bootstrap CLI، Argon2id)، Login/Logout با Cookie HttpOnly، Rate limit، Layout/Sidebar، داشبورد | ✅ انجام و تست‌شده |
| ۳ | CRUD شاگرد، جستجو/فیلتر/مرتب‌سازی، پرونده با تب‌ها، آرشیو، Activity Log | ⏳ بعدی |
| ۴ | برنامه‌ها (تمرینی/غذایی/مکمل/ویتامین)، جلسات و حرکات، Duplicate، تأیید، PDF با Playwright، نسخه‌بندی PDF | — |
| ۵ | ربات تلگرام (Webhook + secret، محدودیت User ID)، worker صوت با job در DB، FFmpeg، Faster-Whisper، Parser فارسی، فرهنگ لغت | — |
| ۶ | عکس پیشرفت (خصوصی، حذف EXIF)، مقایسه دو تاریخ، اندازه‌ها و نمودار | — |
| ۷ | استقرار VPS/Vercel، SSL، تست امنیت، بکاپ رمزگذاری‌شده خارج از VPS و تست Restore، مستندات نهایی | — |

---

## فاز ۲ — احراز هویت و پنل (۱۴۰۵/۰۸/۰۹)

### چه چیزی ساخته شد
- **حساب تک‌مربی**: `python -m app.cli create-admin` فقط یک‌بار اجرا می‌شود و اگر حسابی موجود باشد رد می‌شود. نام کاربری و رمز از env یا ورودی تعاملی (بدون نمایش رمز) خوانده می‌شوند و رمز پیش‌فرض وجود ندارد. `reset-password` برای بازیابی است و همه نشست‌ها را باطل می‌کند.
- **رمز عبور**: هش با Argon2id، حداقل ۱۰ کاراکتر، rehash خودکار در صورت تغییر پارامترها، و مقایسه با hash ساختگی برای کاربر ناموجود تا از روی زمان پاسخ نتوان وجود نام کاربری را فهمید.
- **Session**: سمت سرور در جدول `auth_sessions`. Cookie از نوع HttpOnly و SameSite=Lax است و در Production `Secure` با پیشوند `__Host-` دارد. فقط SHA-256 توکن ذخیره می‌شود. انقضا ۷ روز است و Logout نشست را در سرور باطل می‌کند. توکن هرگز در body یا localStorage نیست.
- **API**: `POST /api/auth/login`، `POST /api/auth/logout`، `GET /api/auth/me`، `POST /api/auth/change-password`. تغییر رمز بقیه نشست‌ها را باطل و در Activity Log ثبت می‌کند. `GET /api/dashboard/summary` و `GET /api/dashboard/recent-activity` هم اضافه شدند و همه مسیرهای پنل احراز هویت می‌خواهند.
- **Rate limit ورود**: شکست‌ها در جدول `login_attempts` ذخیره می‌شوند تا با Restart یا چند worker از بین نروند. سقف ۵ تلاش برای هر نام کاربری و ۲۰ تلاش برای هر IP در ۱۵ دقیقه است و پیام خطا یکسان است. یک `limit_req` هم برای `/api/auth/login` در Nginx اضافه شد.
- **CSRF**: middleware برای POST/PUT/DELETE هدر `X-Requested-With: fetch` را الزامی می‌کند و اگر Origin فرستاده شود باید دامنه پنل باشد. Webhook تلگرام از این قاعده مستثناست و با secret خودش محافظت می‌شود.
- **داشبورد**: کارت‌های کل شاگردان (بدون بایگانی‌شده‌ها)، شاگردان فعال، کل برنامه‌های ثبت‌شده (تأییدشده و بایگانی، بدون پیش‌نویس) و برنامه‌های **ماه جاری شمسی** به وقت تهران. فهرست آخرین شاگردان، آخرین برنامه‌ها و فعالیت‌های اخیر نمایش داده می‌شوند و جستجوی سریع و دکمه‌های افزودن شاگرد و ثبت برنامه هم وجود دارند.
- **پنل**: کامپوننت‌های shadcn/ui (Button، Input، Label، Card، Alert، Skeleton، Sheet، Toaster) روی Radix. Sidebar در دسکتاپ سمت راست است و در موبایل نوار بالا با منوی کشویی دارد. AuthGate کاربر بدون نشست را به `/login?next=...` می‌فرستد و این مسیر بازگشت در برابر open redirect محافظت شده است. صفحه تنظیمات فرم تغییر رمز دارد. صفحات شاگردان و برنامه‌ها فعلاً پیام «در فاز بعد» نشان می‌دهند.

### Migrationها
- `20261031_8112dee81d16_auth_sessions_and_login_attempts` — جداول `auth_sessions` و `login_attempts` (افزوده به سند برای Session سمت سرور و Rate limit پایدار).

### تست‌های اجراشده و نتیجه
| تست | نتیجه |
|---|---|
| `pytest` — ۳۹ تست (۲۶ تست جدید): ورود موفق و ویژگی‌های Cookie، ذخیره hash توکن، پیام یکسان برای رمز اشتباه و کاربر ناموجود، `me` بدون نشست، باطل شدن Cookie قدیمی بعد از Logout، نشست منقضی، کاربر غیرفعال، Rate limit (حتی با رمز درست)، پاک شدن شکست‌ها بعد از ورود موفق، CSRF (بدون هدر و با Origin بیگانه)، تغییر رمز و باطل شدن نشست‌های دیگر، اعتبارسنجی رمز، Argon2id، شمارش‌های داشبورد، Activity، مرز ماه شمسی (آبان و اسفند)، CLI (ساخت، ساخت دوم، رمز ضعیف، بازیابی) | ✅ ۳۹/۳۹ |
| Alembic: `downgrade base` → `upgrade head` و `alembic check` | ✅ |
| Frontend `npm test` (تاریخ، ارقام، جلوگیری از open redirect) | ✅ ۶/۶ |
| `typecheck`، `lint` (بدون خطا و هشدار)، `build` | ✅ |
| E2E با Playwright (`e2e/phase2.smoke.mjs`) روی API و پنل واقعی: هدایت به Login، خطای فارسی رمز اشتباه، ورود، داشبورد با داده، HttpOnly بودن Cookie و خالی بودن localStorage، اعتبارسنجی فرم تغییر رمز، Logout، موبایل بدون اسکرول افقی و منوی کشویی | ✅ ۷/۷ |

### ناقص / تست‌نشده
- **shadcn CLI**: دامنه `ui.shadcn.com` در شبکه این محیط مسدود بود، پس کامپوننت‌ها با الگوی استاندارد shadcn و Radix دستی اضافه شدند. `components.json` برای استفاده بعدی از CLI وجود دارد.
- Cookie در حالت Production (`Secure` و `__Host-`) فقط در تست واحد بررسی شده و روی HTTPS واقعی بعد از استقرار باید تست شود.
- Nginx `limit_req` همچنان با `nginx -t` تست نشده است (nginx در محیط نیست).
- رنگ‌های برند هنوز موقت‌اند.

### گام بعدی
فاز ۳: API و UI مدیریت شاگردان (CRUD، جستجو، فیلتر، مرتب‌سازی، صفحه‌بندی)، پرونده با تب‌ها، آرشیو و غیرفعال‌سازی، ثبت در Activity Log و آپلود امن تصویر پروفایل.

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
