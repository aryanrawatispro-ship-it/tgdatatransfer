#!/bin/bash
# Quick installation script for Telegram Channel Media Transfer Tool

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  Telegram Channel Media Transfer Tool - Installation      ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Check Python installation
echo "[1/4] Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed!"
    echo ""
    echo "Please install Python 3.7+ first:"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-pip"
    echo "  CentOS/RHEL:   sudo yum install python3 python3-pip"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "✓ Found Python $PYTHON_VERSION"

# Check pip installation
echo ""
echo "[2/4] Checking pip installation..."
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 is not installed!"
    echo ""
    echo "Please install pip3:"
    echo "  Ubuntu/Debian: sudo apt install python3-pip"
    echo "  CentOS/RHEL:   sudo yum install python3-pip"
    exit 1
fi
echo "✓ pip3 is installed"

# Install dependencies
echo ""
echo "[3/4] Installing Python dependencies..."
pip3 install -r requirements.txt --user
if [ $? -eq 0 ]; then
    echo "✓ Dependencies installed successfully"
else
    echo "❌ Failed to install dependencies"
    echo "Try: pip3 install --user -r requirements.txt"
    exit 1
fi

# Make script executable
echo ""
echo "[4/4] Setting permissions..."
chmod +x transfer.py
echo "✓ Permissions set"

# Create directories
echo ""
echo "Creating directories..."
mkdir -p temp_downloads
echo "✓ Created temp_downloads directory"

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║  Installation Complete!                                    ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo "1. Get your API credentials from https://my.telegram.org"
echo "2. Run: python3 transfer.py"
echo "3. Follow the interactive setup"
echo ""
echo "For detailed instructions, see: SETUP.md"
echo ""
