#!/bin/bash

# LLM Ops Platform 개발 환경 시작 스크립트

set -e

echo "🚀 Starting LLM Ops Platform Development Environment"
echo ""

# Check if backend is running
if ! lsof -ti :8000 > /dev/null 2>&1; then
    echo "📦 Starting Backend Server..."
    cd "$(dirname "$0")/../backend"
    source .venv/bin/activate
    python -m src.api.app > /tmp/backend.log 2>&1 &
    BACKEND_PID=$!
    echo "   Backend started (PID: $BACKEND_PID)"
    echo "   Logs: /tmp/backend.log"
    sleep 3
else
    echo "✅ Backend already running on port 8000"
fi

# Check if frontend is running
if ! lsof -ti :3000 > /dev/null 2>&1; then
    echo "🎨 Starting Frontend Server..."
    cd "$(dirname "$0")/../frontend"
    npm run dev > /tmp/frontend.log 2>&1 &
    FRONTEND_PID=$!
    echo "   Frontend started (PID: $FRONTEND_PID)"
    echo "   Logs: /tmp/frontend.log"
    sleep 3
else
    echo "✅ Frontend already running on port 3000"
fi

echo ""
echo "✅ Development environment is ready!"
echo ""
echo "📍 URLs:"
echo "   Frontend: http://localhost:3000"
echo "   Backend API: http://localhost:8000"
echo "   API Docs: http://localhost:8000/llm-ops/v1/docs"
echo ""
echo "Press Ctrl+C to stop all servers"

# Wait for user interrupt
trap "echo ''; echo '🛑 Stopping servers...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT
wait

