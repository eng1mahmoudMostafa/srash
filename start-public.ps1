# تشغيل «صراحة بلا كذب» محليًا + رابط عام مستقر أثناء الجلسة
# Usage: powershell -ExecutionPolicy Bypass -File .\start-public.ps1
# الترتيب الجذري: النفق أولًا ← ثم Django مُهيَّأ بنفس الرابط
# (SITE_BASE_URL + CSRF) حتى تعمل الروابط المشتركة والإرسال من أي جهاز.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$py   = "$root\backend\.venv\Scripts\python.exe"
$cf   = "$env:TEMP\cloudflared_srash.exe"
if (-not (Test-Path $cf)) { Copy-Item "$env:USERPROFILE\srash-tools\cloudflared.exe" $cf }

# 0) إيقاف أي نسخة قديمة (تجنب تضارب المنافذ والروابط الميتة)
Get-Process python  -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process cloudflared_srash -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

# 1) النفق أولًا لمعرفة الرابط قبل تشغيل Django
$out="$env:TEMP\cf_out.log"; $err="$env:TEMP\cf_err.log"
Remove-Item $out,$err -ErrorAction SilentlyContinue
Start-Process -FilePath $cf -ArgumentList "tunnel","--url","http://localhost:8000","--no-autoupdate" `
  -RedirectStandardOutput $out -RedirectStandardError $err -WindowStyle Hidden
Write-Host "...جارٍ إنشاء الرابط العام..." -ForegroundColor Cyan
$url = $null
foreach ($i in 1..10) {
  Start-Sleep -Seconds 3
  $url = (Select-String -Path $err,$out -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -AllMatches |
          ForEach-Object { $_.Matches.Value } | Select-Object -Unique -First 1)
  if ($url) { break }
}
if (-not $url) { Write-Host "تعذر إنشاء الرابط، راجع $err" -ForegroundColor Red; exit 1 }

# 2) Django مُهيَّأ بنفس الرابط: روابط المشاركة + CSRF + الوسائط تعمل فورًا
$env:DJANGO_ALLOWED_HOSTS = "*"
$env:CSRF_TRUSTED_ORIGINS = "$url,https://*.trycloudflare.com,http://localhost:5173,http://localhost:8000"
$env:SITE_BASE_URL        = "$url"
$env:DB_ENGINE            = "sqlite"
$env:CACHE_BACKEND        = "locmem"
$env:COOKIE_SECURE        = "0"
$env:EMAIL_BACKEND        = "django.core.mail.backends.console.EmailBackend"
Start-Process -FilePath $py -ArgumentList "manage.py","runserver","0.0.0.0:8000","--noreload" `
  -WorkingDirectory "$root\backend" -WindowStyle Hidden
Start-Sleep -Seconds 6

Write-Host ""
Write-Host "=============================================" -ForegroundColor Green
Write-Host " الموقع : $url" -ForegroundColor Green
Write-Host " محليًا : http://localhost:5173" -ForegroundColor Gray
Write-Host " ملاحظة: أرسل للناس رابط «الموقع» أعلاه فقط." -ForegroundColor Yellow
Write-Host "=============================================" -ForegroundColor Green
Start-Process $url
