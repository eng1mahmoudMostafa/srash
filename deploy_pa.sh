#!/bin/bash
# =============================================================================
#  auto-deploy لموقع صراحة على PythonAnywhere (الخطة المجانية)
# =============================================================================
#  الفكرة: متحتاجش تدخل السيرفر كل شهر. أي تحديث على GitHub
#  بينزّل هنا لوحده خلال 24 ساعة (git pull + migrate + reload).
#
#  التثبيت (مرة واحدة بس):
#    1. ارفع السكربت ده على GitHub واعمل git pull عليه هنا
#    2. PythonAnywhere -> Tasks -> Create a new scheduled task:
#         Command:   bash ~/srash/deploy_pa.sh
#         Schedule:  Daily, any hour
#    3. خلاص — مش هتدخل تاني أبداً.
#
#  لمتابعة السجل:  tail -20 ~/srash/deploy.log
# =============================================================================
set -u

LOG="$HOME/srash/deploy.log"

{
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') ==="

  cd "$HOME/srash" || { echo "ERROR: project folder not found"; exit 1; }

  # سحب معلومات التحديثات من GitHub (المستودع عام — مش محتاج كارت/توكن)
  if ! git fetch origin main -q; then
    echo "fetch failed (offline?) — will retry tomorrow"
    exit 1
  fi

  LOCAL=$(git rev-parse HEAD)
  REMOTE=$(git rev-parse origin/main)

  if [ "$LOCAL" = "$REMOTE" ]; then
    echo "up-to-date ($LOCAL) — nothing to do"
    exit 0
  fi

  echo "update found: $LOCAL -> $REMOTE"

  if ! git pull origin main; then
    echo "ERROR: git pull failed — check for local changes on the server"
    exit 1
  fi

  # تثبيت أي مكتبات جديدة (سريع لو مفيش تغيير)
  pip3 install -r backend/requirements.txt -q 2>&1 | tail -2

  # تحديث قاعدة البيانات والملفات الثابتة
  cd backend || exit 1
  python3 manage.py migrate --noinput
  python3 manage.py collectstatic --noinput

  # إعادة تشغيل الموقع (بايثون أني وير بيراقب ملف WSGI)
  touch /var/www/*_pythonanywhere_com_wsgi.py 2>/dev/null \
    || echo "WARNING: could not touch wsgi file — reload manually"

  echo "DEPLOYED OK: $REMOTE"

} >> "$LOG" 2>&1
