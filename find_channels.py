#!/usr/bin/env python3
"""
Simple script to find and list your Telegram channels
No config.json needed - prompts for credentials
"""
import asyncio
from telethon import TelegramClient
from telethon.tl.types import Channel

async def main():
    print("\n" + "="*80)
    print("TELEGRAM CHANNEL FINDER")
    print("="*80 + "\n")

    print("This script will list all channels/groups you have access to.")
    print("You'll need your API credentials from https://my.telegram.org\n")

    # Get credentials
    api_id = input("Enter your API ID: ").strip()
    api_hash = input("Enter your API Hash: ").strip()

    # Create client
    client = TelegramClient('temp_session', int(api_id), api_hash)

    print("\nConnecting to Telegram...")
    print("You'll need to authenticate if not already logged in.\n")

    await client.start()

    if not await client.is_user_authorized():
        print("Authentication required. Please check your device for verification code.")
    else:
        me = await client.get_me()
        print(f"✓ Logged in as: {me.first_name}\n")

    print("\n" + "="*80)
    print("SCANNING YOUR CHANNELS AND GROUPS...")
    print("="*80 + "\n")

    channels = []
    supergroups = []
    private_groups = []

    async for dialog in client.iter_dialogs():
        entity = dialog.entity

        if isinstance(entity, Channel):
            info = {
                'title': dialog.title,
                'id': entity.id,
                'username': entity.username,
                'is_broadcast': entity.broadcast,
                'megagroup': entity.megagroup
            }

            if entity.broadcast:
                channels.append(info)
            elif entity.megagroup:
                supergroups.append(info)
            else:
                private_groups.append(info)

    # Display results
    print(f"\n{'='*80}")
    print(f"CHANNELS (Broadcast channels you can use): {len(channels)}")
    print(f"{'='*80}\n")

    if channels:
        for i, ch in enumerate(channels, 1):
            print(f"{i}. {ch['title']}")
            print(f"   Channel ID: {ch['id']}")
            if ch['username']:
                print(f"   Username: @{ch['username']}")
                print(f"   ✓ Use in config: @{ch['username']}")
            else:
                print(f"   ✓ Use in config: {ch['id']}")
            print()
    else:
        print("No broadcast channels found.")
        print("Note: You need to be a member of channels to see them here.\n")

    print(f"\n{'='*80}")
    print(f"SUPERGROUPS (Groups that might work): {len(supergroups)}")
    print(f"{'='*80}\n")

    if supergroups:
        for i, gr in enumerate(supergroups[:10], 1):  # Show first 10
            print(f"{i}. {gr['title']}")
            print(f"   Group ID: {gr['id']}")
            if gr['username']:
                print(f"   Username: @{gr['username']}")
                print(f"   ✓ Use in config: @{gr['username']}")
            else:
                print(f"   ✓ Use in config: {gr['id']}")
            print()
        if len(supergroups) > 10:
            print(f"... and {len(supergroups) - 10} more supergroups\n")

    print("\n" + "="*80)
    print("INSTRUCTIONS:")
    print("="*80)
    print("\n1. Find your SOURCE channel (where you want to copy FROM)")
    print("2. Find your DESTINATION channel (where you want to copy TO)")
    print("3. Copy the 'Use in config' value for each")
    print("4. Run: python3 transfer.py")
    print("5. Enter those values when prompted")
    print("\nIMPORTANT:")
    print("- You must be a MEMBER of the source channel")
    print("- You must be an ADMIN of the destination channel")
    print("- Private channels show as IDs (numbers)")
    print("- Public channels show as @usernames (easier to use)\n")

    await client.disconnect()
    print("✓ Disconnected\n")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nCancelled by user\n")
    except Exception as e:
        print(f"\n✗ Error: {e}\n")
