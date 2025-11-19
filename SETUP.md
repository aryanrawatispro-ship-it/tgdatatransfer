# Detailed Setup Guide

Complete step-by-step instructions for setting up the Telegram Channel Media Transfer Tool on a Linux VPS.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Python Solution Setup (Recommended)](#python-solution-setup-recommended)
3. [Alternative: tdl CLI Setup](#alternative-tdl-cli-setup)
4. [Getting Telegram API Credentials](#getting-telegram-api-credentials)
5. [Finding Channel IDs](#finding-channel-ids)
6. [Running in Background](#running-in-background)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements
- Linux VPS (Ubuntu 20.04+, Debian 10+, CentOS 7+)
- At least 100MB free disk space
- Python 3.7 or higher
- Internet connection
- SSH access to your VPS

### Check Python Version
```bash
python3 --version
```

If Python is not installed:
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip

# CentOS/RHEL
sudo yum install python3 python3-pip
```

---

## Python Solution Setup (Recommended)

This is the recommended approach with the automated script.

### Step 1: Clone or Download Repository

```bash
cd ~
git clone https://github.com/yourusername/tgdatatransfer.git
cd tgdatatransfer
```

Or if you uploaded files manually:
```bash
cd tgdatatransfer
```

### Step 2: Install Dependencies

```bash
pip3 install -r requirements.txt
```

If you encounter permission errors:
```bash
pip3 install --user -r requirements.txt
```

### Step 3: Get Telegram API Credentials

See [Getting Telegram API Credentials](#getting-telegram-api-credentials) section below.

### Step 4: First Run

```bash
python3 transfer.py
```

The script will:
1. Prompt you for API credentials
2. Ask for source and destination channels
3. Configure settings interactively
4. Save everything to `config.json`
5. Start the transfer process

### Step 5: Verify Configuration

The script creates `config.json`. You can edit it directly:

```bash
nano config.json
```

Example configuration:
```json
{
  "api_id": "12345678",
  "api_hash": "abcdef1234567890abcdef1234567890",
  "phone": "+1234567890",
  "source_channel": "@source_channel",
  "destination_channel": "@dest_channel",
  "delay_between_files": 2,
  "preserve_captions": true,
  "download_path": "./temp_downloads"
}
```

---

## Alternative: tdl CLI Setup

`tdl` is a Telegram downloader CLI tool. Here's how to set it up:

### Step 1: Install tdl

**Option A: Download prebuilt binary**
```bash
# Download latest release (check https://github.com/iyear/tdl/releases for latest version)
wget https://github.com/iyear/tdl/releases/download/v0.16.3/tdl_Linux_64bit.tar.gz

# Extract
tar -xzf tdl_Linux_64bit.tar.gz

# Move to system path
sudo mv tdl /usr/local/bin/

# Verify installation
tdl version
```

**Option B: Install with Go**
```bash
# Install Go if not installed
wget https://go.dev/dl/go1.21.5.linux-amd64.tar.gz
sudo tar -C /usr/local -xzf go1.21.5.linux-amd64.tar.gz
export PATH=$PATH:/usr/local/go/bin

# Install tdl
go install github.com/iyear/tdl@latest

# Add to PATH
export PATH=$PATH:~/go/bin
```

### Step 2: Authenticate tdl

```bash
# Login to Telegram
tdl login -n mysession

# You'll be prompted for:
# - Phone number (with country code)
# - Verification code sent to your Telegram app
# - 2FA password (if enabled)
```

### Step 3: Download from Channel

**List available media:**
```bash
tdl chat ls -n mysession
```

**Download specific channel:**
```bash
# Download all media from a channel
tdl dl -n mysession -c @channelname

# Download with limits
tdl dl -n mysession -c @channelname --limit 10

# Download specific file types
tdl dl -n mysession -c @channelname --include "*.jpg,*.mp4"
```

### Step 4: Upload to Another Channel

tdl is primarily for downloading. For uploading, you'll need to:

1. Use Telegram Desktop or mobile app
2. Use the Python script (recommended)
3. Use Telegram Bot API with curl/scripts

**Example upload with curl (requires bot token):**
```bash
curl -F "chat_id=@destination_channel" \
     -F "document=@/path/to/file" \
     "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/sendDocument"
```

### Step 5: Automation with tdl

Create a bash script to automate:

```bash
#!/bin/bash
# tdl-transfer.sh

SOURCE_CHANNEL="@source_channel"
DEST_CHANNEL="@dest_channel"
SESSION="mysession"
DOWNLOAD_DIR="./downloads"

# Download files one by one
tdl dl -n $SESSION -c $SOURCE_CHANNEL --dir $DOWNLOAD_DIR --limit 1

# Upload using your preferred method (bot API, etc.)
# Then delete local file
```

**Note:** The Python solution is more integrated and handles the full workflow automatically.

---

## Getting Telegram API Credentials

### Step 1: Visit Telegram API Portal

Go to: https://my.telegram.org

### Step 2: Log In

1. Enter your phone number (with country code, e.g., +1234567890)
2. Click "Next"
3. Enter the verification code sent to your Telegram app
4. If you have 2FA enabled, enter your password

### Step 3: Create Application

1. Click on "API Development Tools"
2. Fill out the form:
   - **App title**: Any name (e.g., "Media Transfer Tool")
   - **Short name**: Any short name (e.g., "transfer")
   - **Platform**: Choose "Other"
   - **Description**: Optional
3. Click "Create application"

### Step 4: Copy Credentials

You'll see:
- **api_id**: A number (e.g., 12345678)
- **api_hash**: A long string (e.g., abcdef1234567890...)

**IMPORTANT:** Keep these credentials private! Never share them or commit them to public repositories.

---

## Finding Channel IDs

### Method 1: Using Username (Easiest)

If the channel has a public username, use it directly:
```
@channelname
```

### Method 2: Using Web Telegram

1. Open https://web.telegram.org
2. Navigate to the channel
3. Look at the URL:
   - Public: `https://web.telegram.org/k/#@channelname` → use `@channelname`
   - Private: `https://web.telegram.org/k/#-1001234567890` → use `-1001234567890`

### Method 3: Using Bot

1. Add [@username_to_id_bot](https://t.me/username_to_id_bot) to your channel
2. Forward any message from the channel to the bot
3. The bot will reply with the channel ID

### Method 4: Using Python Script

```python
from telethon.sync import TelegramClient

api_id = YOUR_API_ID
api_hash = 'YOUR_API_HASH'

with TelegramClient('session', api_id, api_hash) as client:
    for dialog in client.iter_dialogs():
        print(f"{dialog.name}: {dialog.id}")
```

---

## Running in Background

### Option 1: screen (Recommended for Beginners)

**Install screen:**
```bash
# Ubuntu/Debian
sudo apt install screen

# CentOS
sudo yum install screen
```

**Usage:**
```bash
# Start new screen session
screen -S telegram_transfer

# Run the script
cd ~/tgdatatransfer
python3 transfer.py

# Detach from screen (keeps running)
# Press: Ctrl+A, then D

# List screens
screen -ls

# Reattach to screen
screen -r telegram_transfer

# Kill screen session
screen -X -S telegram_transfer quit
```

### Option 2: tmux (More Features)

**Install tmux:**
```bash
# Ubuntu/Debian
sudo apt install tmux

# CentOS
sudo yum install tmux
```

**Usage:**
```bash
# Start new tmux session
tmux new -s telegram_transfer

# Run the script
cd ~/tgdatatransfer
python3 transfer.py

# Detach from tmux
# Press: Ctrl+B, then D

# List sessions
tmux ls

# Reattach to session
tmux attach -t telegram_transfer

# Kill session
tmux kill-session -t telegram_transfer
```

### Option 3: nohup (Simple but Limited)

```bash
cd ~/tgdatatransfer
nohup python3 transfer.py > transfer.log 2>&1 &

# Check if running
ps aux | grep transfer.py

# View log
tail -f transfer.log

# Stop process
pkill -f transfer.py
```

### Option 4: systemd Service (Most Professional)

Create a service file:

```bash
sudo nano /etc/systemd/system/telegram-transfer.service
```

Add:
```ini
[Unit]
Description=Telegram Channel Media Transfer
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/home/youruser/tgdatatransfer
ExecStart=/usr/bin/python3 /home/youruser/tgdatatransfer/transfer.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-transfer
sudo systemctl start telegram-transfer

# Check status
sudo systemctl status telegram-transfer

# View logs
sudo journalctl -u telegram-transfer -f

# Stop service
sudo systemctl stop telegram-transfer
```

---

## Troubleshooting

### Authentication Errors

**Problem:** "Phone number is invalid"
```bash
# Solution: Ensure phone includes country code
# ✗ Wrong: 1234567890
# ✓ Correct: +1234567890
```

**Problem:** "API ID or hash is invalid"
```bash
# Solution: Verify credentials at https://my.telegram.org
# Delete session.session file and try again
rm session.session session.session-journal
python3 transfer.py
```

### Channel Access Errors

**Problem:** "ChannelPrivateError"
```bash
# Solutions:
# 1. Ensure you're a member of the source channel
# 2. For destination, ensure you have admin rights
# 3. Use correct channel ID or username
```

**Problem:** "Cannot find channel"
```bash
# Solutions:
# 1. For public channels: use @username
# 2. For private channels: use numeric ID (-1001234567890)
# 3. Verify you have access by opening channel in Telegram app
```

### Storage Issues

**Problem:** "No space left on device"
```bash
# Check available space
df -h

# Clean up download directory
rm -rf temp_downloads/*

# Reduce max file size in config.json
nano config.json
# Change "max_file_size_mb": 500  (or lower)
```

### Rate Limiting

**Problem:** "FloodWaitError: too many requests"
```bash
# Solution: Increase delay in config.json
nano config.json
# Change "delay_between_files": 5  (or higher)

# The script handles FloodWait automatically, but higher delays prevent it
```

### Python/Dependency Issues

**Problem:** "ModuleNotFoundError: No module named 'telethon'"
```bash
# Solution: Reinstall dependencies
pip3 install --force-reinstall -r requirements.txt
```

**Problem:** "python3: command not found"
```bash
# Install Python
sudo apt update && sudo apt install python3 python3-pip
```

### Performance Issues

**Problem:** Transfer is slow
```bash
# Solutions:
# 1. Check VPS internet speed: speedtest-cli
# 2. Reduce delay_between_files if no rate limits
# 3. Check VPS load: htop or top
```

### Resume After Interruption

**Problem:** Need to restart from where it stopped
```bash
# The script saves progress automatically
# Just run it again:
python3 transfer.py

# To start fresh (delete progress):
rm progress.json
python3 transfer.py
```

### Viewing Progress

**Check progress file:**
```bash
cat progress.json
```

**Watch logs in real-time:**
```bash
# If using screen/tmux, just attach to session
screen -r telegram_transfer

# If using nohup
tail -f transfer.log

# If using systemd
sudo journalctl -u telegram-transfer -f
```

---

## Additional Tips

### Check Disk Usage
```bash
# Monitor disk usage while running
watch -n 5 df -h

# Check download directory size
du -sh temp_downloads/
```

### Test Configuration
Before running full transfer, test with a small limit:
1. Edit the script temporarily to add a counter
2. Or manually stop after a few files to verify

### Backup Configuration
```bash
# Backup your config and progress
cp config.json config.json.backup
cp progress.json progress.json.backup
```

### Security Best Practices
```bash
# Set proper permissions on config file
chmod 600 config.json

# Never commit config.json to git (already in .gitignore)
git status  # Verify config.json is ignored
```

---

## Getting Help

If you encounter issues not covered here:

1. Check Telethon documentation: https://docs.telethon.dev/
2. Telegram API docs: https://core.telegram.org/api
3. Review error messages carefully - they often indicate the solution
4. Check VPS system logs: `sudo journalctl -xe`

---

## Quick Reference Commands

```bash
# Start transfer
python3 transfer.py

# Run in background with screen
screen -S tg && python3 transfer.py

# Check progress
cat progress.json

# View config
cat config.json

# Check running processes
ps aux | grep transfer.py

# Check disk space
df -h

# Clean downloads
rm -rf temp_downloads/*

# Fresh start (delete progress)
rm progress.json && python3 transfer.py
```
