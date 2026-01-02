#!/usr/bin/env python3
"""
Telegram Video Downloader - Optimized version with ID file as single source of truth
The ID file (all_image_ids.txt) is the ONLY resource to track download status
Format: #123456 = downloaded, 123456 = pending
"""

import os
import json
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple
from datetime import datetime
from telethon import TelegramClient, types
from telethon.errors import FloodWaitError, MessageIdInvalidError, ChannelPrivateError
import time
import random
import sys
import shutil
from contextlib import suppress

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('video_downloader.log', encoding='utf-8', delay=True),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Suppress noisy telethon logs
telethon_logger = logging.getLogger('telethon')
telethon_logger.setLevel(logging.WARNING)

class VideoDownloader:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = Path(config_path)
        self.load_config()
        
        # Initialize paths
        self.ids_file = Path("all_image_ids.txt")
        self.download_path = Path("downloaded_videos")
        self.download_path.mkdir(exist_ok=True)
        
        # Progress tracking - only from ID file
        self.downloaded_ids: Set[int] = set()
        
        # Telegram client
        self.client = None
        self.channel_entity = None
        
        # Optimizations
        self._current_batch_folder = None
        self._folder_video_count = 0
        self._batch_size = 100
        self._concurrent_downloads = 5
        self._semaphore = asyncio.Semaphore(self._concurrent_downloads)
        self._video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv'}
        
        # Load existing progress from ID file only
        self.load_progress()
    
    def load_config(self):
        """Load configuration from config.json"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            self.api_id = config.get("api_id")
            self.api_hash = config.get("api_hash")
            
            if not self.api_id or not self.api_hash:
                raise ValueError("API ID or API Hash not found in config.json")
                
            logger.info("✓ Configuration loaded")
            
        except FileNotFoundError:
            logger.error(f"❌ Config file not found: {self.config_path}")
            print(f"\n❌ ERROR: config.json file not found!")
            print("Please create config.json with your Telegram API credentials:")
            print('''
{
    "api_id": "YOUR_API_ID",
    "api_hash": "YOUR_API_HASH",
    "session_name": "video_session"
}
''')
            sys.exit(1)
        except Exception as e:
            logger.error(f"❌ Error loading config: {e}")
            sys.exit(1)
    
    def load_progress(self):
        """Load progress from ID file only - this is the single source of truth"""
        self.downloaded_ids = set()
        
        if self.ids_file.exists():
            with open(self.ids_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('#'):
                        try:
                            vid = int(line[1:])
                            self.downloaded_ids.add(vid)
                        except ValueError:
                            # Skip invalid lines
                            continue
            
            logger.info(f"✓ Progress from ID file: {len(self.downloaded_ids)} downloaded IDs")
    
    def save_progress(self):
        """No longer save progress to external files - ID file is the only source"""
        # Just log current state
        logger.debug(f"Current state: {len(self.downloaded_ids)} downloaded (from ID file)")
    
    def get_pending_ids(self) -> List[int]:
        """Get list of IDs that need to be downloaded - based ONLY on ID file"""
        if not self.ids_file.exists():
            logger.error(f"❌ ID file not found: {self.ids_file}")
            print(f"\n❌ ERROR: all_image_ids.txt file not found!")
            print("Please run the ID scanner first to generate the ID list.")
            sys.exit(1)
        
        pending_ids = []
        
        # Read IDs from file
        with open(self.ids_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                # Handle commented lines (already downloaded)
                if line.startswith('#'):
                    try:
                        vid = int(line[1:])
                        # Already in downloaded_ids set from load_progress
                    except ValueError:
                        continue
                else:
                    try:
                        vid = int(line)
                        # Only add if not already marked as downloaded in ID file
                        if vid not in self.downloaded_ids:
                            pending_ids.append(vid)
                    except ValueError:
                        continue
        
        logger.info(f"✓ Pending IDs: {len(pending_ids)}")
        logger.info(f"✓ Already downloaded (from ID file): {len(self.downloaded_ids)}")
        
        return sorted(pending_ids)
    
    async def connect_to_telegram(self, session_name: str = "video_session"):
        """Connect to Telegram"""
        try:
            logger.info("Connecting to Telegram...")
            
            self.client = TelegramClient(
                session_name,
                self.api_id,
                self.api_hash,
                connection_retries=3,
                request_retries=3
            )
            
            await self.client.start()
            logger.info("✓ Connected to Telegram")
            
            me = await self.client.get_me()
            logger.info(f"✓ Logged in as: {me.username or me.first_name}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to connect: {e}")
            print(f"\n❌ CONNECTION ERROR: {e}")
            return False
    
    async def get_channel(self, channel_input: str):
        """Get channel entity"""
        try:
            logger.info(f"Getting channel: {channel_input}")
            self.channel_entity = await self.client.get_entity(channel_input)
            logger.info(f"✓ Channel: {self.channel_entity.title}")
            return True
        except Exception as e:
            logger.error(f"❌ Error getting channel: {e}")
            print(f"\n❌ CHANNEL ERROR: {e}")
            return False
    
    def get_current_batch_folder(self) -> Path:
        """Get or create current batch folder"""
        if self._current_batch_folder and self._folder_video_count < self._batch_size:
            return self._current_batch_folder
        
        # Find existing batch folders
        batch_folders = []
        for folder in self.download_path.iterdir():
            if folder.is_dir() and folder.name.startswith("batch_"):
                try:
                    batch_num = int(folder.name.split('_')[1])
                    batch_folders.append((batch_num, folder))
                except (ValueError, IndexError):
                    continue
        
        if not batch_folders:
            new_folder = self.download_path / "batch_001"
            new_folder.mkdir(exist_ok=True)
            logger.info(f"Created: {new_folder.name}")
            self._current_batch_folder = new_folder
            self._folder_video_count = 0
            return new_folder
        
        batch_folders.sort(key=lambda x: x[0])
        last_num, last_folder = batch_folders[-1]
        
        # Count videos in last folder
        video_count = 0
        for ext in self._video_extensions:
            video_count += len(list(last_folder.glob(f"*{ext}")))
        
        if video_count < self._batch_size:
            logger.info(f"Using: {last_folder.name} ({video_count}/{self._batch_size})")
            self._current_batch_folder = last_folder
            self._folder_video_count = video_count
            return last_folder
        else:
            new_num = last_num + 1
            new_folder = self.download_path / f"batch_{new_num:03d}"
            new_folder.mkdir(exist_ok=True)
            logger.info(f"Created: {new_folder.name}")
            self._current_batch_folder = new_folder
            self._folder_video_count = 0
            return new_folder
    
    def update_id_file(self, video_id: int):
        """Update the ID file with # prefix for downloaded IDs"""
        try:
            # Read all lines
            with open(self.ids_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Find and update the line
            updated = False
            for i, line in enumerate(lines):
                line_stripped = line.strip()
                if line_stripped and not line_stripped.startswith('#'):
                    try:
                        vid = int(line_stripped)
                        if vid == video_id:
                            lines[i] = f"#{video_id}\n"
                            updated = True
                            break
                    except ValueError:
                        continue
            
            # Write back
            with open(self.ids_file, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            
            if updated:
                logger.debug(f"Updated ID file for {video_id}")
                # Add to downloaded set
                self.downloaded_ids.add(video_id)
            else:
                # Check if already marked
                for i, line in enumerate(lines):
                    if line.strip() == f"#{video_id}":
                        logger.debug(f"ID {video_id} already marked in file")
                        self.downloaded_ids.add(video_id)
                        return
                
                logger.warning(f"ID {video_id} not found in ID file")
                
        except Exception as e:
            logger.error(f"Error updating ID file for {video_id}: {e}")
    
    def check_id_file_status(self, video_id: int) -> bool:
        """Check if video_id is marked as downloaded in ID file"""
        try:
            with open(self.ids_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line == f"#{video_id}":
                        return True
            return False
        except Exception:
            return False
    
    async def download_single_video(self, video_id: int, folder: Path, total_num: int, current_num: int) -> Tuple[bool, str]:
        """Download a single video with progress bar"""
        max_retries = 2
        retry_delay = 3
        
        async with self._semaphore:
            for attempt in range(max_retries):
                try:
                    # FIRST: Double-check ID file to ensure video hasn't been marked as downloaded
                    # by another process or during this session
                    if self.check_id_file_status(video_id):
                        # Already marked as downloaded in ID file
                        if video_id not in self.downloaded_ids:
                            self.downloaded_ids.add(video_id)
                        self._folder_video_count += 1
                        return True, f"Already marked as downloaded in ID file"
                    
                    # SECOND: Check if already in downloaded set (from earlier in this session)
                    if video_id in self.downloaded_ids:
                        self._folder_video_count += 1
                        return True, f"Already downloaded in this session"
                    
                    # Get message
                    message = await self.client.get_messages(
                        self.channel_entity,
                        ids=video_id
                    )
                    
                    if not message:
                        return False, "Message not found"
                    
                    if not message.media:
                        return False, "No media"
                    
                    # Prepare progress tracking
                    last_update_time = 0
                    progress_interval = 0.5  # Update progress every 0.5 seconds
                    
                    def progress_callback(current, total):
                        nonlocal last_update_time
                        current_time = time.time()
                        if current_time - last_update_time > progress_interval or current == total:
                            percent = (current / total) * 100 if total > 0 else 0
                            bar_length = 30
                            filled = int(bar_length * current // total) if total > 0 else bar_length
                            bar = '█' * filled + '░' * (bar_length - filled)
                            
                            size_info = f"{current/1024/1024:.1f}/{total/1024/1024:.1f} MB" if total > 0 else f"{current/1024/1024:.1f} MB"
                            
                            print(f"\r[{current_num:03d}/{total_num:03d}] {video_id} [{bar}] {percent:.1f}% {size_info}", end='', flush=True)
                            last_update_time = current_time
                    
                    # Download
                    start_time = time.time()
                    filename = folder / f"{video_id}.mp4"
                    
                    try:
                        result = await asyncio.wait_for(
                            self.client.download_media(
                                message,
                                file=filename,
                                progress_callback=progress_callback
                            ),
                            timeout=300
                        )
                    except asyncio.TimeoutError:
                        print(f"\r[{current_num:03d}/{total_num:03d}] {video_id} [░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] Timeout           ")
                        return False, "Timeout"
                    
                    # Verify download
                    if result and Path(result).exists():
                        try:
                            file_size = Path(result).stat().st_size
                            elapsed = time.time() - start_time
                            
                            if file_size > 1024:
                                # SUCCESS: Update ID file IMMEDIATELY
                                self.update_id_file(video_id)
                                self._folder_video_count += 1
                                
                                # Show final progress bar
                                bar = '█' * 30
                                speed = file_size / elapsed / 1024 if elapsed > 0 else 0
                                size_mb = file_size / 1024 / 1024
                                print(f"\r[{current_num:03d}/{total_num:03d}] {video_id} [{bar}] 100.0% {size_mb:.1f}MB in {elapsed:.1f}s ({speed:.0f} KB/s) ✓")
                                
                                return True, f"Downloaded"
                            else:
                                Path(result).unlink(missing_ok=True)
                                print(f"\r[{current_num:03d}/{total_num:03d}] {video_id} [░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] File too small    ")
                                return False, "File too small"
                        except OSError:
                            print(f"\r[{current_num:03d}/{total_num:03d}] {video_id} [░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] File error        ")
                            return False, "File error"
                    else:
                        print(f"\r[{current_num:03d}/{total_num:03d}] {video_id} [░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] Download failed   ")
                        return False, "Download failed"
                        
                except FloodWaitError as e:
                    wait_time = min(e.seconds + 5, 60)
                    print(f"\r[{current_num:03d}/{total_num:03d}] {video_id} [░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] Flood wait: {wait_time}s")
                    await asyncio.sleep(wait_time)
                    continue
                    
                except (MessageIdInvalidError, ChannelPrivateError) as e:
                    error_msg = str(e)[:30]
                    print(f"\r[{current_num:03d}/{total_num:03d}] {video_id} [░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] {error_msg}")
                    return False, f"Error: {e}"
                    
                except Exception as e:
                    error_msg = str(e)[:30]
                    if attempt < max_retries - 1:
                        delay = retry_delay * (attempt + 1)
                        print(f"\r[{current_num:03d}/{total_num:03d}] {video_id} [░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] Retry in {delay}s")
                        await asyncio.sleep(delay)
                    else:
                        print(f"\r[{current_num:03d}/{total_num:03d}] {video_id} [░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] {error_msg}")
                        return False, f"Failed: {str(e)[:50]}"
            
            print(f"\r[{current_num:03d}/{total_num:03d}] {video_id} [░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] Max retries      ")
            return False, "Max retries"
    
    async def download_videos_parallel(self, video_ids: List[int]):
        """Download multiple videos in parallel"""
        if not video_ids:
            logger.info("No videos to download")
            return
        
        total_videos = len(video_ids)
        downloaded = 0
        failed = 0
        
        logger.info(f"Starting download of {total_videos} videos ({self._concurrent_downloads} concurrent)")
        print(f"\n📥 Downloading {total_videos} videos ({self._concurrent_downloads} at once)...")
        print("=" * 60)
        
        start_time = time.time()
        
        # Process in smaller batches for better progress tracking
        batch_size = self._concurrent_downloads * 2  # 10 videos per batch
        overall_start_time = time.time()
        
        for batch_start in range(0, total_videos, batch_size):
            batch_end = min(batch_start + batch_size, total_videos)
            batch_ids = video_ids[batch_start:batch_end]
            
            # Get current folder for this batch
            current_folder = self.get_current_batch_folder()
            
            # Create download tasks with proper numbering
            tasks = []
            for idx, video_id in enumerate(batch_ids, 1):
                current_num = batch_start + idx
                task = self.download_single_video(video_id, current_folder, total_videos, current_num)
                tasks.append(task)
            
            # Run tasks concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for video_id, result in zip(batch_ids, results):
                if isinstance(result, Exception):
                    failed += 1
                else:
                    success, message = result
                    if success:
                        downloaded += 1
                    else:
                        failed += 1
            
            # Show batch summary
            current_processed = batch_end
            elapsed = time.time() - overall_start_time
            progress_pct = (current_processed / total_videos) * 100
            
            if current_processed > 0:
                avg_speed = downloaded / (elapsed / 60) if elapsed > 0 else 0
                remaining_time = ((total_videos - current_processed) / max(1, current_processed)) * elapsed if current_processed > 0 else 0
                
                print(f"\n📊 Batch complete: {current_processed}/{total_videos} ({progress_pct:.1f}%)")
                print(f"   Speed: {avg_speed:.1f} videos/min | Downloaded: {downloaded} | Failed: {failed}")
                print(f"   Remaining: ~{remaining_time/60:.1f} minutes")
                print("-" * 60)
        
        # Final summary
        total_time = time.time() - start_time
        
        print("\n" + "=" * 60)
        print("🎉 DOWNLOAD COMPLETE!")
        print("=" * 60)
        print(f"Total videos: {total_videos}")
        print(f"✅ Successfully downloaded: {downloaded}")
        print(f"❌ Failed: {failed}")
        
        if downloaded + failed > 0:
            success_rate = (downloaded / (downloaded + failed)) * 100
            print(f"📈 Success rate: {success_rate:.1f}%")
        
        print(f"⏱️  Total time: {total_time/60:.1f} minutes")
        
        if downloaded > 0 and total_time > 0:
            speed = downloaded / (total_time / 60)
            print(f"⚡ Average speed: {speed:.1f} videos/minute")
        
        # Create summary
        self.create_summary(downloaded, failed, total_time)
    
    def create_summary(self, downloaded: int, failed: int, total_time: float):
        """Create summary file"""
        try:
            summary_file = self.download_path / "download_summary.txt"
            
            summary = f"""=== VIDEO DOWNLOAD SUMMARY ===
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

STATISTICS:
Total videos attempted: {downloaded + failed}
Successfully downloaded: {downloaded}
Failed downloads: {failed}
Success rate: {((downloaded/(downloaded+failed))*100):.1f}% if downloaded+failed > 0 else 0%

PERFORMANCE:
Total download time: {total_time/60:.1f} minutes
Average time per video: {total_time/(downloaded+failed):.1f} seconds if downloaded+failed > 0 else 0
Average speed: {downloaded/(total_time/60):.1f} videos/minute if total_time > 0 else 0
Concurrent downloads: {self._concurrent_downloads}

TRACKING METHOD:
- ID file (all_image_ids.txt) is the ONLY source of truth
- Downloaded IDs are prefixed with # in the ID file
- No external progress files are used
- Script always checks ID file before downloading

FILES:
ID list: {self.ids_file}
Download folder: {self.download_path}/
Log file: video_downloader.log

NOTES:
- Run 'python {sys.argv[0]} check' to verify ID file status
- Run 'python {sys.argv[0]} clean' to clean and verify ID file
- Check video_downloader.log for detailed error messages
"""
            
            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write(summary)
            
            logger.info(f"Summary saved to: {summary_file}")
            
        except Exception as e:
            logger.error(f"Error creating summary: {e}")
    
    async def run(self):
        """Main download process"""
        print("\n" + "=" * 60)
        print("📹 TELEGRAM VIDEO DOWNLOADER")
        print("=" * 60)
        print("ID file is the ONLY source of truth")
        print("#123456 = downloaded, 123456 = pending")
        print("=" * 60)
        
        # Get pending IDs from ID file only
        pending_ids = self.get_pending_ids()
        
        if not pending_ids:
            print("✅ All videos already downloaded (based on ID file)!")
            print(f"   Downloaded: {len(self.downloaded_ids)}")
            return
        
        print(f"\n📊 Found {len(pending_ids)} videos to download")
        print(f"📊 Already downloaded (from ID file): {len(self.downloaded_ids)}")
        print(f"⚡ Concurrent downloads: {self._concurrent_downloads}")
        
        # Get channel input
        print("\n" + "-" * 60)
        channel_input = input("Enter channel (@username or invite link): ").strip()
        
        if not channel_input:
            print("❌ No channel provided")
            return
        
        # Confirm
        print("\n" + "-" * 60)
        confirm = input(f"Start downloading {len(pending_ids)} videos? (y/N): ").strip().lower()
        
        if confirm != 'y':
            print("❌ Download cancelled")
            return
        
        # Connect to Telegram
        print("\n" + "-" * 60)
        print("🔗 Connecting to Telegram...")
        
        if not await self.connect_to_telegram():
            return
        
        # Get channel
        if not await self.get_channel(channel_input):
            return
        
        # Start download
        print("\n" + "-" * 60)
        print("🚀 Starting download process...")
        print("-" * 60)
        
        try:
            await self.download_videos_parallel(pending_ids)
        except KeyboardInterrupt:
            print("\n\n⚠️  Download interrupted by user")
            print("ID file has been updated for successfully downloaded videos.")
            print("Run the script again to resume.")
        except Exception as e:
            print(f"\n❌ Fatal error: {e}")
            logger.error(f"Fatal error: {e}", exc_info=True)
        finally:
            if self.client:
                await self.client.disconnect()
                print("\n👋 Disconnected from Telegram")

async def main():
    """Main entry point"""
    downloader = VideoDownloader()
    await downloader.run()

def check_id_file():
    """Quick check of ID file status"""
    ids_file = Path("all_image_ids.txt")
    
    if not ids_file.exists():
        print(f"❌ File not found: {ids_file}")
        return
    
    total = 0
    downloaded = 0
    pending = 0
    
    # Also check for duplicates
    seen_ids = set()
    duplicates = set()
    
    with open(ids_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            total += 1
            if line.startswith('#'):
                downloaded += 1
                try:
                    vid = int(line[1:])
                    if vid in seen_ids:
                        duplicates.add(vid)
                    else:
                        seen_ids.add(vid)
                except ValueError:
                    pass
            else:
                pending += 1
                try:
                    vid = int(line)
                    if vid in seen_ids:
                        duplicates.add(vid)
                    else:
                        seen_ids.add(vid)
                except ValueError:
                    pass
    
    print(f"\n📊 ID FILE STATUS: {ids_file}")
    print("=" * 40)
    print(f"Total lines in file: {total}")
    print(f"Downloaded (# prefix): {downloaded}")
    print(f"Pending (no prefix): {pending}")
    
    if total > 0:
        print(f"Completion: {(downloaded/total*100):.1f}%")
    
    print(f"\nUnique IDs found: {len(seen_ids)}")
    
    if duplicates:
        print(f"⚠️  WARNING: {len(duplicates)} duplicate IDs found!")
        print("   Run: python video_downloader.py clean")
    else:
        print("✓ No duplicate IDs found")
    
    # Check for file system consistency
    download_path = Path("downloaded_videos")
    if download_path.exists():
        video_files = []
        for ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv']:
            video_files.extend(download_path.rglob(f"*{ext}"))
        
        print(f"\n📁 Downloaded videos in filesystem: {len(video_files)}")
        
        # Check for videos that are downloaded but not marked in ID file
        downloaded_video_ids = set()
        for video_file in video_files:
            try:
                vid = int(video_file.stem)
                downloaded_video_ids.add(vid)
            except ValueError:
                pass
        
        # IDs marked as downloaded in file
        marked_downloaded = set()
        with open(ids_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('#'):
                    try:
                        vid = int(line[1:])
                        marked_downloaded.add(vid)
                    except ValueError:
                        continue
        
        not_marked = downloaded_video_ids - marked_downloaded
        if not_marked:
            print(f"⚠️  Found {len(not_marked)} downloaded videos NOT marked in ID file")
            print("   Consider running: python video_downloader.py clean")

def verify_and_clean_id_file():
    """Verify ID file and remove any duplicate # marks or empty lines"""
    ids_file = Path("all_image_ids.txt")
    
    if not ids_file.exists():
        print(f"❌ File not found: {ids_file}")
        return
    
    # Create backup first
    backup_file = ids_file.with_suffix('.txt.backup')
    try:
        shutil.copy2(ids_file, backup_file)
        print(f"✓ Backup created: {backup_file}")
    except Exception as e:
        print(f"❌ Failed to create backup: {e}")
        return
    
    # Read and process all IDs
    downloaded_ids = set()
    pending_ids = set()
    all_lines = []
    
    with open(ids_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue  # Skip empty lines
            
            if line.startswith('#'):
                try:
                    vid = int(line[1:])
                    if vid not in downloaded_ids and vid not in pending_ids:
                        downloaded_ids.add(vid)
                        all_lines.append(f"#{vid}\n")
                    else:
                        print(f"  Skipping duplicate: {line}")
                except ValueError:
                    print(f"  Skipping invalid line: {line}")
                    continue
            else:
                try:
                    vid = int(line)
                    if vid not in pending_ids and vid not in downloaded_ids:
                        pending_ids.add(vid)
                        all_lines.append(f"{vid}\n")
                    else:
                        print(f"  Skipping duplicate: {line}")
                except ValueError:
                    print(f"  Skipping invalid line: {line}")
                    continue
    
    # Write back cleaned file
    with open(ids_file, 'w', encoding='utf-8') as f:
        f.writelines(all_lines)
    
    print(f"\n✅ ID File cleaned and verified:")
    print(f"   Downloaded IDs: {len(downloaded_ids)}")
    print(f"   Pending IDs: {len(pending_ids)}")
    print(f"   Total unique IDs: {len(downloaded_ids) + len(pending_ids)}")
    
    # Also check downloaded videos in filesystem
    download_path = Path("downloaded_videos")
    if download_path.exists():
        video_files = []
        for ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv']:
            video_files.extend(download_path.rglob(f"*{ext}"))
        
        actual_downloaded = set()
        for video_file in video_files:
            try:
                vid = int(video_file.stem)
                actual_downloaded.add(vid)
            except ValueError:
                pass
        
        # Find videos that exist but aren't marked
        missing_marks = actual_downloaded - downloaded_ids
        if missing_marks:
            print(f"\n⚠️  Found {len(missing_marks)} downloaded videos not marked in ID file")
            print("   Adding # marks for these videos...")
            
            # Add marks for missing videos
            for vid in sorted(missing_marks):
                if vid in pending_ids:
                    # Update from pending to downloaded
                    all_lines = []
                    with open(ids_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if line == str(vid):
                                all_lines.append(f"#{vid}\n")
                                print(f"     Marked #{vid}")
                            else:
                                all_lines.append(f"{line}\n" if line else "\n")
                    
                    with open(ids_file, 'w', encoding='utf-8') as f:
                        f.writelines(all_lines)
            
            print("   Done!")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "check":
            check_id_file()
        elif sys.argv[1] == "clean":
            verify_and_clean_id_file()
        else:
            print(f"Usage: python {sys.argv[0]} [check|clean]")
            print("\nCommands:")
            print("  check  - Check ID file status")
            print("  clean  - Clean and verify ID file (creates backup)")
            print("  (no arg) - Run downloader")
    else:
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            print("\n\n👋 Program terminated by user")
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")