#!/bin/bash
# Quick start script for local development

echo "🚀 Starting JSSP Backend..."
echo ""

# Check if MiniZinc is installed
if ! command -v minizinc &> /dev/null
then
    echo "❌ MiniZinc is not installed!"
    echo "Please install MiniZinc from: https://www.minizinc.org/software.html"
    exit 1
fi

echo "✅ MiniZinc found: $(minizinc --version | head -n 1)"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo ""
echo "✅ Setup complete!"
echo ""
echo "🌐 Starting server on http://localhost:8000"
echo "📚 API docs available at http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000