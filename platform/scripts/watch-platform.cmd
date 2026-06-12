@echo off
setlocal EnableExtensions

chcp 65001 >nul

rem Public entry: show the live status panel without starting services.
call "%~dp0_platform-control.cmd" watch
exit /b %ERRORLEVEL%
