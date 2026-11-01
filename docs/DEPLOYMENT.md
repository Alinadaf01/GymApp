# راهنمای استقرار — Basharnia Coach CRM

کل سامانه روی **یک VPS کوچک** و **یک دامنه** اجرا می‌شود؛ Vercel و سرویس دیگری لازم نیست.

```text
https://coach.example.com/       ──►  web    (پنل Next.js)
https://coach.example.com/api/   ──►  api    (FastAPI)  ──►  db (PostgreSQL)
Telegram ──► https://coach.example.com/api/telegram/webhook
                                      worker (Whisper + Parser فارسی)
                                      /data/basharnia (فایل‌های خصوصی)
همه پشت nginx (TLS)؛ فقط پورت‌های ۸۰ و ۴۴۳ باز هستند
```

## ۰. پیش‌نیازها

| مورد | توضیح |
|---|---|
| VPS | **Ubuntu 24.04**، **۲ vCPU، ۴ گیگابایت RAM، ۴۰ گیگابایت SSD** کافی است (یک کاربر). بیشترین مصرف مال Whisper است: حدود ۱٫۲ گیگابایت هنگام تبدیل ویس |
| **محل VPS** | **خارج از ایران**، چون تلگرام در ایران فیلتر است و ربات کار نمی‌کند. سرور باید به `api.telegram.org`، Let's Encrypt، Docker Hub، PyPI، npm، `deb.debian.org`، `cdn.playwright.dev` و HuggingFace دسترسی داشته باشد (VPSهای خارج از ایران معمولاً دارند) |
| دامنه | یک دامنه یا زیر‌دامنه، مثلاً `coach.example.com`، با رکورد A به IP سرور |
| ربات تلگرام | Token از [@BotFather](https://t.me/BotFather) و **شناسه عددی** تلگرام مربی (از [@userinfobot](https://t.me/userinfobot)) |

زمان تبدیل ویس روی ۲ vCPU تقریباً هم‌اندازه طول ویس است (یک دقیقه ویس، حدود یک دقیقه). اگر کند بود، می‌توان VPS را ارتقا داد؛ داده‌ها حفظ می‌شوند.

## ۱. نصب با یک دستور

با SSH و کاربر root وارد سرور شوید. مخزن خصوصی است، پس برای clone یکی از این دو لازم است:
- یک **Deploy key** فقط‌خواندنی (GitHub → مخزن → Settings → Deploy keys)
- یا یک **Fine-grained token** فقط‌خواندنی محدود به همین مخزن

```bash
git clone https://github.com/Alinadaf01/GymApp.git /opt/basharnia
```

```bash
bash /opt/basharnia/infra/scripts/install.sh
```

اسکریپت این موارد را می‌پرسد: دامنه، Token ربات (هنگام تایپ نمایش داده نمی‌شود)، شناسه عددی مربی، نام کاربر لینوکس برای ورودهای بعدی، و ایمیل برای گواهی SSL. سپس خودش:

1. سرور را ایمن می‌کند: SSH فقط با کلید، ورود root بسته، فایروال، Fail2ban، به‌روزرسانی امنیتی خودکار و swap.
2. همه رمزها را تصادفی می‌سازد و در `.env` (با مجوز `600`) ذخیره می‌کند.
3. بررسی می‌کند که دامنه به همین سرور اشاره کند.
4. image‌ها را می‌سازد (بار اول چند دقیقه طول می‌کشد) و گواهی SSL می‌گیرد.
5. سرویس‌ها را اجرا می‌کند و سالم بودن را بررسی می‌کند.
6. نام کاربری و رمز **حساب مربی** را می‌پرسد (رمز حداقل ۱۰ کاراکتر).
7. مدل Whisper را دانلود می‌کند و ربات تلگرام را وصل می‌کند.

اجرای دوباره اسکریپت بی‌خطر است و مراحل انجام‌شده را رد می‌کند.

> **هشدار SSH:** بعد از نصب، ورود root بسته می‌شود. **پیش از بستن نشست فعلی**، در یک ترمینال دیگر با `ssh coachadmin@coach.example.com` (همان کلید قبلی) وارد شوید و مطمئن شوید کار می‌کند. اسکریپت فقط وقتی SSH را می‌بندد که کلید شما برای کاربر جدید کپی شده باشد.

## ۲. بررسی

- `https://coach.example.com` را باز کنید و با حساب مربی وارد شوید.
- در تلگرام به ربات `/start` بفرستید. از هر حساب دیگری باید پیام «این ربات فقط برای مربی است» برگردد.
- در پنل، بخش **تنظیمات**، لوگو، نام مربی، شماره تماس و رنگ را وارد کنید (روی PDFها چاپ می‌شوند).

## ۳. بکاپ (پیش از ورود داده واقعی)

۱. **روی کامپیوتر خودتان** (نه روی سرور) کلید بکاپ بسازید. ابزار `age` را از [github.com/FiloSottile/age](https://github.com/FiloSottile/age/releases) بگیرید (ویندوز، مک و لینوکس):

```bash
age-keygen -o basharnia-backup.key
```

فایل `basharnia-backup.key` را در دو جای امن نگه دارید (مثلاً مدیر رمز عبور و یک USB). **بدون این فایل هیچ بکاپی باز نمی‌شود.** خط `public key: age1...` همان کلید عمومی است که روی سرور می‌گذارید.

۲. روی سرور:

```bash
sudo install -m 600 /opt/basharnia/infra/backup/backup.env.example /etc/basharnia/backup.env && sudo nano /etc/basharnia/backup.env
```

در این فایل، `AGE_RECIPIENT=age1...` (کلید عمومی) و `RCLONE_REMOTE` را بگذارید. مقصد خارجی را با `sudo rclone config` تعریف کنید؛ گزینه‌ها در `BACKUP_RESTORE.md` آمده است.

۳. فعال‌سازی، اجرای اول و بررسی:

```bash
sudo cp /opt/basharnia/infra/systemd/basharnia-backup.* /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now basharnia-backup.timer
```

```bash
sudo systemctl start basharnia-backup.service && journalctl -u basharnia-backup -n 30
```

۴. تمرین بازیابی را یک بار انجام دهید (`BACKUP_RESTORE.md`).

## ۴. دوره تست ویس

نصب‌کننده `AUDIO_RETAIN_HOURS=720` تنظیم می‌کند: ویس‌های خام ۳۰ روز نگه داشته می‌شوند تا بشود دقت را روی همان ویس‌ها دوباره سنجید. روند تست در [`VOICE_TEST.md`](VOICE_TEST.md) آمده است. پس از پایان دوره تست، برای حذف فوری ویس‌ها مقدار را صفر کنید:

```bash
cd /opt/basharnia && sudo sed -i 's/^AUDIO_RETAIN_HOURS=.*/AUDIO_RETAIN_HOURS=0/' .env && docker compose up -d worker
```

## ۵. به‌روزرسانی نسخه

```bash
cd /opt/basharnia && sudo systemctl start basharnia-backup.service && git pull && docker compose build && docker compose up -d
```

migrationهای جدید خودکار اجرا می‌شوند.

## ۶. چک‌لیست نهایی

- [ ] پنل روی `https://` باز می‌شود و `http://` به `https://` هدایت می‌شود.
- [ ] ورود، ساخت شاگرد و آپلود عکس.
- [ ] ثبت برنامه، تأیید، دانلود و **چاپ PDF**.
- [ ] ربات: `/start`، یک **ویس واقعی**، بازبینی، تأیید و دریافت PDF در تلگرام.
- [ ] پیام به ربات از یک حساب دیگر رد می‌شود.
- [ ] `sudo ufw status` فقط پورت‌های ۲۲، ۸۰ و ۴۴۳ را نشان می‌دهد.
- [ ] `docker compose ps` همه سرویس‌ها را healthy یا running نشان می‌دهد.
- [ ] بکاپ اول ساخته شده، در مقصد خارجی هست و **تمرین بازیابی** پاس شده است.
- [ ] `sudo certbot renew --dry-run` موفق است.

## عیب‌یابی

| مشکل | بررسی |
|---|---|
| خطای DNS در نصب | رکورد A دامنه باید IP همین سرور باشد؛ چند دقیقه صبر کنید و دوباره اجرا کنید |
| ربات جواب نمی‌دهد | `docker compose run --rm api python -m app.cli webhook-info` (`last_error_message`) و `docker compose logs api` |
| ویس پردازش نمی‌شود | `docker compose logs worker` |
| خطای ورود در پنل | `FRONTEND_URL` و `API_BASE_URL` در `.env` باید دقیقاً `https://<دامنه>` باشند |
| PDF ساخته نمی‌شود | `docker compose logs api` و حافظه آزاد (`free -h`) |
| رمز مربی فراموش شده | `docker compose run --rm api python -m app.cli reset-password` |

## نصب دستی (اختیاری)

اسکریپت‌ها جدا هم قابل اجرا هستند:
- `infra/scripts/setup-vps.sh`: ایمن‌سازی سرور (با `DRY_RUN=1` فقط کارهایی را که انجام می‌دهد نشان می‌دهد).
- `infra/scripts/init-ssl.sh`: گواهی SSL.
- سپس با `docker compose up -d` اجرا کنید.

متغیرهای `.env` در `.env.example` توضیح داده شده‌اند.
