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

from telethon import TelegramClient
from telethon.tl.types import DocumentAttributeFilename, Message
from telethon.errors import FloodWaitError, ChannelPrivateError
import re


class Config:
    """Configuration manager with interactive setup."""

    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = self._load_or_create_config()

    def _load_or_create_config(self) -> Dict:
        """Load existing config or create new one interactively."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    # Validate required fields
                    required_fields = ['api_id', 'api_hash', 'source_channel', 'destination_channel']
                    # Phone is only required if login_method is 'phone' or not specified
                    login_method = config.get('login_method', 'phone')
                    if login_method == 'phone' and 'phone' not in config:
                        print(f"⚠ Config file is missing phone number for phone login. Starting fresh setup.")
                        return self._interactive_setup()
                    if all(field in config for field in required_fields):
                        return config
                    else:
                        print(f"⚠ Config file is missing required fields. Starting fresh setup.")
                        return self._interactive_setup()
            except json.JSONDecodeError:
                print(f"⚠ Config file is corrupted. Starting fresh setup.")
                return self._interactive_setup()
        else:
            return self._interactive_setup()

    def _interactive_setup(self) -> Dict:
        """Interactive configuration setup."""
        print("\n" + "="*60)
        print("TELEGRAM CHANNEL TRANSFER - FIRST TIME SETUP")
        print("="*60 + "\n")

        print("First, you need API credentials from https://my.telegram.org")
        print("Go to 'API Development Tools' and create an application.\n")

        # Validate API ID (must be numeric)
        while True:
            api_id = input("Enter your API ID: ").strip()
            if api_id.isdigit():
                break
            print("  ✗ API ID must be a number. Please try again.")

        api_hash = input("Enter your API Hash: ").strip()

        # Choose login method
        print("\n" + "-"*60)
        print("Authentication Method")
        print("-"*60 + "\n")
        print("Choose how to log in to Telegram:")
        print("  1. Phone Number (traditional SMS/call verification)")
        print("  2. QR Code (scan with Telegram mobile app)\n")

        login_method = "phone"  # default
        phone = ""

        while True:
            choice = input("Enter your choice (1 or 2) [default: 1]: ").strip()
            if not choice or choice == "1":
                login_method = "phone"
                phone = input("Enter your phone number (with country code, e.g., +1234567890): ").strip()
                break
            elif choice == "2":
                login_method = "qr"
                print("✓ QR code login selected. You'll scan a QR code when the script starts.")
                break
            else:
                print("  ✗ Invalid choice. Please enter 1 or 2.")

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

        # Validate delay input
        while True:
            delay_input = input("Delay between files in seconds [default: 2]: ").strip()
            if not delay_input:
                delay = 2
                break
            try:
                delay = int(delay_input)
                if delay >= 0:
                    break
                print("  ✗ Delay must be a positive number. Please try again.")
            except ValueError:
                print("  ✗ Invalid number. Please try again.")

        preserve = input("Preserve original captions? (yes/no) [default: yes]: ").strip().lower()
        preserve_captions = preserve != 'no'

        copy_text = input("Copy text messages too? (yes/no) [default: yes]: ").strip().lower()
        copy_text_messages = copy_text != 'no'

        download_path = input("Download path [default: ./temp_downloads]: ").strip()
        download_path = download_path if download_path else "./temp_downloads"

        config = {
            "api_id": api_id,
            "api_hash": api_hash,
            "login_method": login_method,
            "phone": phone,  # Empty string if QR code login
            "source_channel": source_channel,
            "destination_channel": destination_channel,
            "delay_between_files": delay,
            "preserve_captions": preserve_captions,
            "copy_text_messages": copy_text_messages,
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
            try:
                with open(self.progress_path, 'r') as f:
                    data = json.load(f)
                    # Ensure processed_ids exists for backward compatibility
                    if "processed_ids" not in data:
                        data["processed_ids"] = []
                    return data
            except json.JSONDecodeError:
                print(f"⚠ Progress file is corrupted. Starting fresh.")
                # Backup corrupted file
                backup_path = f"{self.progress_path}.backup"
                os.rename(self.progress_path, backup_path)
                print(f"  Old progress backed up to: {backup_path}")

        return {
            "last_message_id": 0,
            "processed_count": 0,
            "processed_ids": [],  # Track actual processed message IDs
            "text_messages_copied": 0,  # Track text-only messages
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
        if message_id not in self.data.get("processed_ids", []):
            self.data.setdefault("processed_ids", []).append(message_id)
            self.data["processed_count"] += 1
        self.data["last_message_id"] = max(self.data["last_message_id"], message_id)
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

    def mark_text_copied(self, message_id: int):
        """Mark a text message as copied."""
        if message_id not in self.data.get("processed_ids", []):
            self.data.setdefault("processed_ids", []).append(message_id)
            self.data.setdefault("text_messages_copied", 0)
            self.data["text_messages_copied"] += 1
        self.data["last_message_id"] = max(self.data["last_message_id"], message_id)
        self.save()

    def is_processed(self, message_id: int) -> bool:
        """Check if message was already processed."""
        # Check in processed_ids list (more accurate) or skipped_ids
        return (message_id in self.data.get("processed_ids", []) or
                message_id in self.data.get("skipped_ids", []))

    def get_stats(self) -> Dict:
        """Get current statistics."""
        return {
            "processed": self.data["processed_count"],
            "text_copied": self.data.get("text_messages_copied", 0),
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

        await self.client.connect()

        # Check if already authorized
        if await self.client.is_user_authorized():
            me = await self.client.get_me()
            print(f"✓ Already authenticated as: {me.first_name} ({me.phone})")
            return True

        # Authenticate based on login method
        login_method = self.config.get("login_method", "phone")

        if login_method == "qr":
            print("QR Code Login Selected")
            print("-" * 60)
            print("\nGenerating QR code for login...")
            print("Open Telegram on your mobile device and scan the QR code:\n")

            try:
                # Use QR code login
                qr_login = await self.client.qr_login()

                # Display QR code
                print("  Scan this QR code with your Telegram mobile app:")
                print("  (Settings > Devices > Link Desktop Device)\n")

                # Generate a simple text-based QR code representation
                try:
                    # Try to display as link
                    import qrcode
                    qr = qrcode.QRCode(version=1, box_size=1, border=1)
                    qr.add_data(qr_login.url)
                    qr.make(fit=True)
                    qr.print_ascii(invert=True)
                except ImportError:
                    # Fallback: just show the URL
                    print(f"  QR Code URL: {qr_login.url}\n")
                    print("  You can:")
                    print("  1. Scan the URL above with a QR code app, then open in Telegram")
                    print("  2. Visit https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=" + qr_login.url)
                    print("     and scan the QR code displayed\n")

                print("\n  Waiting for you to scan the QR code...")

                # Wait for login
                await qr_login.wait()

                # Verify authorization
                if await self.client.is_user_authorized():
                    me = await self.client.get_me()
                    print(f"\n✓ Successfully authenticated as: {me.first_name}")
                    return True
                else:
                    print("\n✗ QR code authentication failed")
                    return False

            except Exception as e:
                print(f"\n✗ QR code login error: {e}")
                print("  Try using phone number login instead.")
                return False

        else:
            # Traditional phone number login
            phone = self.config.get("phone")
            if not phone:
                print("✗ Phone number not configured")
                return False

            try:
                await self.client.start(phone=phone)

                if await self.client.is_user_authorized():
                    me = await self.client.get_me()
                    print(f"✓ Authenticated as: {me.first_name} ({me.phone})")
                    return True
                else:
                    print("✗ Authentication failed")
                    return False

            except Exception as e:
                print(f"✗ Phone login error: {e}")
                return False

    def sanitize_filename(self, filename: str) -> str:
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

    async def count_media_messages(self, source_entity, limit: int = 100) -> int:
        """Count total media messages in source channel (limited for performance)."""
        print("\nEstimating media files in source channel...")
        count = 0
        async for message in self.client.iter_messages(source_entity, limit=limit):
            if message.media:
                count += 1
        return count

    def cleanup_orphaned_files(self):
        """Clean up any orphaned files from previous interrupted runs."""
        if not self.download_path.exists():
            return

        files = list(self.download_path.glob('*'))
        if files:
            print(f"\n⚠ Found {len(files)} orphaned files from previous run")
            for file_path in files:
                try:
                    file_path.unlink()
                    print(f"  🗑 Deleted: {file_path.name}")
                except Exception as e:
                    print(f"  ⚠ Could not delete {file_path.name}: {e}")

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
                # Safely extract file size
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
                    file_info["file_name"] = self.sanitize_filename(attr.file_name)
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
            file_info["file_name"] = self.sanitize_filename(file_info["file_name"])

        return file_info

    async def download_file(self, message: Message, file_info: Dict) -> Optional[Path]:
        """Download a single file."""
        base_name = file_info["file_name"]
        file_path = self.download_path / base_name

        # Handle duplicate filenames
        counter = 1
        while file_path.exists():
            name, ext = os.path.splitext(base_name)
            file_path = self.download_path / f"{name}_{counter}{ext}"
            counter += 1

        try:
            print(f"  ⬇ Downloading: {file_path.name}")
            print(f"    Size: {file_info['file_size'] / (1024*1024):.2f} MB")

            # Download with progress bar
            await self.client.download_media(
                message.media,
                file=str(file_path)
            )

            # Verify file was downloaded and has content
            if file_path.exists() and file_path.stat().st_size > 0:
                print(f"  ✓ Downloaded successfully")
                return file_path
            else:
                print(f"  ✗ Download failed - file not found or empty")
                # Clean up empty file if it exists
                if file_path.exists():
                    file_path.unlink()
                return None

        except Exception as e:
            print(f"  ✗ Download error: {e}")
            # Clean up partial download
            if file_path.exists():
                try:
                    file_path.unlink()
                except:
                    pass
            return None

    async def upload_file(self, file_path: Path, caption: Optional[str], dest_entity, retry_count: int = 0) -> bool:
        """Upload file to destination channel."""
        max_retries = 3

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
            if retry_count >= max_retries:
                print(f"  ✗ Max retries reached for rate limiting")
                return False

            wait_time = min(e.seconds, 300)  # Cap wait at 5 minutes
            print(f"  ⚠ Rate limit hit. Waiting {wait_time} seconds...")
            await asyncio.sleep(wait_time)
            return await self.upload_file(file_path, caption, dest_entity, retry_count + 1)

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

    async def copy_text_message(self, message: Message, dest_entity, retry_count: int = 0) -> bool:
        """Copy text-only message to destination channel."""
        max_retries = 3

        try:
            print(f"  📝 Copying text message...")

            # Send message text to destination
            await self.client.send_message(
                dest_entity,
                message.message
            )

            print(f"  ✓ Text copied successfully")
            return True

        except FloodWaitError as e:
            if retry_count >= max_retries:
                print(f"  ✗ Max retries reached for rate limiting")
                return False

            wait_time = min(e.seconds, 300)  # Cap wait at 5 minutes
            print(f"  ⚠ Rate limit hit. Waiting {wait_time} seconds...")
            await asyncio.sleep(wait_time)
            return await self.copy_text_message(message, dest_entity, retry_count + 1)

        except Exception as e:
            print(f"  ✗ Text copy error: {e}")
            return False

    async def transfer_all(self):
        """Main transfer loop."""
        # Clean up any orphaned files from previous interrupted runs
        self.cleanup_orphaned_files()

        source_entity = await self.get_channel_info(self.config.get("source_channel"))
        dest_entity = await self.get_channel_info(self.config.get("destination_channel"))

        if not source_entity or not dest_entity:
            print("\n✗ Could not access one or both channels. Exiting.")
            return

        print(f"\n✓ Source: {getattr(source_entity, 'title', source_entity.id)}")
        print(f"✓ Destination: {getattr(dest_entity, 'title', dest_entity.id)}")

        # Estimate media count (limited to avoid long delays)
        estimated_count = await self.count_media_messages(source_entity, limit=100)
        print(f"\n✓ Estimated media files: ~{estimated_count} (sampled from recent 100 messages)")

        # Check for resume
        stats = self.progress.get_stats()
        if stats["processed"] > 0 or stats.get("text_copied", 0) > 0:
            print(f"\n⟳ Resuming from previous session")
            print(f"  Already processed: {stats['processed']} media files")
            if stats.get("text_copied", 0) > 0:
                print(f"  Text messages copied: {stats['text_copied']}")
            print(f"  Failed: {stats['failed']} messages")
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

            # Handle text-only messages
            if not message.media:
                # Check if we should copy text messages
                if self.config.get("copy_text_messages", True) and message.message:
                    print(f"\n[Text Message {message.id}] Copying text...")

                    # Copy text message
                    copy_success = await self.copy_text_message(message, dest_entity)

                    if copy_success:
                        self.progress.mark_text_copied(message.id)
                    else:
                        self.progress.mark_failed(message.id)

                    # Rate limiting delay
                    if delay > 0:
                        print(f"  ⏱ Waiting {delay} seconds...")
                        await asyncio.sleep(delay)
                else:
                    # Skip text messages if not configured to copy
                    self.progress.mark_skipped(message.id)
                continue

            # Get file info for media messages
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

            print(f"\n[{stats['processed'] + processed_in_session + 1}] Processing message {message.id}")

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
        print(f"\n✓ Total media files: {final_stats['processed']}")
        print(f"✓ Total size: {final_stats['total_size_mb']} MB")
        if final_stats.get('text_copied', 0) > 0:
            print(f"✓ Text messages copied: {final_stats['text_copied']}")
        print(f"⚠ Failed: {final_stats['failed']} messages")
        print(f"⊘ Skipped: {final_stats['skipped']} messages")
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
