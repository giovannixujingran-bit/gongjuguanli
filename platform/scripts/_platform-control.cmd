@echo off
setlocal EnableExtensions

chcp 65001 >nul

rem Internal implementation shared by the public platform *.cmd entries.
rem Keep this file pure ASCII -- under chcp 65001 cmd can misread batch
rem lines containing multi-byte characters and execute garbage fragments.

set "PLATFORM_DIR=%~dp0.."
pushd "%PLATFORM_DIR%" >nul 2>nul
if errorlevel 1 (
  echo [FAIL] Cannot enter platform directory: %PLATFORM_DIR%
  pause
  exit /b 1
)

if not exist ".run" mkdir ".run" >nul 2>nul

call :load_env

if defined PLATFORM_PYTHON (
  set "PY=%PLATFORM_PYTHON%"
) else if exist ".\.venv\Scripts\python.exe" (
  set "PY=.\.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

set "PS=pwsh.exe"
where.exe "%PS%" >nul 2>nul
if errorlevel 1 set "PS=powershell.exe"

set "ACTION=%~1"
if "%ACTION%"=="" set "ACTION=status"

if /i "%ACTION%"=="start" goto start
if /i "%ACTION%"=="status" goto status_once
if /i "%ACTION%"=="watch" goto watch
if /i "%ACTION%"=="stop" goto stop
if /i "%ACTION%"=="restart" goto restart

echo [FAIL] Unknown internal action: %ACTION%
goto finish_error

:start
echo.
echo === Start platform ===
echo Platform: %CD%
echo Python:   %PY%
echo Shell:    %PS%
echo.

echo [1/3] Starting PostgreSQL + API...
"%PS%" -NoProfile -ExecutionPolicy Bypass -File ".\scripts\serve.ps1" start
set "API_START_CODE=%ERRORLEVEL%"
if not "%API_START_CODE%"=="0" (
  echo [WARN] API startup script exited with code %API_START_CODE%.
)

echo.
echo [2/3] Starting web portal on 0.0.0.0:5174...
call :probe_url "http://127.0.0.1:5174/"
if "%ERRORLEVEL%"=="0" (
  echo [OK] Web portal is already running.
) else (
  start "Platform Web 5174" /min cmd /d /c ""%PY%" -m http.server 5174 --bind 0.0.0.0 --directory apps\web > ".run\web.log" 2> ".run\web.err""
  timeout /t 2 /nobreak >nul
)

echo.
echo [3/3] Opening live status. Press Ctrl+C to close this panel.
timeout /t 2 /nobreak >nul
goto watch

:restart
call :stop_services
echo.
goto start

:stop
call :stop_services
echo.
call :status_body
goto finish

:status_once
call :status_body
goto finish

:watch
cls
call :status_body
echo Commands:
echo   scripts\start-platform.cmd      Start API + web portal + live status
echo   scripts\stop-platform.cmd       Stop API + web portal
echo   scripts\status-platform.cmd     Print one status snapshot
echo   scripts\restart-platform.cmd    Restart API + web portal + live status
echo   scripts\watch-platform.cmd      Show live status only
echo.
echo This panel refreshes every 5 seconds. Press Ctrl+C to close it.
timeout /t 5 /nobreak >nul
goto watch

:status_body
echo.
echo === Platform status ===
echo Time: %DATE% %TIME%
echo.
call :print_pg_status
call :print_url_status "API health" "http://127.0.0.1:8000/health"
call :print_url_status "Web portal" "http://127.0.0.1:5174/"

call :detect_lan_ip
echo.
echo Local:
echo   Web: http://127.0.0.1:5174/
echo   API: http://127.0.0.1:8000/health
if defined LAN_IP (
  echo LAN / DingTalk PC:
  echo   Web: http://%LAN_IP%:5174/
) else (
  echo LAN / DingTalk PC:
  echo   Web: http://^<your LAN IP^>:5174/
)
echo.
echo Logs:
echo   API: .run\api.log
echo   Web: .run\web.log
echo.
exit /b 0

:stop_services
echo.
echo === Stop platform ===
echo [1/2] Stopping API...
"%PS%" -NoProfile -ExecutionPolicy Bypass -File ".\scripts\serve.ps1" stop
echo.
echo [2/2] Stopping web portal on port 5174...
call :stop_port 5174
exit /b 0

:stop_port
set "STOP_PORT=%~1"
set "FOUND_PORT_PID="
for /f "tokens=5" %%P in ('netstat -ano -p tcp ^| findstr /R /C:":%STOP_PORT% .*LISTENING"') do (
  set "FOUND_PORT_PID=%%P"
  taskkill /PID %%P /F >nul 2>nul
  if errorlevel 1 (
    echo [WARN] Could not stop PID %%P on port %STOP_PORT%.
  ) else (
    echo [OK] Stopped PID %%P on port %STOP_PORT%.
  )
)
if not defined FOUND_PORT_PID echo [OK] Nothing is listening on port %STOP_PORT%.
exit /b 0

:load_env
if not exist ".env" exit /b 0
for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
  set "ENV_NAME=%%A"
  set "ENV_VALUE=%%B"
  call :set_env_if_needed
)
exit /b 0

:set_env_if_needed
if "%ENV_NAME%"=="" exit /b 0
if "%ENV_NAME:~0,1%"=="#" exit /b 0
if /i "%ENV_NAME%"=="PLATFORM_PYTHON" set "PLATFORM_PYTHON=%ENV_VALUE%"
exit /b 0

:probe_url
%PS% -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-WebRequest -UseBasicParsing -Uri '%~1' -TimeoutSec 2; if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { exit 0 } exit 1 } catch { exit 1 }"
exit /b %ERRORLEVEL%

:print_url_status
call :probe_url "%~2"
if "%ERRORLEVEL%"=="0" (
  echo [OK]   %~1 - %~2
) else (
  echo [FAIL] %~1 - %~2
)
exit /b 0

:print_pg_status
for /f "usebackq delims=" %%L in (`%PS% -NoProfile -ExecutionPolicy Bypass -File ".\scripts\pg.ps1" status`) do (
  echo [INFO] PostgreSQL - %%L
)
exit /b 0

:detect_lan_ip
set "LAN_IP="
for /f "tokens=2 delims=:" %%I in ('ipconfig ^| findstr /C:"IPv4"') do (
  if not defined LAN_IP (
    for /f "tokens=* delims= " %%J in ("%%I") do set "LAN_IP=%%J"
  )
)
exit /b 0

:finish_error
popd >nul
exit /b 1

:finish
popd >nul
exit /b 0
