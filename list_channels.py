#!/usr/bin/env python3
"""
Helper script to list all accessible Telegram channels/groups
"""
import asyncio
from telethon import TelegramClient
from telethon.tl.types import Channel, Chat

async def list_channels():
    """List all channels the user has access to."""

    # Load config
    import json
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("Error: config.json not found. Run transfer.py first to create it.")
        return

    # Create client
    client = TelegramClient(
        'session',
        int(config.get("api_id")),
        config.get("api_hash")
    )

    await client.connect()

    if not await client.is_user_authorized():
        print("Error: Not authenticated. Run transfer.py first to authenticate.")
        await client.disconnect()
        return

    print("\n" + "="*80)
    print("YOUR ACCESSIBLE CHANNELS AND GROUPS")
    print("="*80 + "\n")

    channels = []
    groups = []

    async for dialog in client.iter_dialogs():
        entity = dialog.entity

        # Channel
        if isinstance(entity, Channel):
            if entity.broadcast:  # It's a channel
                channels.append({
                    'title': dialog.title,
                    'id': entity.id,
                    'username': f"@{entity.username}" if entity.username else "No username (private)",
                    'access_hash': entity.access_hash
                })
            else:  # It's a supergroup
                groups.append({
                    'title': dialog.title,
                    'id': entity.id,
                    'username': f"@{entity.username}" if entity.username else "No username (private)",
                    'access_hash': entity.access_hash
                })

    # Display channels
    print(f"CHANNELS ({len(channels)}):")
    print("-" * 80)
    if channels:
        for i, ch in enumerate(channels, 1):
            print(f"\n{i}. {ch['title']}")
            print(f"   ID: {ch['id']}")
            print(f"   Username: {ch['username']}")
            if ch['username'] != "No username (private)":
                print(f"   Use in config: {ch['username']}")
            else:
                print(f"   Use in config: {ch['id']}")
    else:
        print("   No channels found")

    # Display groups
    print(f"\n\nSUPERGROUPS ({len(groups)}):")
    print("-" * 80)
    if groups:
        for i, gr in enumerate(groups, 1):
            print(f"\n{i}. {gr['title']}")
            print(f"   ID: {gr['id']}")
            print(f"   Username: {gr['username']}")
            if gr['username'] != "No username (private)":
                print(f"   Use in config: {gr['username']}")
            else:
                print(f"   Use in config: {gr['id']}")
    else:
        print("   No supergroups found")

    print("\n" + "="*80)
    print("Copy the 'Use in config' value to your config.json")
    print("="*80 + "\n")

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(list_channels())
