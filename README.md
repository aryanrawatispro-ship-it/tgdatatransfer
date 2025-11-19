# Telegram Channel Media Transfer Tool

A Python-based automation tool for transferring content from one Telegram channel to another with minimal storage footprint. Perfect for VPS environments with limited disk space.

## Features

- **Complete channel cloning** - Copy both media files AND text messages
- **One-file-at-a-time processing** - Minimizes disk usage by downloading, uploading, and deleting each file sequentially
- **Text message copying** - Optional text-only message transfer (no download needed)
- **Progress tracking** - Saves progress to resume if interrupted
- **Interactive setup** - CLI prompts for easy configuration
- **Error handling** - Gracefully handles failures and continues processing
- **Resume capability** - Pick up where you left off after interruptions
- **Rate limiting** - Automatic delays to prevent Telegram API limits
- **Caption preservation** - Maintains original captions and metadata
- **Real-time progress** - Clear terminal output showing current status

## Requirements

- Python 3.7 or higher
- Telegram account
- API credentials (api_id and api_hash from https://my.telegram.org)
- Access to source channel (must be a member)
- Admin rights in destination channel

## Quick Start

### 1. Installation

```bash
# Clone or download this repository
cd tgdatatransfer

# Install Python dependencies
pip3 install -r requirements.txt
```

### 2. Get Telegram API Credentials

1. Go to https://my.telegram.org
2. Log in with your phone number
3. Click on "API Development Tools"
4. Create a new application (if you haven't already)
5. Copy your `api_id` and `api_hash`

### 3. Configure

```bash
# Copy the example config
cp config.example.json config.json

# Edit with your details
nano config.json
```

### 4. Run

```bash
# First run - interactive setup
python3 transfer.py

# Or run in background with screen/tmux
screen -S telegram_transfer
python3 transfer.py
# Press Ctrl+A then D to detach
```

## Configuration

Edit `config.json` with your settings:

```json
{
  "api_id": "YOUR_API_ID",
  "api_hash": "YOUR_API_HASH",
  "phone": "YOUR_PHONE_NUMBER",
  "source_channel": "@source_channel_username",
  "destination_channel": "@destination_channel_username",
  "delay_between_files": 2,
  "preserve_captions": true,
  "copy_text_messages": true,
  "download_path": "./temp_downloads"
}
```

**Configuration Options:**
- `copy_text_messages` - Set to `true` to copy text-only messages, `false` to copy only media (default: `true`)

## Usage

### Basic Usage

```bash
python3 transfer.py
```

### Background Execution

Using `screen`:
```bash
screen -S tg_transfer
python3 transfer.py
# Detach: Ctrl+A, then D
# Reattach: screen -r tg_transfer
```

Using `tmux`:
```bash
tmux new -s tg_transfer
python3 transfer.py
# Detach: Ctrl+B, then D
# Reattach: tmux attach -t tg_transfer
```

### Resume After Interruption

The script automatically saves progress in `progress.json`. Simply run the script again to resume:

```bash
python3 transfer.py
```

## Progress Tracking

Progress is saved in `progress.json` with:
- Total files processed
- Last processed message ID
- Failed file IDs
- Timestamp of last update

## Troubleshooting

### Authentication Issues
- Ensure your phone number includes country code (e.g., +1234567890)
- Check that api_id and api_hash are correct
- Delete `session.session` file and re-authenticate if needed

### Storage Issues
- The script processes one file at a time
- Check `download_path` has write permissions
- Ensure at least 100MB free space for large files

### Rate Limiting
- Increase `delay_between_files` in config.json
- Default is 2 seconds, try 5-10 seconds if you hit limits

### Channel Access
- Verify you're a member of the source channel
- Ensure you have admin/post rights in destination channel
- Use channel username (e.g., @channelname) or numeric ID

## File Structure

```
tgdatatransfer/
├── README.md              # This file
├── SETUP.md              # Detailed setup guide
├── transfer.py           # Main automation script
├── requirements.txt      # Python dependencies
├── config.example.json   # Configuration template
├── config.json          # Your configuration (gitignored)
├── progress.json        # Progress tracking (gitignored)
└── temp_downloads/      # Temporary download directory (gitignored)
```

## Safety Notes

- Never share your `config.json` or `session.session` files
- Keep your API credentials private
- Respect Telegram's Terms of Service
- Only use with channels you have permission to access
- Be mindful of rate limits to avoid account restrictions

## License

MIT License - Feel free to modify and use as needed.

## Support

For issues or questions, refer to:
- Telethon documentation: https://docs.telethon.dev/
- Telegram API documentation: https://core.telegram.org/api
