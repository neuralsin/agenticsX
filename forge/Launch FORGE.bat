@echo off
SETLOCAL ENABLEDELAYEDEXPANSION

:: ─────────────────────────────────────────────────────────────────────────────
:: FORGE Launcher — Double-click this to start FORGE
:: Works with system Python or a local venv inside the forge folder.
:: ─────────────────────────────────────────────────────────────────────────────

TITLE FORGE — Multi-Agent AI Studio

:: Get the directory this batch file lives in
SET "FORGE_DIR=%~dp0"
SET "FORGE_DIR=%FORGE_DIR:~0,-1%"

ECHO.
ECHO  ██████  ██████  ██████   ██████  ███████
ECHO  ██      ██  ██  ██   ██ ██       ██
ECHO  █████   ██  ██  ██████  ██  ███  █████
ECHO  ██      ██  ██  ██   ██ ██   ██  ██
ECHO  ██      ██████  ██   ██  ██████  ███████
ECHO.
ECHO  Multi-Agent AI Development Studio
ECHO  ─────────────────────────────────
ECHO.

:: ── 1. Locate Python ─────────────────────────────────────────────────────────

:: Check for a local venv first (user may have set one up)
SET "PYTHON_EXE="

IF EXIST "%FORGE_DIR%\.venv\Scripts\python.exe" (
    SET "PYTHON_EXE=%FORGE_DIR%\.venv\Scripts\python.exe"
    ECHO [OK] Using local .venv Python
    GOTO :FOUND_PYTHON
)

IF EXIST "%FORGE_DIR%\venv\Scripts\python.exe" (
    SET "PYTHON_EXE=%FORGE_DIR%\venv\Scripts\python.exe"
    ECHO [OK] Using local venv Python
    GOTO :FOUND_PYTHON
)

:: Fall back to system Python
WHERE python >NUL 2>&1
IF %ERRORLEVEL% EQU 0 (
    FOR /F "tokens=*" %%i IN ('WHERE python') DO (
        SET "PYTHON_EXE=%%i"
        GOTO :FOUND_PYTHON
    )
)

WHERE python3 >NUL 2>&1
IF %ERRORLEVEL% EQU 0 (
    FOR /F "tokens=*" %%i IN ('WHERE python3') DO (
        SET "PYTHON_EXE=%%i"
        GOTO :FOUND_PYTHON
    )
)

ECHO [ERROR] Python not found!
ECHO.
ECHO Please install Python 3.10+ from https://python.org
ECHO Make sure to check "Add Python to PATH" during installation.
ECHO.
PAUSE
EXIT /B 1

:FOUND_PYTHON
ECHO [OK] Python: %PYTHON_EXE%

:: ── 2. Check Python version ───────────────────────────────────────────────────

FOR /F "tokens=2 delims= " %%v IN ('"%PYTHON_EXE%" --version 2^>^&1') DO SET "PY_VER=%%v"
ECHO [OK] Version: %PY_VER%

:: ── 3. Check / install dependencies ──────────────────────────────────────────

ECHO.
ECHO [..] Checking dependencies...

"%PYTHON_EXE%" -c "import customtkinter" >NUL 2>&1
IF %ERRORLEVEL% NEQ 0 (
    ECHO [!!] customtkinter not found. Installing requirements...
    "%PYTHON_EXE%" -m pip install -r "%FORGE_DIR%\requirements.txt" --quiet
    IF %ERRORLEVEL% NEQ 0 (
        ECHO [ERROR] Failed to install requirements.
        ECHO Run manually: pip install -r requirements.txt
        PAUSE
        EXIT /B 1
    )
    ECHO [OK] Dependencies installed.
) ELSE (
    ECHO [OK] Core dependencies present.
)

:: ── 4. Set environment ────────────────────────────────────────────────────────

:: Load GEMINI_API_KEY from a local .env file if it exists
IF EXIST "%FORGE_DIR%\.env" (
    FOR /F "usebackq tokens=1,2 delims==" %%a IN ("%FORGE_DIR%\.env") DO (
        SET "%%a=%%b"
    )
    ECHO [OK] Loaded .env
)

:: ── 5. Launch FORGE ───────────────────────────────────────────────────────────

ECHO.
ECHO [>>] Launching FORGE...
ECHO.

CD /D "%FORGE_DIR%"
"%PYTHON_EXE%" main.py

SET "EXIT_CODE=%ERRORLEVEL%"
IF %EXIT_CODE% NEQ 0 (
    ECHO.
    ECHO [ERROR] FORGE exited with code %EXIT_CODE%
    ECHO Check the output above for errors.
    ECHO.
    PAUSE
)

ENDLOCAL
EXIT /B %EXIT_CODE%
