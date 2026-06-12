@echo off
setlocal EnableExtensions

chcp 65001 >nul

rem Public entry: print one status snapshot.
call "%~dp0_platform-control.cmd" status
exit /b %ERRORLEVEL%
