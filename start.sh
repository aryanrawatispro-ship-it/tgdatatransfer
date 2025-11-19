#!/bin/bash
# Quick start script with screen session

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SESSION_NAME="tg_transfer"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  Starting Telegram Transfer in Background                 ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Check if screen is installed
if ! command -v screen &> /dev/null; then
    echo "⚠️  'screen' is not installed"
    echo ""
    echo "Install with:"
    echo "  Ubuntu/Debian: sudo apt install screen"
    echo "  CentOS/RHEL:   sudo yum install screen"
    echo ""
    echo "Or run directly: python3 transfer.py"
    exit 1
fi

# Check if session already exists
if screen -list | grep -q "$SESSION_NAME"; then
    echo "ℹ️  Session '$SESSION_NAME' is already running"
    echo ""
    echo "Options:"
    echo "  - Attach to existing session: screen -r $SESSION_NAME"
    echo "  - Kill existing session:      screen -X -S $SESSION_NAME quit"
    echo "  - Start new session:          ./start.sh (after killing)"
    exit 0
fi

# Start screen session
echo "Starting screen session '$SESSION_NAME'..."
screen -dmS "$SESSION_NAME" bash -c "cd '$SCRIPT_DIR' && python3 transfer.py; exec bash"

sleep 1

# Check if started successfully
if screen -list | grep -q "$SESSION_NAME"; then
    echo "✓ Transfer started in background!"
    echo ""
    echo "Commands:"
    echo "  - Attach to session:  screen -r $SESSION_NAME"
    echo "  - Detach from session: Ctrl+A, then D"
    echo "  - View all sessions:  screen -ls"
    echo "  - Kill session:       screen -X -S $SESSION_NAME quit"
    echo ""
    echo "Attaching to session in 3 seconds..."
    echo "(Press Ctrl+C to cancel)"
    sleep 3
    screen -r "$SESSION_NAME"
else
    echo "❌ Failed to start session"
    exit 1
fi
