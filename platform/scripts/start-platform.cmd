@echo off
setlocal EnableExtensions

chcp 65001 >nul

rem Public entry: start platform and keep a live status panel open.
call "%~dp0_platform-control.cmd" start
exit /b %ERRORLEVEL%
