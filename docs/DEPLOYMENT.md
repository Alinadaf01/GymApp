# راهنمای استقرار — Basharnia Coach CRM

این راهنما سامانه را از صفر روی یک VPS اوبونتو ۲۴.۰۴ (Backend، ربات، Whisper، دیتابیس) و Vercel (پنل) راه‌اندازی می‌کند. همه دستورها روی سرور اجرا می‌شوند، مگر آنکه «روی کامپیوتر خودتان» نوشته شده باشد.

```text
coach.example.com  ──►  Vercel (پنل Next.js)
api.example.com    ──►  VPS: nginx (TLS) ─► api (FastAPI) ─► db (PostgreSQL)
                                  worker (Whisper + Parser)
                                  /data/basharnia (فایل‌های خصوصی)
Telegram ──webhook──►  https://api.example.com/api/telegram/webhook
```

## ۰. پیش‌نیازها

| مورد | توضیح |
|---|---|
| VPS | Ubuntu 24.04، حداقل ۴ vCPU، ۸ گیگابایت RAM، ۸۰ گیگابایت NVMe |
| **محل VPS** | سرور باید بدون محدودیت به `api.telegram.org`، Let's Encrypt، Docker Hub، PyPI، `cdn.playwright.dev`، HuggingFace (برای دانلود یک‌باره مدل)، GitHub و مخازن اوبونتو دسترسی داشته باشد. تلگرام در ایران فیلتر است، پس **VPS داخل ایران برای ربات مناسب نیست**؛ VPS خارج از ایران لازم است. |
| دامنه | دو رکورد DNS: `api.example.com` → IP سرور (رکورد A) و `coach.example.com` → Vercel (رکوردی که Vercel می‌دهد) |
| ربات تلگرام | Token از [@BotFather](https://t.me/BotFather) و **شناسه عددی** تلگرام مربی (مثلاً با @userinfobot) |
| کلید بکاپ | یک جفت کلید `age` که **روی کامپیوتر خودتان** ساخته می‌شود (بخش ۸) |
| فضای بکاپ خارجی | یک حساب ذخیره‌سازی که rclone پشتیبانی کند (بخش ۸ و `BACKUP_RESTORE.md`) |

در همه مثال‌ها، `example.com` را با دامنه خودتان جایگزین کنید.

## ۱. آماده‌سازی و ایمن‌سازی سرور

با کاربر root و کلید SSH وارد شوید. مخزن خصوصی است، پس برای clone یک Deploy Key فقط‌خواندنی (GitHub → Settings → Deploy keys) یا یک توکن محدود به همین مخزن لازم است.

```bash
git clone https://github.com/Alinadaf01/GymApp.git /opt/basharnia
```

```bash
ADMIN_USER=coachadmin bash /opt/basharnia/infra/scripts/setup-vps.sh
```

این اسکریپت (قابل اجرای چندباره) این کارها را انجام می‌دهد:
- نصب Docker، Compose، certbot، age، rclone، UFW و Fail2ban از مخازن رسمی اوبونتو.
- فعال کردن به‌روزرسانی امنیتی خودکار.
- ساخت کاربر مدیر با کلید SSH ریشه.
- غیرفعال کردن ورود root و ورود با رمز عبور در SSH، **فقط اگر** کاربر مدیر کلید SSH داشته باشد؛ در غیر این صورت هشدار می‌دهد و از قفل شدن جلوگیری می‌کند.
- باز گذاشتن فقط پورت‌های ۲۲، ۸۰ و ۴۴۳ در فایروال، فعال کردن Fail2ban برای SSH، ساخت swap و ساخت پوشه‌ها با مجوز درست.

برای دیدن کارهایی که انجام می‌شود، بدون اجرای آن‌ها:

```bash
DRY_RUN=1 ADMIN_USER=coachadmin bash /opt/basharnia/infra/scripts/setup-vps.sh
```

> **هشدار:** پیش از بستن نشست root، در یک ترمینال دیگر با `ssh coachadmin@SERVER` وارد شوید و مطمئن شوید ورود کار می‌کند.

از اینجا به بعد با کاربر مدیر کار کنید (`sudo` برای دستورهای root).

## ۲. تنظیم `.env`

```bash
cd /opt/basharnia && cp .env.example .env && chmod 600 .env
```

برای ساختن مقدارهای تصادفی:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

| متغیر | مقدار |
|---|---|
| `APP_ENV` | `production` |
| `APP_SECRET_KEY` | مقدار تصادفی (حداقل ۳۲ کاراکتر) |
| `POSTGRES_PASSWORD` | مقدار تصادفی |
| `DATABASE_URL` | `postgresql+psycopg://basharnia:<POSTGRES_PASSWORD>@db:5432/basharnia` |
| `FRONTEND_URL` | `https://coach.example.com` (باید https باشد) |
| `API_BASE_URL` و `API_DOMAIN` | `https://api.example.com` و `api.example.com` |
| `TELEGRAM_BOT_TOKEN`، `TELEGRAM_ALLOWED_USER_ID` | از BotFather و شناسه عددی مربی |
| `TELEGRAM_WEBHOOK_SECRET` | مقدار تصادفی (حداقل ۲۴ کاراکتر) |
| `ADMIN_USERNAME`، `INITIAL_ADMIN_PASSWORD` | **خالی بگذارید**؛ رمز در بخش ۵ به‌صورت تعاملی پرسیده می‌شود |

API در حالت production با تنظیمات ناامن **اجرا نمی‌شود**: کلید کوتاه، `DATABASE_URL` توسعه، یا `FRONTEND_URL` غیر https.

## ۳. ساخت image و گواهی SSL

```bash
cd /opt/basharnia && docker compose build
```

پیش از اجرای nginx (پورت ۸۰ باید آزاد باشد و DNS دامنه API به همین سرور اشاره کند):

```bash
sudo API_DOMAIN=api.example.com LE_EMAIL=you@example.com bash infra/scripts/init-ssl.sh
```

این اسکریپت گواهی اول را می‌گیرد، تمدیدها را روی webroot nginx تنظیم می‌کند (بدون قطعی)، بعد از هر تمدید nginx را reload می‌کند و تایمر تمدید certbot را فعال می‌کند. برای آزمایش تمدید:

```bash
sudo certbot renew --dry-run
```

## ۴. اجرای سرویس‌ها

```bash
cd /opt/basharnia && docker compose up -d
```

`migrate` پیش از `api` و `worker` اجرا می‌شود و migrationها را اعمال می‌کند. بررسی:

```bash
curl -s https://api.example.com/api/health/ready
```

پاسخ باید `{"status":"ok","database":"ok"}` باشد.

## ۵. حساب مربی

```bash
docker compose run --rm api python -m app.cli create-admin
```

نام کاربری و رمز (حداقل ۱۰ کاراکتر) پرسیده می‌شود. اگر رمز فراموش شد، با `reset-password` رمز جدید بگذارید؛ این دستور همه نشست‌ها را باطل می‌کند.

## ۶. مدل Whisper و ربات تلگرام

مدل یک‌بار در Volume دائمی دانلود می‌شود (حدود ۴۶۰ مگابایت برای `small`). بعد از آن، worker بدون اینترنت بارگذاری‌اش می‌کند.

```bash
docker compose run --rm worker python -m app.cli download-whisper-model
```

```bash
docker compose restart worker
```

```bash
docker compose run --rm api python -m app.cli set-webhook
```

```bash
docker compose run --rm api python -m app.cli webhook-info
```

در تلگرام به ربات `/start` بفرستید. از هر حساب دیگری باید پیام «این ربات فقط برای مربی است» برگردد.

## ۷. پنل روی Vercel

1. در Vercel، مخزن GitHub را Import کنید.
2. **Root Directory** را `apps/web` بگذارید. Framework به‌صورت خودکار Next.js تشخیص داده می‌شود و Node باید ۲۲ باشد.
3. Environment Variable را تنظیم کنید: `NEXT_PUBLIC_API_BASE_URL=https://api.example.com`. هیچ Secretی در Vercel لازم نیست.
4. Deploy کنید و در Settings → Domains دامنه `coach.example.com` را اضافه کنید.

پنل و API باید **زیر یک دامنه اصلی** باشند (`coach.` و `api.` در `example.com`)، چون Cookie ورود `SameSite=Lax` است.

> **شرایط Vercel Hobby:** پلن رایگان Hobby طبق شرایط Vercel برای استفاده **شخصی و غیرتجاری** است. استفاده یک مجموعه ورزشی ممکن است تجاری حساب شود. پیش از استقرار شرایط فعلی را بررسی کنید. جایگزین‌ها: پلن Pro در Vercel، یا اجرای پنل روی همان VPS (درخواست جداگانه).

## ۸. بکاپ خودکار

۱. **روی کامپیوتر خودتان** (نه روی سرور) کلید بسازید و فایل کلید خصوصی را در جای امن (مثلاً مدیر رمز عبور یا USB) نگه دارید:

```bash
age-keygen -o basharnia-backup.key
```

۲. روی سرور، پیکربندی بکاپ را بسازید:

```bash
sudo install -m 600 /opt/basharnia/infra/backup/backup.env.example /etc/basharnia/backup.env
```

در این فایل، `AGE_RECIPIENT` را برابر کلید عمومی (خط `public key: age1...`) و `RCLONE_REMOTE` را برابر مقصد خارجی بگذارید. مقصد را با این دستور تعریف کنید:

```bash
sudo rclone config
```

۳. تایمر روزانه را فعال کنید و یک بار دستی اجرا کنید:

```bash
sudo cp /opt/basharnia/infra/systemd/basharnia-backup.* /etc/systemd/system/ && sudo systemctl daemon-reload
```

```bash
sudo systemctl enable --now basharnia-backup.timer && sudo systemctl start basharnia-backup.service
```

```bash
journalctl -u basharnia-backup -n 30
```

۴. **تمرین بازیابی** (پیش از تحویل، و بعد از آن هر ماه): مراحل در `BACKUP_RESTORE.md`.

## ۹. به‌روزرسانی نسخه

```bash
cd /opt/basharnia && git pull && docker compose build && docker compose up -d
```

migrationهای جدید خودکار اجرا می‌شوند. پیش از هر به‌روزرسانی مهم یک بکاپ دستی بگیرید (`sudo systemctl start basharnia-backup.service`). Vercel با هر push به شاخه اصلی دوباره deploy می‌کند.

## ۱۰. بررسی نهایی پس از استقرار

- [ ] `https://api.example.com/api/health/ready` وضعیت ok را نشان می‌دهد و `http://` به `https://` هدایت می‌شود.
- [ ] ورود به `https://coach.example.com`، ساخت شاگرد و آپلود عکس پروفایل.
- [ ] ثبت برنامه، تأیید، دانلود و چاپ PDF.
- [ ] ربات: `/start`، ارسال یک ویس واقعی، بازبینی، تأیید و دریافت PDF در تلگرام.
- [ ] پیام به ربات از یک حساب دیگر رد می‌شود.
- [ ] `sudo ufw status` فقط پورت‌های ۲۲، ۸۰ و ۴۴۳ را نشان می‌دهد و `sudo fail2ban-client status sshd` فعال است.
- [ ] `docker compose ps` همه سرویس‌ها را healthy یا running نشان می‌دهد.
- [ ] بکاپ اول ساخته شده، در مقصد خارجی موجود است و **تمرین بازیابی** پاس شده است.
- [ ] `sudo certbot renew --dry-run` موفق است.

## عیب‌یابی

| مشکل | بررسی |
|---|---|
| ربات جواب نمی‌دهد | `webhook-info` (`last_error_message`)، `docker compose logs api`، درست بودن `TELEGRAM_ALLOWED_USER_ID` (شناسه عددی) |
| ویس پردازش نمی‌شود | `docker compose logs worker`؛ اگر مدل در Volume نباشد، دستور دانلود بخش ۶ را اجرا کنید |
| خطای ورود یا Cookie در پنل | `FRONTEND_URL` دقیقاً برابر آدرس پنل باشد؛ پنل و API زیر یک دامنه اصلی و هر دو روی https باشند |
| PDF ساخته نمی‌شود | `docker compose logs api`؛ حافظه سرور (Chromium) را بررسی کنید |
| دیسک پر شده | `docker system df`؛ لاگ کانتینرها محدود است (۵ فایل ۱۰ مگابایتی)؛ بکاپ‌های محلی بیش از ۷+۴ نسخه نگه داشته نمی‌شوند |
