# Srash self-healing supervisor: keeps Django + public tunnel alive.
# Restarts the local server if it dies, creates a new public URL if the
# tunnel dies, updates CSRF/SITE_BASE_URL, and saves the URL to the Desktop.
$ErrorActionPreference = 'Continue'
$root    = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root 'backend'
$py      = Join-Path $backend '.venv\Scripts\python.exe'
$cfSrc   = Join-Path $env:USERPROFILE 'srash-tools\cloudflared.exe'
$cf      = Join-Path $env:TEMP 'cloudflared_srash.exe'
if (-not (Test-Path $cf)) { Copy-Item $cfSrc $cf -Force }
$desktop = [Environment]::GetFolderPath('Desktop')
$urlFile = Join-Path $desktop 'CURRENT-URL.txt'
$log     = Join-Path $root '_supervisor.log'

function Log($m) {
  Add-Content -Path $log -Value ('[' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + '] ' + $m)
}

function Stop-OurPython {
  Get-Process | Where-Object { $_.Path -and $_.Path -eq $py } | Stop-Process -Force -ErrorAction SilentlyContinue
  Start-Sleep -Seconds 2
}

function Stop-OurTunnel {
  Get-Process | Where-Object { $_.ProcessName -like 'cloudflared*' } | Stop-Process -Force -ErrorAction SilentlyContinue
  Start-Sleep -Seconds 2
}

function Start-Django($u) {
  $env:DJANGO_ALLOWED_HOSTS = '*'
  $env:DB_ENGINE = 'sqlite'
  $env:CACHE_BACKEND = 'locmem'
  $env:COOKIE_SECURE = '0'
  $env:CSRF_TRUSTED_ORIGINS = $u
  $env:SITE_BASE_URL = $u
  Start-Process -FilePath $py -ArgumentList 'manage.py','runserver','0.0.0.0:8000','--noreload' -WorkingDirectory $backend -WindowStyle Hidden
  Start-Sleep -Seconds 6
}

function Start-Tunnel {
  $out = Join-Path $env:TEMP 'cf_out.log'
  $err = Join-Path $env:TEMP 'cf_err.log'
  Remove-Item $out, $err -ErrorAction SilentlyContinue
  Start-Process -FilePath $cf -ArgumentList 'tunnel','--url','http://localhost:8000','--no-autoupdate' -RedirectStandardOutput $out -RedirectStandardError $err -WindowStyle Hidden
  # Reject reserved/placeholder hosts (api/www/update/metrics) that
  # cloudflared prints when quick-tunnel registration FAILS.
  foreach ($i in 1..20) {
    Start-Sleep -Seconds 2
    foreach ($p in @($out, $err)) {
      if (Test-Path $p) {
        $t = Get-Content $p -Raw
        if ($t -match 'https://(?!api\.|www\.|update\.|metrics\.)[a-z0-9-]+\.trycloudflare\.com') {
          $candidate = $Matches[0]
          if (Test-Url $candidate) { return $candidate }
        }
      }
    }
  }
  return $null
}

function Test-Url($u) {
  try { return ((Invoke-WebRequest -Uri ($u + '/api/stats/') -UseBasicParsing -TimeoutSec 12).StatusCode -eq 200) }
  catch { return $false }
}

function Publish($u) {
  $txt = $u + "`r`nLast updated: " + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + "`r`nIf the link changed, copy the new one from this file."
  Set-Content -Path $urlFile -Value $txt
}

Log '=== supervisor start ==='
Stop-OurPython
Stop-OurTunnel
Start-Django 'http://localhost:8000'
if (-not (Test-Url 'http://localhost:8000')) { Log 'warning: local server not responding yet' }

$url = Start-Tunnel
if ($url) {
  Stop-OurPython
  Start-Django $url
  Publish $url
  Log ('PUBLIC URL: ' + $url)
} else {
  Log 'tunnel creation failed - will retry in loop'
}

$failLocal = 0
$failRemote = 0
while ($true) {
  Start-Sleep -Seconds 30
  if (Test-Url 'http://localhost:8000') { $failLocal = 0 }
  else {
    $failLocal++
    if ($failLocal -ge 2) {
      Log 'local server down - restarting'
      Stop-OurPython
      Start-Django $(if ($url) { $url } else { 'http://localhost:8000' })
      $failLocal = 0
    }
  }
  if ($url -and (Test-Url $url)) { $failRemote = 0 }
  else {
    $failRemote++
    if ($failRemote -ge 2) {
      Log 'public url dead - creating new tunnel'
      Stop-OurTunnel
      $nu = Start-Tunnel
      if ($nu) {
        $url = $nu
        Stop-OurPython
        Start-Django $url
        Publish $url
        Log ('NEW PUBLIC URL: ' + $url)
      } else {
        Log 'tunnel retry failed - will try again'
      }
      $failRemote = 0
    }
  }
}