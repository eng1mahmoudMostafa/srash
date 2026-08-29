#!/usr/bin/env bash
# إصلاح إعداد PythonAnywhere (تثبيت Pillow + إكمال الخطوات المتبقية)
set -e
cd "$(dirname "$0")"
USERPA=$(whoami)
VENV="$HOME/venv-srash"
echo "============================================="
echo "  إصلاح وإكمال إعداد صراحة"
echo "============================================="

echo "[1/5] تثبيت Pillow..."
"$VENV/bin/pip" install --quiet Pillow
grep -qxF 'Pillow>=10.0' backend/requirements.txt || echo "Pillow>=10.0" >> backend/requirements.txt

echo "[2/5] إنشاء قاعدة البيانات..."
"$VENV/bin/python" backend/manage.py migrate --noinput

echo "[3/5] تجميع الملفات الثابتة..."
"$VENV/bin/python" backend/manage.py collectstatic --noinput

echo "[4/5] توليد ملف pa_wsgi.py..."
cat > "$HOME/srash/pa_wsgi.py" <<EOF2
import os, sys
sys.path.insert(0, '/home/$USERPA/srash/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
EOF2

echo "[5/5] اكتمل!"
echo "============================================="
echo "  ✅ تم الإصلاح بنجاح — أكمل من تبويب Web"
echo "============================================="
echo "Working directory: /home/$USERPA/srash/backend"
echo "Virtualenv:        /home/$USERPA/venv-srash"
echo "WSGI:              انسخ محتوى /home/$USERPA/srash/pa_wsgi.py"
echo "Static:            /static/  =>  /home/$USERPA/srash/backend/staticfiles"
echo "Static:            /media/   =>  /home/$USERPA/srash/backend/media"
echo "رابط موقعك: https://$USERPA.pythonanywhere.com"