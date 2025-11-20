#!/usr/bin/env python3
"""
Parallel transfer - downloads next file while uploading current one
Can be ~2x faster than sequential processing
"""
import asyncio
import json
import os
from pathlib import Path
from datetime import datetime
from telethon import TelegramClient
from telethon.tl.types import Channel
from telethon.errors import FloodWaitError

async def get_channel(client, channel_id):
    """Find channel by ID."""
    if channel_id.lstrip('-').isdigit():
        target_id = int(channel_id)
        if str(target_id).startswith('-100'):
            target_id_alt = int(str(target_id)[4:])
        else:
            target_id_alt = target_id

        async for dialog in client.iter_dialogs():
            if dialog.entity.id == target_id or dialog.entity.id == target_id_alt:
                return dialog.entity
    else:
        return await client.get_entity(channel_id)
    return None

async def download_file(client, message, download_path):
    """Download a file with progress."""
    file_path = download_path / f"temp_{message.id}.file"

    start_time = datetime.now()
    last_update = [start_time]

    def progress(current, total):
        now = datetime.now()
        if (now - last_update[0]).total_seconds() >= 2:
            percent = (current / total) * 100
            elapsed = (now - start_time).total_seconds()
            speed = (current / (1024*1024)) / elapsed if elapsed > 0 else 0
            print(f"  ⬇ Download: {percent:.1f}% | {speed:.2f} MB/s", end='\r')
            last_update[0] = now

    try:
        await client.download_media(message.media, file=str(file_path), progress_callback=progress)
        print()  # New line
        return file_path
    except Exception as e:
        print(f"\n✗ Download error: {e}")
        return None

async def upload_file(client, file_path, caption, dest_entity):
    """Upload a file with progress."""
    start_time = datetime.now()
    last_update = [start_time]

    def progress(current, total):
        now = datetime.now()
        if (now - last_update[0]).total_seconds() >= 2:
            percent = (current / total) * 100
            elapsed = (now - start_time).total_seconds()
            speed = (current / (1024*1024)) / elapsed if elapsed > 0 else 0
            print(f"  ⬆ Upload: {percent:.1f}% | {speed:.2f} MB/s", end='\r')
            last_update[0] = now

    try:
        await client.send_file(dest_entity, file=str(file_path), caption=caption, progress_callback=progress)
        print()  # New line
        return True
    except FloodWaitError as e:
        print(f"\n⚠ Rate limit: waiting {e.seconds}s...")
        await asyncio.sleep(e.seconds)
        await client.send_file(dest_entity, file=str(file_path), caption=caption)
        return True
    except Exception as e:
        print(f"\n✗ Upload error: {e}")
        return False

async def main():
    # Load config
    with open('config.json', 'r') as f:
        config = json.load(f)

    download_path = Path(config.get('download_path', './temp_downloads'))
    download_path.mkdir(parents=True, exist_ok=True)

    # Create client
    client = TelegramClient(
        'session',
        int(config['api_id']),
        config['api_hash'],
        connection_retries=10,
        retry_delay=2,
        timeout=30
    )

    await client.connect()

    if not await client.is_user_authorized():
        print("✗ Not authenticated. Run transfer.py first.")
        return

    me = await client.get_me()
    print(f"\n✓ Logged in as: {me.first_name}\n")

    # Get channels
    print("Looking up channels...")
    source_entity = await get_channel(client, config['source_channel'])
    dest_entity = await get_channel(client, config['destination_channel'])

    if not source_entity or not dest_entity:
        print("✗ Could not find channels")
        return

    print(f"✓ Source: {source_entity.title}")
    print(f"✓ Destination: {dest_entity.title}\n")

    # Count messages
    print("Counting messages...")
    messages = []
    async for msg in client.iter_messages(source_entity):
        if msg.media:
            messages.append(msg)

    total = len(messages)
    messages.reverse()  # Process from oldest to newest (first message to last)
    print(f"Found {total} media files\n")

    print("="*60)
    print("PARALLEL TRANSFER MODE")
    print("Downloads next file while uploading current one")
    print("="*60 + "\n")

    # Process files
    processed = 0
    errors = 0

    download_task = None
    next_idx = 0

    while next_idx < total or download_task is not None:
        # Start downloading next file if not already downloading
        if download_task is None and next_idx < total:
            msg = messages[next_idx]
            next_idx += 1
            file_size = msg.file.size if msg.file else 0
            print(f"\n[{next_idx}/{total}] Processing (Size: {file_size/(1024*1024):.2f} MB)")
            download_task = asyncio.create_task(download_file(client, msg, download_path))
            current_msg = msg

        # Wait for download to complete
        if download_task:
            file_path = await download_task
            download_task = None

            if file_path and file_path.exists():
                # Get caption
                caption = current_msg.message if config.get('preserve_captions', True) else None

                # Start next download in parallel with upload
                if next_idx < total:
                    msg = messages[next_idx]
                    next_idx += 1
                    file_size = msg.file.size if msg.file else 0
                    print(f"\n[{next_idx}/{total}] Downloading next while uploading current...")
                    download_task = asyncio.create_task(download_file(client, msg, download_path))
                    next_msg = msg

                # Upload current file
                success = await upload_file(client, file_path, caption, dest_entity)

                # Delete file
                try:
                    file_path.unlink()
                    print("  🗑 Deleted local file")
                except:
                    pass

                if success:
                    processed += 1
                    print(f"  ✓ Complete ({processed}/{total})")
                else:
                    errors += 1

                if download_task:
                    current_msg = next_msg
            else:
                errors += 1

    print(f"\n\n{'='*60}")
    print("COMPLETED!")
    print("="*60)
    print(f"✓ Transferred: {processed}")
    print(f"✗ Errors: {errors}\n")

    await client.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nCancelled\n")
    except Exception as e:
        print(f"\n✗ Error: {e}\n")
        import traceback
        traceback.print_exc()
