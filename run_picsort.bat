@echo off
REM Double-click this file to start PicSort on Windows.
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set PYTHON=.venv\Scripts\python.exe
) else (
    where py >nul 2>nul && (set PYTHON=py -3) || (set PYTHON=python)
)

%PYTHON% -c "import PIL, imagehash, numpy, send2trash" >nul 2>nul
if errorlevel 1 (
    echo Installing dependencies...
    %PYTHON% -m pip install -r requirements.txt
)

echo Starting PicSort...
%PYTHON% picsort.py
if errorlevel 1 pause
