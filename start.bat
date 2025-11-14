@echo off
REM Quick start script for local development on Windows

echo 🚀 Starting JSSP Backend...
echo.

@REM REM Check if MiniZinc is installed
@REM where minizinc >nul 2>nul
@REM if %ERRORLEVEL% NEQ 0 (
@REM     echo ❌ MiniZinc is not installed!
@REM     echo Please install MiniZinc from: https://www.minizinc.org/software.html
@REM     pause
@REM     exit /b 1
@REM )

@REM echo ✅ MiniZinc found
@REM minizinc --version
@REM echo.

REM Check if virtual environment exists
if not exist "venv" (
    echo 📦 Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo 🔧 Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo 📥 Installing dependencies...
python -m pip install -q --upgrade pip
pip install -q -r requirements.txt

echo.
echo ✅ Setup complete!
echo.
echo 🌐 Starting server on http://localhost:8000
echo 📚 API docs available at http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop the server
echo.

REM Start the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000