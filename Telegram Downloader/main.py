from telethon.sync import TelegramClient
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
import os

# Replace these with your own values
api_id = 1234567        # from https://my.telegram.org
api_hash = 'your_api_hash'
phone = '+1234567890'   # your phone number with country code
group_username = 'group_username_or_id'  # Can be @groupname or ID

# Create folder to save media
os.makedirs("downloads", exist_ok=True)

with TelegramClient('session_name', api_id, api_hash) as client:
    # Join group by username (if you're not in already and it's public)
    # client(JoinChannelRequest(group_username))

    for message in client.iter_messages(group_username, limit=100):  # adjust limit as needed
        if message.media:
            try:
                client.download_media(message, file="downloads/")
                print(f"Downloaded: {message.id}")
            except Exception as e:
                print(f"Failed to download {message.id}: {e}")
