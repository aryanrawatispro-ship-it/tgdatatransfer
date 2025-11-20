#!/usr/bin/env python3
"""
Fast message forwarding tool for public channels
Forwards messages directly without downloading/uploading
Much faster than download/upload method
"""
import asyncio
import json
import os
from pathlib import Path
from datetime import datetime
from telethon import TelegramClient
from telethon.tl.types import Channel
from telethon.errors import FloodWaitError


class ForwardProgressTracker:
    """Tracks forwarding progress with resume capability."""

    def __init__(self, progress_path: str = "transfer_data/forward_progress.json"):
        # Ensure transfer_data directory exists
        Path("transfer_data").mkdir(exist_ok=True)
        self.progress_path = progress_path
        self.data = self._load_progress()

    def _load_progress(self):
        """Load existing progress or create new."""
        if os.path.exists(self.progress_path):
            try:
                with open(self.progress_path, 'r') as f:
                    data = json.load(f)
                    if "forwarded_ids" not in data:
                        data["forwarded_ids"] = []
                    return data
            except json.JSONDecodeError:
                print(f"⚠ Progress file corrupted. Starting fresh.")
                backup_path = f"{self.progress_path}.backup"
                os.rename(self.progress_path, backup_path)

        return {
            "forwarded_ids": [],
            "failed_ids": [],
            "forwarded_count": 0,
            "started_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat()
        }

    def save(self):
        """Save current progress."""
        self.data["last_updated"] = datetime.now().isoformat()
        with open(self.progress_path, 'w') as f:
            json.dump(self.data, f, indent=2)

    def mark_forwarded(self, message_id: int):
        """Mark a message as successfully forwarded."""
        if message_id not in self.data["forwarded_ids"]:
            self.data["forwarded_ids"].append(message_id)
            self.data["forwarded_count"] += 1
        self.save()

    def mark_failed(self, message_id: int):
        """Mark a message as failed."""
        if message_id not in self.data["failed_ids"]:
            self.data["failed_ids"].append(message_id)
        self.save()

    def is_forwarded(self, message_id: int) -> bool:
        """Check if message was already forwarded."""
        return message_id in self.data["forwarded_ids"]

    def get_stats(self):
        """Get current statistics."""
        return {
            "forwarded": self.data["forwarded_count"],
            "failed": len(self.data["failed_ids"])
        }


async def get_channel(client, channel_id):
    """Find channel by ID or username."""
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
        # Username or link
        return await client.get_entity(channel_id)
    return None


async def main():
    # Load config
    with open('config.json', 'r') as f:
        config = json.load(f)

    # Initialize progress tracker
    progress = ForwardProgressTracker()

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

    print("\nEnter source channel (public channel with forwarding enabled):")
    print("  Examples: @channelname, https://t.me/channelname, or -1001234567890")
    source_input = input("Source: ").strip()

    print("\nEnter destination channel (where messages will be forwarded to):")
    print("  Examples: @channelname, https://t.me/channelname, or -1001234567890")
    dest_input = input("Destination: ").strip()

    source_entity = await get_channel(client, source_input)
    dest_entity = await get_channel(client, dest_input)

    if not source_entity or not dest_entity:
        print("\n✗ Could not find channels")
        await client.disconnect()
        return

    print(f"\n✓ Source: {source_entity.title}")
    print(f"✓ Destination: {dest_entity.title}\n")

    # Count messages
    print("Counting messages...")
    messages = []
    skipped = 0

    async for msg in client.iter_messages(source_entity):
        # Skip already forwarded messages
        if progress.is_forwarded(msg.id):
            skipped += 1
            continue

        # Include all messages (media and text)
        if msg.media or msg.message:
            messages.append(msg)

    total = len(messages)
    messages.reverse()  # Process from oldest to newest

    # Display count
    print(f"Found {total} new messages")
    if skipped > 0:
        print(f"  ({skipped} already forwarded)")
    print()

    if total == 0:
        stats = progress.get_stats()
        print("✓ All messages already forwarded!")
        print(f"\nStats: {stats['forwarded']} messages forwarded")
        await client.disconnect()
        return

    print("="*60)
    print("FORWARD MODE - ULTRA FAST")
    print("Forwards messages without downloading/uploading")
    print("="*60 + "\n")

    choice = input("Start forwarding? (yes/no): ").strip().lower()
    if choice != 'yes':
        print("Cancelled")
        await client.disconnect()
        return

    print()

    # Forward messages
    forwarded = 0
    errors = 0
    delay = config.get('delay_between_files', 0)

    for idx, message in enumerate(messages, 1):
        try:
            # Show progress
            msg_type = "Media" if message.media else "Text"
            print(f"[{idx}/{total}] Forwarding {msg_type} message (ID: {message.id})", end='')

            # Forward the message
            await client.forward_messages(dest_entity, message)

            # Mark as forwarded
            progress.mark_forwarded(message.id)
            forwarded += 1
            print(f" ✓ ({forwarded}/{total})")

            # Rate limiting delay
            if delay > 0 and idx < total:
                await asyncio.sleep(delay)

        except FloodWaitError as e:
            print(f"\n⚠ Rate limit: waiting {e.seconds} seconds...")
            await asyncio.sleep(e.seconds)
            # Retry
            try:
                await client.forward_messages(dest_entity, message)
                progress.mark_forwarded(message.id)
                forwarded += 1
                print(f"  ✓ Forwarded after wait ({forwarded}/{total})")
            except Exception as retry_error:
                print(f"  ✗ Error after retry: {retry_error}")
                progress.mark_failed(message.id)
                errors += 1

        except Exception as e:
            print(f" ✗ Error: {e}")
            progress.mark_failed(message.id)
            errors += 1
            continue

    print(f"\n\n{'='*60}")
    print("COMPLETED!")
    print("="*60)

    # Show stats
    print(f"\nThis session:")
    print(f"  ✓ Forwarded: {forwarded}")
    print(f"  ✗ Errors: {errors}")

    stats = progress.get_stats()
    print(f"\nOverall progress:")
    print(f"  ✓ Total forwarded: {stats['forwarded']} messages")
    print(f"  ✗ Total failed: {stats['failed']} messages")
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
