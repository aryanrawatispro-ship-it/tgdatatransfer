What I Want to Do:

Download ALL media/files from a specific private Telegram channel that I'm a member of
Automatically upload each downloaded file to my own channel
Delete each file immediately after successful upload (critical for low storage VPS)
Process files ONE BY ONE to minimize disk usage

My Constraints:

Running on a VPS with very low storage (need to process one file at a time)
Private source channel (I'm a member but can't forward directly)
Need CLI-based solution that I can run via SSH

What I Need:

Complete setup instructions for tdl on Linux VPS
How to authenticate tdl with my Telegram account
The exact tdl commands to:

Download files from the source channel one at a time
Or download with limits to control disk usage


A bash/Python script that automates this workflow:

Download one file from source channel
Upload it to my destination channel using tdl or Telegram API
Delete the local file
Move to next file
Save progress so I can resume if interrupted



Additional Requirements:

Interactive CLI prompts for channel IDs on first run
Progress tracking (show X/Total files processed)
Handle errors gracefully (skip failed files, continue with next)
Resume capability if script is interrupted
Rate limit handling with delays between operations

Configuration Needed:

Source channel ID/username
Destination channel ID/username
Option to preserve captions/metadata
Configurable delay between uploads

Please provide:

Step-by-step tdl installation and authentication
Complete automation script (bash or Python)
How to run in background on VPS (screen/tmux)
How progress is saved and resumed
Error handling for common issues

Make it VPS-friendly with minimal storage footprint and clear terminal output showing real-time progress.
