#!/bin/bash
# Check transfer status and progress

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  Telegram Transfer - Status Check                         ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Check if process is running
if ps aux | grep -v grep | grep "transfer.py" > /dev/null; then
    echo "✓ Transfer process is RUNNING"
    echo ""
    ps aux | grep -v grep | grep "transfer.py" | awk '{print "  PID: " $2 "  CPU: " $3 "%  MEM: " $4 "%"}'
else
    echo "⊗ Transfer process is NOT RUNNING"
fi

echo ""
echo "────────────────────────────────────────────────────────────"
echo ""

# Check progress file
if [ -f "progress.json" ]; then
    echo "📊 Progress Information:"
    echo ""

    if command -v python3 &> /dev/null; then
        python3 << EOF
import json
with open('progress.json', 'r') as f:
    data = json.load(f)
    print(f"  Files Processed: {data.get('processed_count', 0)}")
    print(f"  Files Failed:    {len(data.get('failed_ids', []))}")
    print(f"  Files Skipped:   {len(data.get('skipped_ids', []))}")
    print(f"  Total Size:      {data.get('total_size_mb', 0):.2f} MB")
    print(f"  Last Updated:    {data.get('last_updated', 'N/A')}")
EOF
    else
        cat progress.json
    fi
else
    echo "ℹ️  No progress file found (transfer not started yet)"
fi

echo ""
echo "────────────────────────────────────────────────────────────"
echo ""

# Check disk space
echo "💾 Disk Space:"
echo ""
df -h . | tail -n 1 | awk '{print "  Used: " $3 " / " $2 "  (" $5 ")"}'

echo ""
echo "────────────────────────────────────────────────────────────"
echo ""

# Check screen sessions
if command -v screen &> /dev/null; then
    if screen -ls | grep -q "tg_transfer"; then
        echo "🖥️  Screen Session: ACTIVE"
        echo ""
        echo "  Attach with: screen -r tg_transfer"
    else
        echo "🖥️  Screen Session: Not found"
    fi
else
    echo "ℹ️  'screen' not installed"
fi

echo ""
