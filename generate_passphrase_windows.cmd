@echo off
REM Interactive Windows helper for cognitive passphrase generation.
REM Prompts for profile, order, count, and details, then opens a DOS window
REM running generate_passphrase.exe (if present) or falling back to Python.

cd /d "%~dp0"
setlocal EnableDelayedExpansion

set "profilesJson=%~dp0profiles\profiles.json"
if not exist "%profilesJson%" (
    echo Error: profiles file not found: "%profilesJson%"
    pause
    exit /b 1
)

set /a profileCount=0
for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "Get-Content -Raw -Path '%profilesJson%' | ConvertFrom-Json | Get-Member -MemberType NoteProperty | Select-Object -ExpandProperty Name"`) do (
    set /a profileCount+=1
    set "profile[!profileCount!]=%%P"
)

if %profileCount% EQU 0 (
    echo Error: no profiles found in "%profilesJson%"
    pause
    exit /b 1
)

echo.
echo Select a profile:
for /l %%I in (1,1,%profileCount%) do echo   %%I) !profile[%%I]!
set /p "choice=Enter profile number [1]: "
if "%choice%"=="" set "choice=1"
if not defined profile[%choice%] (
    echo Invalid profile selection: %choice%
    pause
    exit /b 1
)
set "profileName=!profile[%choice%]!"

echo.
echo Select field order:
echo   1) normal
echo   2) random
set /p "choice=Enter order number [1]: "
if /i "%choice%"=="2" (
    set "order=--random"
) else (
    set "order="
)

echo.
set /p "count=Number of passphrases [1]: "
if "%count%"=="" set "count=1"
for /f "delims=0123456789" %%N in ("%count%") do set "countInvalid=1"
if defined countInvalid (
    echo Invalid count: %count%
    pause
    exit /b 1
)
set "countArg=--count %count%"

echo.
echo Show generation details?
set /p "choice=Enter Y for yes, otherwise no [N]: "
if /i "%choice%"=="y" set "details=--details"

set "exePath=%~dp0generate_passphrase.exe"
if exist "%exePath%" (
    set "command=\"%exePath%\" %profileName% %countArg% %order% %details%"
) else (
    set "scriptPath=%~dp0generate_passphrase.py"
    if not exist "%scriptPath%" (
        echo Error: neither generate_passphrase.exe nor generate_passphrase.py was found.
        pause
        exit /b 1
    )
    set "command=python \"%scriptPath%\" %profileName% %countArg% %order% %details%"
)

echo.
echo Running: %command%
start "Cognitive Passphrase" cmd /k %command%
endlocal
