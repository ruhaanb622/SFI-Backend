#!/bin/bash

# Quick script to run the Flask backend

echo "🚀 Starting Flask Backend..."

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "✓ Virtual environment activated"
else
    echo "❌ Virtual environment not found! Run setup_and_run.sh first"
    exit 1
fi

# Run the Flask app
echo "✓ Starting Flask on http://localhost:8423"
echo ""
python main.py

