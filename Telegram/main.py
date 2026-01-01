import os
import re
import json
import asyncio
from pathlib import Path
from typing import Dict

from telethon import TelegramClient
from telethon.tl.types import MessageMediaPhoto, DocumentAttributeVideo
from telethon.errors import FloodWaitError, UserAlreadyParticipantError
from telethon.tl.functions.messages import ImportChatInviteRequest

from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.progress import (
    Progress, BarColumn, TextColumn,
    TimeElapsedColumn, TimeRemainingColumn, TaskProgressColumn
)

# ===================== CONFIG =====================
CONFIG_FILE = "config.json"
SESSION_NAME = "session"
BASE_DOWNLOADS = Path("downloads")
LINKS_FILE = "links.txt"

MAX_PARALLEL_DOWNLOADS = 5
semaphore = asyncio.Semaphore(MAX_PARALLEL_DOWNLOADS)

console = Console()

# ===================== UTILITIES =====================
def load_config() -> Dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_config(api_id: int, api_hash: str):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"api_id": api_id, "api_hash": api_hash}, f, indent=2)

def sanitize_for_fs(name: str) -> str:
    name = re.sub(r"[\\/:*?\"<>|\n\r\t]", "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:80] or "chat"

def choose_chat_folder(chat) -> Path:
    if getattr(chat, "username", None):
        label = f"@{chat.username}"
    elif getattr(chat, "title", None):
        label = chat.title
    else:
        label = f"id_{chat.id}"
    folder = BASE_DOWNLOADS / sanitize_for_fs(label)
    folder.mkdir(parents=True, exist_ok=True)
    return folder

def read_links():
    if not os.path.exists(LINKS_FILE):
        console.print("[red]links.txt not found[/red]")
        return []
    with open(LINKS_FILE, "r", encoding="utf-8") as f:
        return [l.strip() for l in f if l.strip()]

# ===================== MEDIA CHECKERS =====================
def is_photo_message(msg) -> bool:
    return bool(msg and (msg.photo or isinstance(msg.media, MessageMediaPhoto)))

def is_video_message(msg) -> bool:
    if not msg or not msg.media:
        return False
    if getattr(msg, "gif", False) or getattr(msg, "sticker", False):
        return False
    if getattr(msg, "video", None):
        return True
    doc = getattr(msg, "document", None)
    if not doc:
        return False
    return any(isinstance(a, DocumentAttributeVideo) for a in doc.attributes or [])

def build_unique_filename(msg, default_ext=".bin") -> str:
    if msg.file and msg.file.name:
        base = msg.file.name
    else:
        ext = msg.file.ext or default_ext
        base = f"file{ext}"
    return f"msg_{msg.id}_{base}"

# ===================== TELEGRAM =====================
async def resolve_chat(client, chat_query):
    try:
        if "t.me/+" in chat_query or "joinchat" in chat_query:
            invite_hash = chat_query.split("/")[-1].replace("+", "")
            try:
                updates = await client(ImportChatInviteRequest(invite_hash))
                return updates.chats[0]
            except UserAlreadyParticipantError:
                return await client.get_entity(chat_query)
        return await client.get_entity(chat_query)
    except Exception as e:
        console.print(f"[red]Failed to resolve chat: {e}[/red]")
        return None

# ===================== DOWNLOAD =====================
async def download_message(msg, folder: Path):
    try:
        filename = build_unique_filename(msg)
        out_path = folder / filename
        if out_path.exists():
            console.print(f"[yellow]Already exists: {filename}[/yellow]")
            return

        with Progress(
            TextColumn("[bold blue]{task.fields[fn]}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            transient=True,
            console=console,
        ) as progress:
            task = progress.add_task("dl", fn=filename, total=100)
            await msg.download_media(
                file=str(out_path),
                progress_callback=lambda r, t: progress.update(task, completed=r, total=t)
            )

        if msg.message:
            with open(out_path.with_suffix(".txt"), "w", encoding="utf-8") as f:
                f.write(msg.message)

        console.print(f"[green]Downloaded:[/green] {filename}")

    except FloodWaitError as e:
        console.print(f"[yellow]Flood wait {e.seconds}s[/yellow]")
        await asyncio.sleep(e.seconds)
        await download_message(msg, folder)

    except Exception as e:
        console.print(f"[red]Error msg {msg.id}: {e}[/red]")

async def download_message_safe(msg, folder):
    async with semaphore:
        await download_message(msg, folder)

# ===================== MAIN =====================
async def main():
    console.print(Panel.fit("[bold cyan]Telegram Parallel Message Downloader[/bold cyan]"))

    cfg = load_config()
    if not cfg:
        api_id = int(Prompt.ask("Telegram API ID"))
        api_hash = Prompt.ask("Telegram API Hash")
        save_config(api_id, api_hash)
        cfg = {"api_id": api_id, "api_hash": api_hash}

    client = TelegramClient(SESSION_NAME, cfg["api_id"], cfg["api_hash"])
    await client.start()

    chat_query = Prompt.ask("Enter chat username / ID / invite link")
    chat = await resolve_chat(client, chat_query)
    if not chat:
        return

    folder = choose_chat_folder(chat)
    console.print(f"[green]Download folder:[/green] {folder.resolve()}")

    links = read_links()
    if not links:
        return

    # Read all links and filter out already processed ones
    unprocessed_links = []
    for link in links:
        if link.startswith("#"):
            console.print(f"[yellow]Skipping already downloaded:[/yellow] {link}")
        else:
            unprocessed_links.append(link)
    
    if not unprocessed_links:
        console.print("[yellow]All links have already been downloaded![/yellow]")
        await client.disconnect()
        return

    tasks = []

    for link in unprocessed_links:
        try:
            msg_id = int(link.rstrip("/").split("/")[-1])

            async def worker(mid=msg_id, original_link=link):
                msg = await client.get_messages(chat, ids=mid)
                if not msg:
                    return
                if is_photo_message(msg) or is_video_message(msg):
                    await download_message_safe(msg, folder)
                    # Mark as downloaded by adding # to the beginning
                    mark_link_as_downloaded(original_link)

            tasks.append(asyncio.create_task(worker()))

        except Exception:
            console.print(f"[red]Invalid link skipped:[/red] {link}")

    console.print(f"[cyan]Downloading {len(tasks)} messages in parallel...[/cyan]")
    await asyncio.gather(*tasks)

    await client.disconnect()
    console.print("[bold green]Done ✔[/bold green]")

def mark_link_as_downloaded(link):
    """Mark a link as downloaded by adding # to the beginning of the line"""
    try:
        with open(LINKS_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        with open(LINKS_FILE, "w", encoding="utf-8") as f:
            for line in lines:
                if line.strip() == link:
                    # Add # to mark as downloaded
                    f.write(f"#{line}")
                else:
                    f.write(line)
    except Exception as e:
        console.print(f"[red]Error marking link as downloaded: {e}[/red]")

if __name__ == "__main__":
    asyncio.run(main())
