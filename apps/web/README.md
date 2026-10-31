# apps/web — پنل مربی (Next.js)

```bash
cp .env.example .env.local   # NEXT_PUBLIC_API_BASE_URL
npm ci
npm run dev        # http://localhost:3000
npm test           # unit tests (node:test)
npm run typecheck
npm run lint
npm run build
```

- RTL و فارسی؛ فونت Vazirmatn به‌صورت محلی در `app/fonts` (مجوز OFL).
- هیچ Secretی در Frontend قرار نمی‌گیرد؛ فقط متغیرهای `NEXT_PUBLIC_*` غیرمحرمانه.
- میزبانی روی Vercel (Root Directory: `apps/web`).
