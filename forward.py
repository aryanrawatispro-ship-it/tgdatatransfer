#!/usr/bin/env python3
"""
Fast transfer using message forwarding (no download/upload)
This is MUCH faster than downloading and re-uploading
"""
import asyncio
import json
from telethon import TelegramClient
from telethon.errors import FloodWaitError

async def main():
    # Load config
    with open('config.json', 'r') as f:
        config = json.load(f)

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
    source_id = config['source_channel']
    dest_id = config['destination_channel']

    # Find channels in dialogs
    source_entity = None
    dest_entity = None

    if source_id.lstrip('-').isdigit():
        target_id = int(source_id)
        if str(target_id).startswith('-100'):
            target_id_alt = int(str(target_id)[4:])
        else:
            target_id_alt = target_id

        async for dialog in client.iter_dialogs():
            if dialog.entity.id == target_id or dialog.entity.id == target_id_alt:
                source_entity = dialog.entity
                print(f"✓ Source: {dialog.title}")
                break
    else:
        source_entity = await client.get_entity(source_id)
        print(f"✓ Source: {source_entity.title}")

    if dest_id.lstrip('-').isdigit():
        target_id = int(dest_id)
        if str(target_id).startswith('-100'):
            target_id_alt = int(str(target_id)[4:])
        else:
            target_id_alt = target_id

        async for dialog in client.iter_dialogs():
            if dialog.entity.id == target_id or dialog.entity.id == target_id_alt:
                dest_entity = dialog.entity
                print(f"✓ Destination: {dialog.title}")
                break
    else:
        dest_entity = await client.get_entity(dest_id)
        print(f"✓ Destination: {dest_entity.title}")

    if not source_entity or not dest_entity:
        print("\n✗ Could not find channels")
        return

    print("\n" + "="*60)
    print("FORWARDING MODE - ULTRA FAST")
    print("="*60)
    print("\nThis forwards messages without downloading/uploading.")
    print("Speed: Nearly instant (100x faster than download/upload)\n")

    # Count messages
    print("Counting messages...")
    total = 0
    async for msg in client.iter_messages(source_entity, limit=10000):
        if msg.media or msg.text:
            total += 1

    print(f"Found {total} messages to forward\n")

    choice = input("Start forwarding? (yes/no): ").strip().lower()
    if choice != 'yes':
        print("Cancelled")
        return

    print("\n" + "="*60)
    print("STARTING FORWARD...")
    print("="*60 + "\n")

    # Forward messages
    forwarded = 0
    errors = 0

    async for message in client.iter_messages(source_entity):
        if not message.media and not message.text:
            continue

        try:
            await client.forward_messages(dest_entity, message)
            forwarded += 1
            print(f"✓ Forwarded {forwarded}/{total}", end='\r')

            # Small delay to avoid flood
            await asyncio.sleep(0.1)

        except FloodWaitError as e:
            print(f"\n⚠ Rate limit: waiting {e.seconds} seconds...")
            await asyncio.sleep(e.seconds)
            # Retry
            await client.forward_messages(dest_entity, message)
            forwarded += 1

        except Exception as e:
            errors += 1
            print(f"\n✗ Error forwarding message: {e}")
            continue

    print(f"\n\n{'='*60}")
    print("COMPLETED!")
    print("="*60)
    print(f"✓ Forwarded: {forwarded}")
    print(f"✗ Errors: {errors}")
    print()

    await client.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nCancelled by user\n")
    except Exception as e:
        print(f"\n✗ Error: {e}\n")
        import traceback
        traceback.print_exc()
