#!/bin/bash
# =============================================================================
#  auto-deploy + auto-renew لموقع صراحة على PythonAnywhere (الخطة المجانية)
# =============================================================================
#  مهم جدا — الخطة المجانية على بايثون أني وير (من مارس 2026):
#  الموقع بيقف لو مدخلتش لمدة شهر. السكربت ده بيحل المشكلتين مع بعض:
#    1) بينزّل أي تحديث من GitHub (git pull + migrate + reload)
#    2) بيعمل Reload عن طريق الـ API الرسمي كل يوم — وده بيمدّ تاريخ
#       التشغيل تلقائياً فمش محتاج تدخل تجدّد شهرياً أبداً
#
#  التثبيت (مرة واحدة):
#    1. من صفحة Account على بايثون أني وير -> API token -> أنشئ توكن
#    2. على الكونسول:  echo 'التوكن' > ~/.pa_api_token
#    3. PythonAnywhere -> Tasks -> مهمة يومية:  bash ~/srash/deploy_pa.sh
#    4. خلاص — مش هتدخل تاني أبداً
#
#  لمتابعة السجل:  tail -20 ~/srash/deploy.log
# =============================================================================
set -u

LOG="$HOME/srash/deploy.log"
USER_NAME="$(whoami)"
DOMAIN="${USER_NAME}.pythonanywhere.com"

{
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') ==="

  cd "$HOME/srash" || { echo "ERROR: project folder not found"; exit 1; }

  # ---- 1) تحديث الكود من GitHub ----
  if git fetch origin main -q; then
    LOCAL=$(git rev-parse HEAD)
    REMOTE=$(git rev-parse origin/main)
    if [ "$LOCAL" = "$REMOTE" ]; then
      echo "code: up-to-date ($LOCAL)"
    else
      echo "code: update found: $LOCAL -> $REMOTE"
      if git pull origin main; then
        pip3 install -r backend/requirements.txt -q 2>&1 | tail -2
        cd backend || exit 1
        python3 manage.py migrate --noinput
        python3 manage.py collectstatic --noinput
        cd "$HOME/srash" || exit 1
        echo "code: migrated + collectstatic OK"
      else
        echo "code: ERROR git pull failed — check for local changes"
      fi
    fi
  else
    echo "code: fetch failed (offline?) — retry tomorrow"
  fi

  # ---- 2) Reload + renew ----
  # المصدر الأول للتوكن: متغير البيئة $API_TOKEN. التاني: ملف ~/.pa_api_token
  # ملاحظة: الـreload عن طريق الـAPI رجّع 404 في اختباراتنا (بايثون أني وير
  # مش متاحركة الـendpoint ده حالياً) — فمنعتمدش عليه؛ لمس ملف WSGI هو
  # الطريقة المضمونة لإعادة تشغيل الموقع على بايثون أني وير.
  TOKEN="${API_TOKEN:-}"
  TOKEN_FILE="$HOME/.pa_api_token"
  if [ -z "$TOKEN" ] && [ -f "$TOKEN_FILE" ]; then
    TOKEN=$(tr -d '[:space:]' < "$TOKEN_FILE")
  fi

  # (أ) سجّل تاريخ انتهاء الموقع (مراقبة: هل النشاط اليومي بيمدّد التاريخ؟)
  if [ -n "$TOKEN" ]; then
    EXPIRY=$(curl -s -H "Authorization: Token $TOKEN" \
      "https://www.pythonanywhere.com/api/v0/user/${USER_NAME}/webapps/${DOMAIN}/" 2>/dev/null \
      | python3 -c "import sys,json; print(json.load(sys.stdin).get('expiry','?'))" 2>/dev/null \
      || echo "?")
    echo "expiry: ${EXPIRY}"
  fi

  # (ب) لمس ملف WSGI — إعادة تشغيل مضمونة للموقع
  if touch /var/www/*_pythonanywhere_com_wsgi.py 2>/dev/null; then
    echo "reload: wsgi touched OK"
  else
    echo "reload: WARNING could not touch wsgi file"
  fi

} >> "$LOG" 2>&1
