@echo off
setlocal EnableExtensions

chcp 65001 >nul

rem Public entry: restart platform and keep a live status panel open.
call "%~dp0_platform-control.cmd" restart
exit /b %ERRORLEVEL%
