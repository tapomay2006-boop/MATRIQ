@echo off
title CPSE Pipeline 1 - Qwen2.5-3B LoRA Extraction Server
cd /d "%~dp0"

echo ======================================================================
echo  CPSE MATERIAL MASTER PIPELINE 1 EXTRACTION SERVER
echo  Starting on http://127.0.0.1:8001 ...
echo ======================================================================

set PYTHON_EXE=..\..\.venv\Scripts\python.exe

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Virtual environment not found at: %PYTHON_EXE%
    echo Please ensure .venv is installed in the repository root.
    pause
    exit /b 1
)

"%PYTHON_EXE%" server.py --host 127.0.0.1 --port 8001
pause
