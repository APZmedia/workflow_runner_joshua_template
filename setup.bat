@echo off
set VENV_DIR=workflow_runner\venv

if not exist %VENV_DIR% (
    echo Creating virtual environment...
    python -m venv %VENV_DIR%
)

echo Activating virtual environment...
call %VENV_DIR%\Scripts\activate

echo Installing dependencies...
pip install -r workflow_runner\requirements.txt

echo Virtual environment setup complete.
echo To activate it manually, run: call %VENV_DIR%\Scripts\activate
