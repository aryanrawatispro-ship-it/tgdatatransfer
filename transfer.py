#!/usr/bin/env python3
"""
Telegram Channel Media Transfer Tool
Downloads media from source channel and uploads to destination channel
with minimal storage footprint (one file at a time).
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List

from telethon import TelegramClient, events
from telethon.tl.types import DocumentAttributeFilename, Message
from telethon.errors import FloodWaitError, ChannelPrivateError
from tqdm import tqdm


class Config:
    """Configuration manager with interactive setup."""

    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = self._load_or_create_config()

    def _load_or_create_config(self) -> Dict:
        """Load existing config or create new one interactively."""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return json.load(f)
        else:
            return self._interactive_setup()

    def _interactive_setup(self) -> Dict:
        """Interactive configuration setup."""
        print("\n" + "="*60)
        print("TELEGRAM CHANNEL TRANSFER - FIRST TIME SETUP")
        print("="*60 + "\n")

        print("First, you need API credentials from https://my.telegram.org")
        print("Go to 'API Development Tools' and create an application.\n")

        api_id = input("Enter your API ID: ").strip()
        api_hash = input("Enter your API Hash: ").strip()
        phone = input("Enter your phone number (with country code, e.g., +1234567890): ").strip()

        print("\n" + "-"*60)
        print("Channel Configuration")
        print("-"*60 + "\n")
        print("You can use channel username (@channelname) or numeric ID.")
        print("For private channels, use the numeric ID (e.g., -1001234567890).\n")

        source_channel = input("Enter SOURCE channel (to download from): ").strip()
        destination_channel = input("Enter DESTINATION channel (to upload to): ").strip()

        print("\n" + "-"*60)
        print("Optional Settings")
        print("-"*60 + "\n")

        delay = input("Delay between files in seconds [default: 2]: ").strip()
        delay = int(delay) if delay else 2

        preserve = input("Preserve original captions? (yes/no) [default: yes]: ").strip().lower()
        preserve_captions = preserve != 'no'

        download_path = input("Download path [default: ./temp_downloads]: ").strip()
        download_path = download_path if download_path else "./temp_downloads"

        config = {
            "api_id": api_id,
            "api_hash": api_hash,
            "phone": phone,
            "source_channel": source_channel,
            "destination_channel": destination_channel,
            "delay_between_files": delay,
            "preserve_captions": preserve_captions,
            "download_path": download_path,
            "max_file_size_mb": 2000,
            "file_types": ["photo", "video", "document", "audio"]
        }

        # Save configuration
        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=2)

        print(f"\n✓ Configuration saved to {self.config_path}")
        print("You can edit this file directly to change settings.\n")

        return config

    def get(self, key: str, default=None):
        """Get configuration value."""
        return self.config.get(key, default)


class ProgressTracker:
    """Tracks transfer progress with resume capability."""

    def __init__(self, progress_path: str = "progress.json"):
        self.progress_path = progress_path
        self.data = self._load_progress()

    def _load_progress(self) -> Dict:
        """Load existing progress or create new."""
        if os.path.exists(self.progress_path):
            with open(self.progress_path, 'r') as f:
                return json.load(f)
        return {
            "last_message_id": 0,
            "processed_count": 0,
            "failed_ids": [],
            "skipped_ids": [],
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
        self.data["last_message_id"] = message_id
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
        if message_id not in self.data["skipped_ids"]:
            self.data["skipped_ids"].append(message_id)
        self.save()

    def is_processed(self, message_id: int) -> bool:
        """Check if message was already processed."""
        return message_id <= self.data["last_message_id"]

    def get_stats(self) -> Dict:
        """Get current statistics."""
        return {
            "processed": self.data["processed_count"],
            "failed": len(self.data["failed_ids"]),
            "skipped": len(self.data["skipped_ids"]),
            "total_size_mb": round(self.data["total_size_mb"], 2)
        }


class TelegramTransfer:
    """Main transfer orchestrator."""

    def __init__(self, config: Config):
        self.config = config
        self.progress = ProgressTracker()
        self.client = None
        self.download_path = Path(config.get("download_path", "./temp_downloads"))

        # Create download directory
        self.download_path.mkdir(parents=True, exist_ok=True)

    async def initialize(self):
        """Initialize Telegram client and authenticate."""
        print("\n" + "="*60)
        print("Connecting to Telegram...")
        print("="*60 + "\n")

        self.client = TelegramClient(
            'session',
            int(self.config.get("api_id")),
            self.config.get("api_hash")
        )

        await self.client.start(phone=self.config.get("phone"))

        if await self.client.is_user_authorized():
            me = await self.client.get_me()
            print(f"✓ Authenticated as: {me.first_name} ({me.phone})")
        else:
            print("✗ Authentication failed")
            return False

        return True

    async def get_channel_info(self, channel_id: str):
        """Get channel information."""
        try:
            entity = await self.client.get_entity(channel_id)
            return entity
        except ChannelPrivateError:
            print(f"✗ Cannot access channel: {channel_id}")
            print("  Make sure you're a member of the channel.")
            return None
        except Exception as e:
            print(f"✗ Error accessing channel {channel_id}: {e}")
            return None

    async def count_media_messages(self, source_entity) -> int:
        """Count total media messages in source channel."""
        print("\nCounting media files in source channel...")
        count = 0
        async for message in self.client.iter_messages(source_entity):
            if message.media:
                count += 1
        return count

    def get_file_info(self, message: Message) -> Optional[Dict]:
        """Extract file information from message."""
        if not message.media:
            return None

        file_info = {
            "message_id": message.id,
            "file_name": None,
            "file_size": 0,
            "media_type": None,
            "caption": message.message if self.config.get("preserve_captions") else None
        }

        # Photo
        if hasattr(message.media, 'photo'):
            file_info["media_type"] = "photo"
            file_info["file_name"] = f"photo_{message.id}.jpg"
            if hasattr(message.media.photo, 'sizes'):
                file_info["file_size"] = max([s.size if hasattr(s, 'size') else 0 for s in message.media.photo.sizes])

        # Document (video, file, audio, etc.)
        elif hasattr(message.media, 'document'):
            doc = message.media.document
            file_info["media_type"] = "document"
            file_info["file_size"] = doc.size

            # Try to get filename from attributes
            for attr in doc.attributes:
                if isinstance(attr, DocumentAttributeFilename):
                    file_info["file_name"] = attr.file_name
                    break

            if not file_info["file_name"]:
                file_info["file_name"] = f"file_{message.id}"

        else:
            return None

        return file_info

    async def download_file(self, message: Message, file_info: Dict) -> Optional[Path]:
        """Download a single file."""
        file_path = self.download_path / file_info["file_name"]

        try:
            print(f"  ⬇ Downloading: {file_info['file_name']}")
            print(f"    Size: {file_info['file_size'] / (1024*1024):.2f} MB")

            # Download with progress bar
            await self.client.download_media(
                message.media,
                file=str(file_path)
            )

            if file_path.exists():
                print(f"  ✓ Downloaded successfully")
                return file_path
            else:
                print(f"  ✗ Download failed - file not found")
                return None

        except Exception as e:
            print(f"  ✗ Download error: {e}")
            return None

    async def upload_file(self, file_path: Path, caption: Optional[str], dest_entity) -> bool:
        """Upload file to destination channel."""
        try:
            print(f"  ⬆ Uploading to destination channel...")

            await self.client.send_file(
                dest_entity,
                file=str(file_path),
                caption=caption
            )

            print(f"  ✓ Uploaded successfully")
            return True

        except FloodWaitError as e:
            print(f"  ⚠ Rate limit hit. Waiting {e.seconds} seconds...")
            await asyncio.sleep(e.seconds)
            return await self.upload_file(file_path, caption, dest_entity)

        except Exception as e:
            print(f"  ✗ Upload error: {e}")
            return False

    def cleanup_file(self, file_path: Path):
        """Delete downloaded file to free space."""
        try:
            if file_path.exists():
                file_path.unlink()
                print(f"  🗑 Deleted local file")
        except Exception as e:
            print(f"  ⚠ Could not delete file: {e}")

    async def transfer_all(self):
        """Main transfer loop."""
        source_entity = await self.get_channel_info(self.config.get("source_channel"))
        dest_entity = await self.get_channel_info(self.config.get("destination_channel"))

        if not source_entity or not dest_entity:
            print("\n✗ Could not access one or both channels. Exiting.")
            return

        print(f"\n✓ Source: {getattr(source_entity, 'title', source_entity.id)}")
        print(f"✓ Destination: {getattr(dest_entity, 'title', dest_entity.id)}")

        # Count total media
        total_media = await self.count_media_messages(source_entity)
        print(f"\n✓ Found {total_media} media files")

        # Check for resume
        stats = self.progress.get_stats()
        if stats["processed"] > 0:
            print(f"\n⟳ Resuming from previous session")
            print(f"  Already processed: {stats['processed']} files")
            print(f"  Failed: {stats['failed']} files")
            print(f"  Total transferred: {stats['total_size_mb']} MB")

        print("\n" + "="*60)
        print("Starting transfer...")
        print("="*60 + "\n")

        delay = self.config.get("delay_between_files", 2)
        processed_in_session = 0

        # Iterate through all messages
        async for message in self.client.iter_messages(source_entity, reverse=True):
            # Skip if already processed
            if self.progress.is_processed(message.id):
                continue

            # Skip non-media messages
            if not message.media:
                self.progress.mark_skipped(message.id)
                continue

            # Get file info
            file_info = self.get_file_info(message)
            if not file_info:
                self.progress.mark_skipped(message.id)
                continue

            # Check file size limit
            max_size_mb = self.config.get("max_file_size_mb", 2000)
            file_size_mb = file_info["file_size"] / (1024 * 1024)
            if file_size_mb > max_size_mb:
                print(f"\n⊘ Skipping (too large): {file_info['file_name']} ({file_size_mb:.2f} MB)")
                self.progress.mark_skipped(message.id)
                continue

            print(f"\n[{processed_in_session + 1}/{total_media - stats['processed']}] Processing message {message.id}")

            # Download
            file_path = await self.download_file(message, file_info)
            if not file_path:
                self.progress.mark_failed(message.id)
                continue

            # Upload
            upload_success = await self.upload_file(
                file_path,
                file_info["caption"],
                dest_entity
            )

            # Cleanup
            self.cleanup_file(file_path)

            # Update progress
            if upload_success:
                self.progress.mark_processed(message.id, file_size_mb)
                processed_in_session += 1
            else:
                self.progress.mark_failed(message.id)

            # Rate limiting delay
            if delay > 0:
                print(f"  ⏱ Waiting {delay} seconds...")
                await asyncio.sleep(delay)

        # Final statistics
        final_stats = self.progress.get_stats()
        print("\n" + "="*60)
        print("TRANSFER COMPLETE")
        print("="*60)
        print(f"\n✓ Total processed: {final_stats['processed']} files")
        print(f"✓ Total size: {final_stats['total_size_mb']} MB")
        print(f"⚠ Failed: {final_stats['failed']} files")
        print(f"⊘ Skipped: {final_stats['skipped']} files")
        print(f"\nProgress saved to: {self.progress.progress_path}")
        print()

    async def run(self):
        """Run the transfer process."""
        try:
            if not await self.initialize():
                return

            await self.transfer_all()

        except KeyboardInterrupt:
            print("\n\n⚠ Transfer interrupted by user")
            print(f"Progress saved. Run again to resume.")

        except Exception as e:
            print(f"\n✗ Unexpected error: {e}")
            import traceback
            traceback.print_exc()

        finally:
            if self.client:
                await self.client.disconnect()
                print("\n✓ Disconnected from Telegram\n")


async def main():
    """Main entry point."""
    print("\n╔════════════════════════════════════════════════════════════╗")
    print("║    TELEGRAM CHANNEL MEDIA TRANSFER TOOL                    ║")
    print("║    Low Storage VPS Optimized                               ║")
    print("╚════════════════════════════════════════════════════════════╝")

    # Load configuration
    config = Config()

    # Create and run transfer
    transfer = TelegramTransfer(config)
    await transfer.run()


if __name__ == "__main__":
    # Run async main
    asyncio.run(main())
