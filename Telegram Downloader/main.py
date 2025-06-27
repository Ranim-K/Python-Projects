# ========================================================
# 🔽 Telegram Downloader 🔽
# 🛠️ Created by Ranim
# 📅 June 2025
# ========================================================

import os
import asyncio
from telethon.sync import TelegramClient
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
from telethon.errors import UsernameInvalidError, ChannelPrivateError
from telethon import functions
from tqdm import tqdm

# 🔐 Your Telegram API credentials
api_id = 1234567
api_hash = 'your_api_hash'

# 📂 Download directory
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# 📦 Estimate file size
def get_file_size(msg):
    if msg.media and isinstance(msg.media, MessageMediaDocument):
        return msg.media.document.size or 0
    return 0

# 🚀 Main script logic
async def main():
    async with TelegramClient('session', api_id, api_hash) as client:
        print("✅ Logged in successfully.")

        # Ask user for target group/channel
        target = input("📌 Enter channel @username or invite link: ").strip()

        # Try to get entity normally, fallback to join invite
        try:
            entity = await client.get_entity(target)
        except ValueError:
            if "joinchat/" in target:
                print("📨 Joining private channel...")
                hash_part = target.split("joinchat/")[-1]
                await client(functions.messages.ImportChatInviteRequest(hash_part))
                entity = await client.get_entity(target)
            else:
                print("❌ Invalid link or username.")
                return
        except UsernameInvalidError:
            print("❌ Invalid username.")
            return
        except ChannelPrivateError:
            print("🔒 Cannot access this private channel/group.")
            return
        except Exception as e:
            print(f"⚠️ Unexpected error: {e}")
            return

        print("📡 Fetching messages...")
        messages = await client.get_messages(entity, limit=None)

        # Filter photos and documents
        media_messages = [msg for msg in messages if msg.media and (isinstance(msg.media, MessageMediaPhoto) or isinstance(msg.media, MessageMediaDocument))]

        total_size = sum(get_file_size(msg) for msg in media_messages)
        total_mb = total_size / (1024 * 1024)

        print(f"\n📊 Total media files found: {len(media_messages)}")
        print(f"💾 Estimated total size: {total_mb:.2f} MB\n")

        if not media_messages:
            print("🚫 No media found.")
            return

        # Let user choose how many to download
        while True:
            try:
                count = int(input(f"🔢 Enter how many files to download (1–{len(media_messages)}): "))
                if 1 <= count <= len(media_messages):
                    break
            except:
                pass
            print("❗ Invalid input. Try again.")

        print("\n⬇️ Starting download...\n")

        # Download with progress bar and per-file logging
        for i, msg in tqdm(enumerate(media_messages[:count]), total=count, desc="Downloading"):
            try:
                path = await client.download_media(msg, file=DOWNLOAD_FOLDER + "/")
                if path:
                    tqdm.write(f"✅ [{i+1}/{count}] Downloaded: {os.path.basename(path)}")
                else:
                    tqdm.write(f"⚠️ [{i+1}/{count}] No file found in message {msg.id}")
            except Exception as e:
                tqdm.write(f"❌ [{i+1}/{count}] Error: {e}")

        print("\n✅ Download complete.")

# 🧠 Run the async loop
if __name__ == "__main__":
    asyncio.run(main())

