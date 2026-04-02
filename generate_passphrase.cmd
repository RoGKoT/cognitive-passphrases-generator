@echo off
REM Windows CMD wrapper to run the Python passphrase generator.
cd /d "%~dp0"
python "%~dp0generate_passphrase.py" %*
if %ERRORLEVEL% NEQ 0 (
    echo Python failed or not found, trying py launcher...
    py "%~dp0generate_passphrase.py" %*
)
