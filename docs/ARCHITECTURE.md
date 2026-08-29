# البنية المعمارية

## تدفق الإرسال المجهول

```
الزائر → /u/ahmed → كتابة رسالة → POST /api/messages/
   → Rate limiting (HMAC للـIP)
   → التحقق من حالة استقبال المستهدف
   → فحص Spam/إساءة (على النص الصريح قبل التشفير)
   → تشفير AES-256-GCM
   → حفظ في PostgreSQL (بدون sender, بدون IP)
   → إشعار المستلم
```

## تدفق الاستقبال

```
المستلم (Session) → GET /api/messages/inbox/
   → جلب الرسائل النشطة
   → فك التشفير بمفتاح الخادم
   → عرض للمستلم فقط
   → حذف ناعم / بلاغ
```

## نموذج البيانات

| الجدول | وصف |
|-------|-----|
| users | مستخدمون مخصّصون (AbstractUser) بدون إلزامية البريد |
| profiles | بيانات الملف العام (عرض، بيو) |
| user_settings | إعدادات الخصوصية/مكافحة الإساءة |
| messages | الرسائل المشفّرة (body_ciphertext، body_nonce) |
| reports | بلاغات المحتوى |
| abuse_events | إشارات HMAC قصيرة العمر لمكافحة الإساءة |
| notifications | إشعارات داخل التطبيق |

## مراحل التنفيذ

1. MVC — Django + PostgreSQL + CustomUser + Models
2. المصادقة Session + كوكي HttpOnly + CSRF
3. API الرسائل المجهولة + Rate limiting + Spam checks
4. تشفير الرسائل + سياسة الاحتفاظ
5. الواجهة React — صفحات المدخال والملكية
6. Docker → اختبارات → نشر