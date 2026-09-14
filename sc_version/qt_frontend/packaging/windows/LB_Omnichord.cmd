@echo off
setlocal

rem Explorer's "Run with PowerShell" obeys the machine execution policy and
rem closes its temporary console on failure.  This double-click entry point
rem applies a process-only bypass to the bundled, local launcher and preserves
rem an error message for interactive users.  It changes no system policy.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_windows.ps1" %*
set "lb_exit_code=%ERRORLEVEL%"

if not "%lb_exit_code%"=="0" (
    echo.
    echo LB Omnichord could not start. Error code: %lb_exit_code%
    if /I not "%CI%"=="true" pause
)

exit /b %lb_exit_code%
