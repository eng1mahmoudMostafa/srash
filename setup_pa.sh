#!/usr/bin/env bash
# إعداد «صراحة» على PythonAnywhere بأمر واحد:
#   git clone https://github.com/eng1mahmoudMostafa/srash && bash srash/setup_pa.sh
set -e
cd "$(dirname "$0")"
echo "============================================="
echo "  إعداد موقع صراحة على PythonAnywhere"
echo "============================================="

USERPA=$(whoami)
echo "المستخدم: $USERPA"

# 1) كلمة مرور بريد Gmail (لن تُخزَّن في أي مستودع — فقط في .env على حسابك)
read -p "الصق كلمة مرور تطبيق Gmail (EMAIL_HOST_PASSWORD): " EP
if [ -z "$EP" ]; then echo "لم تُدخل كلمة المرور — أعد تشغيل السكربت"; exit 1; fi

# 2) مفتاح سري عشوائي قوي يُولَّد تلقائيًا
SK=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")

# 3) ملف البيئة (لا يُرفع لـGitHub — .gitignore يستبعده)
cat > .env <<EOF
DJANGO_SECRET_KEY=$SK
DJANGO_DEBUG=0
DB_ENGINE=sqlite
CACHE_BACKEND=locmem
COOKIE_SECURE=1
SECURE_HSTS_SECONDS=31536000
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=1
EMAIL_HOST_USER=sarahuhbilakadhb@gmail.com
EMAIL_HOST_PASSWORD=$EP
DEFAULT_FROM_EMAIL=sarahuhbilakadhb@gmail.com
DJANGO_ALLOWED_HOSTS=$USERPA.pythonanywhere.com
CSRF_TRUSTED_ORIGINS=https://$USERPA.pythonanywhere.com
CORS_ALLOWED_ORIGINS=https://$USERPA.pythonanywhere.com
SITE_BASE_URL=https://$USERPA.pythonanywhere.com
EOF
echo "[1/5] تم إنشاء ملف .env بالقيم السرية"

# 4) بيئة افتراضية + مكتبات
python3 -m venv "$HOME/venv-srash"
"$HOME/venv-srash/bin/pip" install --quiet --upgrade pip
"$HOME/venv-srash/bin/pip" install --quiet -r backend/requirements.txt
echo "[2/5] تم تثبيت المكتبات"

# 5) قاعدة البيانات + الملفات الثابتة
"$HOME/venv-srash/bin/python" backend/manage.py migrate --noinput
echo "[3/5] تم إنشاء قاعدة البيانات"
"$HOME/venv-srash/bin/python" backend/manage.py collectstatic --noinput
echo "[4/5] تم تجميع الملفات الثابتة"

# 6) توليد ملف WSGI الجاهز
cat > "$HOME/srash/pa_wsgi.py" <<EOF2
import os, sys
sys.path.insert(0, '/home/$USERPA/srash/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
EOF2
echo "[5/5] تم توليد ملف pa_wsgi.py"

echo ""
echo "============================================="
echo "  ✅ الإعداد اكتمل بنجاح!"
echo "============================================="
echo "الخطوات المتبقية (في تبويب Web):"
echo "1. Source code / Working directory:"
echo "   /home/$USERPA/srash/backend"
echo "2. Virtualenv:"
echo "   /home/$USERPA/venv-srash"
echo "3. انسخ محتوى /home/$USERPA/srash/pa_wsgi.py"
echo "   والصقه في ملف WSGI configuration"
echo "4. Static files: /static/ => /home/$USERPA/srash/backend/staticfiles"
echo "   Static files: /media/ => /home/$USERPA/srash/backend/media"
echo "5. اضغط Reload ثم افتح:"
echo "   https://$USERPA.pythonanywhere.com"