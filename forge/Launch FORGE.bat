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

:: We want all pip installs to go to D:\Forge\venv to prevent C: drive clutter.
SET "STORAGE_DIR=D:\Forge"
IF NOT EXIST "%STORAGE_DIR%" MKDIR "%STORAGE_DIR%"

SET "PYTHON_EXE="

:: 1. Check if the central venv already exists
IF EXIST "%STORAGE_DIR%\venv\Scripts\python.exe" (
    SET "PYTHON_EXE=%STORAGE_DIR%\venv\Scripts\python.exe"
    ECHO [OK] Using central venv Python in %STORAGE_DIR%\venv
    GOTO :FOUND_PYTHON
)

:: 2. If it doesn't exist, find system Python to create it
SET "SYS_PYTHON="
WHERE python >NUL 2>&1
IF %ERRORLEVEL% EQU 0 (
    FOR /F "tokens=*" %%i IN ('WHERE python') DO (
        SET "SYS_PYTHON=%%i"
        GOTO :CREATE_VENV
    )
)
WHERE python3 >NUL 2>&1
IF %ERRORLEVEL% EQU 0 (
    FOR /F "tokens=*" %%i IN ('WHERE python3') DO (
        SET "SYS_PYTHON=%%i"
        GOTO :CREATE_VENV
    )
)

ECHO [ERROR] Python not found!
ECHO Please install Python 3.10+ from https://python.org
ECHO Make sure to check "Add Python to PATH" during installation.
PAUSE
EXIT /B 1

:CREATE_VENV
ECHO [..] Creating central virtual environment in %STORAGE_DIR%\venv...
ECHO      (This prevents pip installs from cluttering the C: drive)
"%SYS_PYTHON%" -m venv "%STORAGE_DIR%\venv"
IF EXIST "%STORAGE_DIR%\venv\Scripts\python.exe" (
    SET "PYTHON_EXE=%STORAGE_DIR%\venv\Scripts\python.exe"
    ECHO [OK] Venv created successfully.
    GOTO :FOUND_PYTHON
)

:: 3. Fallbacks if venv creation fails
IF EXIST "%FORGE_DIR%\.venv\Scripts\python.exe" (
    SET "PYTHON_EXE=%FORGE_DIR%\.venv\Scripts\python.exe"
    GOTO :FOUND_PYTHON
)
SET "PYTHON_EXE=%SYS_PYTHON%"

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
    ECHO [!!] customtkinter not found. Installing requirements - this may take a few minutes...
    "%PYTHON_EXE%" -m pip install -r "%FORGE_DIR%\requirements.txt"
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

:: ── 4b. Kill any stale FORGE process on port 47392 ───────────────────────────
ECHO [..] Checking for stale FORGE instances...
FOR /F "tokens=5" %%p IN ('netstat -ano ^| findstr ":47392 " 2^>nul') DO (
    IF NOT "%%p"=="0" (
        ECHO [!!] Killing stale FORGE process PID %%p
        taskkill /F /PID %%p >nul 2>&1
    )
)
timeout /t 1 /nobreak >nul

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
