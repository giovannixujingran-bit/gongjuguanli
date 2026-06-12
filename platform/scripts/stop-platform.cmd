@echo off
setlocal EnableExtensions

chcp 65001 >nul

rem Public entry: stop API and web portal.
call "%~dp0_platform-control.cmd" stop
exit /b %ERRORLEVEL%
