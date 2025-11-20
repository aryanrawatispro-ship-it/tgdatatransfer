#!/usr/bin/env python3
"""
Parallel transfer - downloads next file while uploading current one
Can be ~2x faster than sequential processing
"""
import asyncio
import json
import os
import re
from pathlib import Path
from datetime import datetime
from telethon import TelegramClient
from telethon.tl.types import Channel, DocumentAttributeFilename
from telethon.errors import FloodWaitError


class ProgressTracker:
    """Tracks transfer progress with resume capability."""

    def __init__(self, progress_path: str = "progress_parallel.json"):
        self.progress_path = progress_path
        self.data = self._load_progress()

    def _load_progress(self):
        """Load existing progress or create new."""
        if os.path.exists(self.progress_path):
            try:
                with open(self.progress_path, 'r') as f:
                    data = json.load(f)
                    if "processed_ids" not in data:
                        data["processed_ids"] = []
                    return data
            except json.JSONDecodeError:
                print(f"⚠ Progress file corrupted. Starting fresh.")
                backup_path = f"{self.progress_path}.backup"
                os.rename(self.progress_path, backup_path)

        return {
            "processed_ids": [],
            "failed_ids": [],
            "processed_count": 0,
            "total_size_mb": 0,
            "started_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat()
        }

    def save(self):
        """Save current progress."""
        self.data["last_updated"] = datetime.now().isoformat()
        with open(self.progress_path, 'w') as f:
            json.dump(self.data, f, indent=2)

    def mark_processed(self, message_id: int, file_size_mb: float = 0):
        """Mark a message as successfully processed."""
        if message_id not in self.data["processed_ids"]:
            self.data["processed_ids"].append(message_id)
            self.data["processed_count"] += 1
        self.data["total_size_mb"] += file_size_mb
        self.save()

    def mark_failed(self, message_id: int):
        """Mark a message as failed."""
        if message_id not in self.data["failed_ids"]:
            self.data["failed_ids"].append(message_id)
        self.save()

    def mark_skipped(self, message_id: int):
        """Mark a message as skipped."""
        if "skipped_ids" not in self.data:
            self.data["skipped_ids"] = []
        if message_id not in self.data["skipped_ids"]:
            self.data["skipped_ids"].append(message_id)
        self.save()

    def is_processed(self, message_id: int) -> bool:
        """Check if message was already processed."""
        return (message_id in self.data["processed_ids"] or
                message_id in self.data.get("skipped_ids", []))

    def get_stats(self):
        """Get current statistics."""
        return {
            "processed": self.data["processed_count"],
            "failed": len(self.data["failed_ids"]),
            "skipped": len(self.data.get("skipped_ids", [])),
            "total_size_mb": round(self.data["total_size_mb"], 2)
        }


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal and invalid characters."""
    # Remove path separators and null bytes
    filename = filename.replace('/', '_').replace('\\', '_').replace('\0', '')
    # Remove or replace other problematic characters
    filename = re.sub(r'[<>:"|?*]', '_', filename)
    # Remove leading/trailing spaces and dots
    filename = filename.strip('. ')
    # Ensure filename is not empty
    if not filename:
        filename = 'unnamed_file'
    # Limit length (most filesystems have 255 char limit)
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:200-len(ext)] + ext
    return filename


def cleanup_orphaned_files(download_path: Path):
    """Clean up any orphaned files from previous interrupted runs."""
    if not download_path.exists():
        return

    files = list(download_path.glob('*'))
    if files:
        print(f"\n⚠ Found {len(files)} orphaned files from previous run")
        for file_path in files:
            try:
                file_path.unlink()
                print(f"  🗑 Deleted: {file_path.name}")
            except Exception as e:
                print(f"  ⚠ Could not delete {file_path.name}: {e}")


def get_file_info(message):
    """Extract file information from message."""
    if not message.media:
        return None

    file_info = {
        "message_id": message.id,
        "file_name": None,
        "file_size": 0,
        "media_type": None
    }

    # Photo
    if hasattr(message.media, 'photo'):
        file_info["media_type"] = "photo"
        file_info["file_name"] = f"photo_{message.id}.jpg"
        if hasattr(message.media.photo, 'sizes'):
            sizes = [getattr(s, 'size', 0) for s in message.media.photo.sizes]
            file_info["file_size"] = max(sizes) if sizes else 0

    # Document (video, file, audio, etc.)
    elif hasattr(message.media, 'document'):
        doc = message.media.document
        file_info["media_type"] = "document"
        file_info["file_size"] = doc.size

        # Try to get filename from attributes
        for attr in doc.attributes:
            if isinstance(attr, DocumentAttributeFilename):
                file_info["file_name"] = sanitize_filename(attr.file_name)
                break

        if not file_info["file_name"]:
            # Generate safe default name
            mime_type = doc.mime_type if hasattr(doc, 'mime_type') else ''
            ext = mime_type.split('/')[-1] if '/' in mime_type else ''
            file_info["file_name"] = f"file_{message.id}.{ext}" if ext else f"file_{message.id}"

    else:
        return None

    # Ensure filename is sanitized
    if file_info["file_name"]:
        file_info["file_name"] = sanitize_filename(file_info["file_name"])

    return file_info


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

async def download_file(client, message, download_path, file_info):
    """Download a file with progress."""
    base_name = file_info["file_name"]
    file_path = download_path / base_name

    # Handle duplicate filenames
    counter = 1
    while file_path.exists():
        name, ext = os.path.splitext(base_name)
        file_path = download_path / f"{name}_{counter}{ext}"
        counter += 1

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
        print(f"  ⬇ Downloading: {file_path.name}")
        print(f"    Size: {file_info['file_size'] / (1024*1024):.2f} MB")

        await client.download_media(message.media, file=str(file_path), progress_callback=progress)
        print()  # New line

        # Verify file was downloaded
        if file_path.exists() and file_path.stat().st_size > 0:
            return file_path
        else:
            print(f"  ✗ Download failed - file not found or empty")
            if file_path.exists():
                file_path.unlink()
            return None

    except Exception as e:
        print(f"\n✗ Download error: {e}")
        # Clean up partial download
        if file_path.exists():
            try:
                file_path.unlink()
            except:
                pass
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

async def copy_text_message(client, message, dest_entity):
    """Copy text-only message to destination channel."""
    try:
        print(f"  📝 Copying text message...")
        await client.send_message(dest_entity, message.message)
        print(f"  ✓ Text copied")
        return True
    except FloodWaitError as e:
        print(f"\n⚠ Rate limit: waiting {e.seconds}s...")
        await asyncio.sleep(e.seconds)
        await client.send_message(dest_entity, message.message)
        return True
    except Exception as e:
        print(f"\n✗ Text copy error: {e}")
        return False

async def main():
    # Load config
    with open('config.json', 'r') as f:
        config = json.load(f)

    download_path = Path(config.get('download_path', './temp_downloads'))
    download_path.mkdir(parents=True, exist_ok=True)

    # Clean up orphaned files from previous runs
    cleanup_orphaned_files(download_path)

    # Initialize progress tracker
    progress = ProgressTracker()

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
    copy_text = config.get('copy_text_messages', True)
    max_size_mb = config.get('max_file_size_mb', 2000)
    messages = []
    skipped = 0
    too_large = 0

    async for msg in client.iter_messages(source_entity):
        # Skip already processed messages
        if progress.is_processed(msg.id):
            skipped += 1
            continue

        # Handle media files
        if msg.media:
            file_info = get_file_info(msg)
            if not file_info:
                continue

            # Check file size limit
            file_size_mb = file_info["file_size"] / (1024 * 1024)
            if file_size_mb > max_size_mb:
                too_large += 1
                progress.mark_skipped(msg.id)
                continue

            messages.append((msg, file_info))

        # Handle text messages
        elif copy_text and msg.message:
            messages.append((msg, None))

    total = len(messages)
    messages.reverse()  # Process from oldest to newest (first message to last)

    # Display count
    print(f"Found {total} new messages")
    if skipped > 0:
        print(f"  ({skipped} already processed)")
    if too_large > 0:
        print(f"  ({too_large} skipped - too large, limit: {max_size_mb} MB)")
    print()

    if total == 0:
        stats = progress.get_stats()
        print("✓ All messages already transferred!")
        print(f"\nStats: {stats['processed']} messages, {stats['total_size_mb']} MB total")
        if stats.get('skipped', 0) > 0:
            print(f"⊘ Skipped: {stats['skipped']} messages")
        await client.disconnect()
        return

    print("="*60)
    print("PARALLEL TRANSFER MODE")
    print("Downloads next file while uploading current one")
    print("="*60 + "\n")

    # Process messages
    processed = 0
    errors = 0

    download_task = None
    next_idx = 0

    while next_idx < total or download_task is not None:
        # Start processing next message if not currently downloading
        if download_task is None and next_idx < total:
            msg, file_info = messages[next_idx]
            next_idx += 1

            # Check if it's a text-only message
            if file_info is None:
                # Text message - process immediately (no download needed)
                print(f"\n[{next_idx}/{total}] Text message")
                success = await copy_text_message(client, msg, dest_entity)

                if success:
                    progress.mark_processed(msg.id, 0)
                    processed += 1
                    print(f"  ✓ Complete ({processed}/{total})")
                else:
                    progress.mark_failed(msg.id)
                    errors += 1
                continue

            # Media file - start download
            file_size_mb = file_info["file_size"] / (1024*1024)
            print(f"\n[{next_idx}/{total}] {file_info['file_name']} ({file_size_mb:.2f} MB)")
            download_task = asyncio.create_task(download_file(client, msg, download_path, file_info))
            current_msg = msg
            current_file_info = file_info

        # Wait for download to complete
        if download_task:
            file_path = await download_task
            download_task = None

            if file_path and file_path.exists():
                # Get caption
                caption = current_msg.message if config.get('preserve_captions', True) else None

                # Start next download in parallel with upload (only if next is media)
                if next_idx < total:
                    next_msg, next_file_info = messages[next_idx]
                    # Only start parallel download if next message has media
                    if next_file_info is not None:
                        next_idx += 1
                        file_size_mb = next_file_info["file_size"] / (1024*1024)
                        print(f"\n[{next_idx}/{total}] Downloading next while uploading current...")
                        download_task = asyncio.create_task(download_file(client, next_msg, download_path, next_file_info))
                        current_msg_temp = next_msg
                        current_file_info_temp = next_file_info

                # Upload current file
                success = await upload_file(client, file_path, caption, dest_entity)

                # Delete file
                try:
                    file_path.unlink()
                    print("  🗑 Deleted local file")
                except:
                    pass

                if success:
                    # Mark as processed
                    file_size_mb = current_file_info["file_size"] / (1024*1024)
                    progress.mark_processed(current_msg.id, file_size_mb)
                    processed += 1
                    print(f"  ✓ Complete ({processed}/{total})")
                else:
                    # Mark as failed
                    progress.mark_failed(current_msg.id)
                    errors += 1

                if download_task:
                    current_msg = current_msg_temp
                    current_file_info = current_file_info_temp
            else:
                # Mark as failed if download failed
                progress.mark_failed(current_msg.id)
                errors += 1

    print(f"\n\n{'='*60}")
    print("COMPLETED!")
    print("="*60)

    # Show session stats
    print(f"\nThis session:")
    print(f"  ✓ Transferred: {processed}")
    print(f"  ✗ Errors: {errors}")

    # Show overall stats
    stats = progress.get_stats()
    print(f"\nOverall progress:")
    print(f"  ✓ Total processed: {stats['processed']} messages")
    print(f"  ✗ Total failed: {stats['failed']} messages")
    if stats.get('skipped', 0) > 0:
        print(f"  ⊘ Total skipped: {stats['skipped']} messages (too large)")
    print(f"  📦 Total size: {stats['total_size_mb']} MB")
    print()

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
