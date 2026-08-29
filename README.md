# صراحة — منصة رسائل مجهولة

منصة حديثة وآمنة تسمح للمستخدم باستقبال رسائل مجهولة، مع تقليل إمكانية كشف هوية
المرسل. مبنية على:

- **Backend:** Django + Django REST Framework
- **Database:** PostgreSQL
- **Cache/Rate-limiting:** Redis
- **Frontend:** React + Vite (proxy إلى Django)
- **Authentication:** Sessions + **HttpOnly/Secure/SameSite=Lax** cookies
  (بدل JWT)
- **تشفير الرسائل:** AES-256-GCM على مستوى الحقل (`body_ciphertext` +
  `body_nonce`)، والمفتاح خارج قاعدة البيانات

> **ملاحظة حول «المجهول»:** لا نعد المستخدم بأن هويته «مستحيل كشفها نهائيًا».
> التصميم يضمن أن **الرسالة لا تُربط بحساب المرسل ولا بعنوان IP**، وأن
> **المستلم لا يرى هوية المرسل**. تُستخدم إشارة HMAC أحادية الاتجاه لعنوان IP
> فقط لأغراض rate-limiting مع احتفاظ محدود، وهذا موثّق في سياسة الخصوصية.

---

## النشر السحابي (رابط ثابت / بدون بيانات على جهازك)

للحصول على **رابط دائم يعمل 24/7 دون تشغيل جهازك، وكل البيانات في السحابة**:

1. **ارفع المشروع إلى GitHub** (المسار مثالًا):
   ```bash
   git init && git add -A && git commit -m "init"
   git remote add origin https://github.com/you/srasha.git
   git push -u origin main
   ```
2. **أنشئ حسابًا مجانيًا على [Render](https://render.com)** (يكفي بريدك الإلكتروني).
3. من لوحة Render اختر **New → Blueprint** واربط مستودع GitHub.
   - `render.yaml` الجاهز سينشئ تلقائيًا: **خدمة الويب** + **قاعدة PostgreSQL مجانية**.
4. بعد النشر، افتح **Environment** وأدخل السرّية (في Render dashboard):
   ```env
   DJANGO_SECRET_KEY=<مفتاح عشوائي طويل>
   DJANGO_ALLOWED_HOSTS=*
   CSRF_TRUSTED_ORIGINS=https://<اسمك>.onrender.com
   SITE_BASE_URL=https://<اسمك>.onrender.com
   DEFAULT_FROM_EMAIL=صراحة <no-reply@onrender.com>
   ```
5. **البريد**: ضع `EMAIL_HOST_USER=<بريدك>` و `EMAIL_HOST_PASSWORD=<كلمة مرور التطبيق>` في نفس الشاشة (كما تعمل محليًا الآن). إعداد `smtp.gmail.com` جاهز.

> **رابع مجاني** على Render يُوقّف الخدمة عندما تنام (يدور الصفحة حتى تستيقظ). لتق ودائم 24/7 استخدم بلان مدفوع (+$7/شهر) أو رفع `render.yaml` تك فيح المنصة بعد تفعيل النوم — الشركة توفر `render.yaml` لتشغيل دائم.

---

## البنية

```
frontend/  (React + Vite)
   │  /api  (proxy في بيئة التطوير)
   ▼
backend/   (Django + DRF)
   ├── users/          نماذج المستخدم والإعدادات والمصادقة
   ├── messages_app/   نموذج الرسالة المشفّرة والإرسال والاستقبال
   ├── moderation/     البلاغات وأحداث الإساءة
   ├── notifications/  الإشعارات داخل التطبيق
   └── common/         التشفير، rate-limiting، فحص spam
```

الهيكل التفصيلي ومراحل التنفيذ موثّقة في `docs/ARCHITECTURE.md`.

---

## التشغيل السريع باستخدام Docker

1. انسخ ملف البيئة واملأ القيم:
   ```bash
   cp .env.example .env
   # عدّل المفاتيح السرية في .env (انظر التوجيهات داخل الملف)
   ```

2. شغّل الحاويات:
   ```bash
   docker compose up --build
   ```

   - Backend: http://localhost:8000
   - الأوامر (migrations + static) تُنفَّذ تلقائيًا عبر `docker-entrypoint.sh`

3. شغّل الواجهة (اختياري — منفصلة):
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

   وسيُوجَّه `/api` إلى backend عبر proxy في Vite.

---

## التشغيل محليًا (بدون Docker)

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# استخدم SQLite للاختبار السريع دون Postgres/Redis:
#   Windows PowerShell:
$env:DB_ENGINE="sqlite"; $env:CACHE_BACKEND="locmem"
python manage.py migrate
python manage.py runserver
```

### إنشاء مشرف

```bash
python manage.py createsuperuser
# لوحة الإدارة: http://localhost:8000/admin/
```

---

## الاختبارات

```bash
cd backend
python manage.py test
```

أو عبر pytest:

```bash
pytest
```

تشمل الاختبارات: التشفير (roundtrip)، فحص spam، تدفق التسجيل/الدخول/الخروج،
الإرسال المجهول، صندوق الرسائل، الحذف الناعم، وحظر المستلم، والبلاغات.

---

## واجهة REST

| الطريقة | المسار | الوصف |
|--------|--------|-------|
| POST | `/api/auth/register/` | إنشاء حساب (username + password فقط) |
| POST | `/api/auth/login/` | تسجيل الدخول (session cookie) |
| POST | `/api/auth/logout/` | تسجيل الخروج |
| GET | `/api/auth/me/` | بيانات المستخدم الحالي |
| GET | `/api/auth/csrf/` | إعداد كوكي CSRF للواجهة |
| GET | `/api/users/<username>/` | الملف العام للمستخدم |
| POST | `/api/messages/` | إرسال رسالة مجهولة (زائر) |
| GET | `/api/messages/inbox/` | صندوق رسائل المستلم |
| PATCH | `/api/messages/<id>/` | تعليم كمقروءة |
| DELETE | `/api/messages/<id>/` | حذف ناعم |
| POST | `/api/messages/<id>/report/` | الإبلاغ عن رسالة |
| GET/PATCH | `/api/settings/` | إعدادات الخصوصية |
| POST | `/api/settings/toggle-anonymous/` | إيقاف/استئناف الاستقبال |

---

## الأمان

- HttpOnly + Secure + SameSite=Lax للكوكيز.
- حماية CSRF مدمجة في Django مع نفخ التوكن للواجهة.
- Rate limiting (5/دقيقة و20/ساعة افتراضيًا) عبر Redis.
- Argon2id لتخزين كلمات المرور (لا تُشفَّر، بل تُجزَّأ).
- تشفير الرسائل AES-256-GCM على مستوى الحقل.
- لا يُخزَّن IP المرسل مع الرسالة؛ فقط HMAC أحادي الاتجاه باحتفاظ محدود.
- HTTPS/HSTS وأدوات الترويسة الأمنية قابلة للتفعيل في الإنتاج.
- حذف ناعم + أمر `purge_deleted_messages` لسياسة الاحتفاظ.

راجع قائمة التحقق الكاملة في `docs/SECURITY.md`.

---

## النسخ الاحتياطي

يفضَّل نسخ يومي مشفّر مع سياسة احتفاظ واختبار استعادة فعلي. أمثلة أوامر
`pg_dump` موثّقة في `docs/OPERATIONS.md`.
