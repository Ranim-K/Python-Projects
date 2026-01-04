import instaloader
import os
from pathlib import Path
import json
from datetime import datetime

class InstagramDownloader:
    def __init__(self, username=None, password=None):
        self.L = instaloader.Instaloader(
            download_pictures=True,
            download_videos=True,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,  # No JSON/TXT files
            compress_json=False,
            post_metadata_txt_pattern="",
            storyitem_metadata_txt_pattern="",
            max_connection_attempts=1
        )
        
        # Login if credentials provided
        if username and password:
            try:
                self.L.login(username, password)
                print("✅ Logged in successfully")
            except Exception as e:
                print(f"⚠️  Login failed: {e}")
    
    def download_profile(self, target_username, download_path="instagram_downloads"):
        """Download all posts, stories, and highlights with organized structure"""
        
        # Create main directory
        main_dir = Path(download_path) / target_username
        main_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Get profile
            profile = instaloader.Profile.from_username(self.L.context, target_username)
            print(f"📱 Downloading from: @{profile.username}")
            print(f"📊 Total posts: {profile.mediacount}")
            
            # Download posts
            self._download_posts(profile, main_dir)
            
            # Download stories (if logged in)
            try:
                self._download_stories(profile, main_dir)
            except:
                print("⚠️  Skipping stories (login may be required)")
            
            # Download highlights
            try:
                self._download_highlights(profile, main_dir)
            except:
                print("⚠️  Skipping highlights (login may be required)")
            
            print(f"\n✅ All downloads completed!")
            print(f"📁 Location: {main_dir}")
            
        except instaloader.exceptions.ProfileNotExistsException:
            print(f"❌ Profile '@{target_username}' does not exist.")
        except Exception as e:
            print(f"❌ Error: {str(e)}")
    
    def _download_posts(self, profile, main_dir):
        """Download posts with organization: multi-image posts get their own folder"""
        posts_dir = main_dir / "posts"
        posts_dir.mkdir(exist_ok=True)
        
        print("\n📸 Downloading posts...")
        post_count = 0
        
        for post in profile.get_posts():
            post_count += 1
            
            # Check if post has multiple media items
            if post.mediacount > 1:
                # Create folder for multi-image post
                post_folder = posts_dir / f"post_{post.shortcode}"
                post_folder.mkdir(exist_ok=True)
                
                # Download to this folder
                self.L.dirname_pattern = str(post_folder)
                self.L.download_post(post, target=profile.username)
                
                # Create info file
                info_file = post_folder / "_post_info.txt"
                with open(info_file, 'w', encoding='utf-8') as f:
                    f.write(f"Post ID: {post.shortcode}\n")
                    f.write(f"Date: {post.date_local}\n")
                    f.write(f"Caption: {post.caption}\n")
                    f.write(f"Likes: {post.likes}\n")
                    f.write(f"Comments: {post.comments}\n")
            else:
                # Single image/video - download directly to posts folder
                self.L.dirname_pattern = str(posts_dir)
                self.L.download_post(post, target=profile.username)
            
            # Clean up metadata files
            self._cleanup_metadata_files(posts_dir if post.mediacount <= 1 else post_folder)
            
            print(f"  Downloaded post {post_count}/{profile.mediacount}", end='\r')
        
        print(f"\n✅ Posts downloaded: {post_count}")
    
    def _download_stories(self, profile, main_dir):
        """Download stories - only if available and logged in"""
        stories_dir = main_dir / "stories"
        stories_dir.mkdir(exist_ok=True)
        
        print("\n🎬 Downloading stories...")
        
        # Get current stories
        for story in self.L.get_stories(userids=[profile.userid]):
            for item in story.get_items():
                # Stories go directly to stories folder (no subfolders needed)
                self.L.dirname_pattern = str(stories_dir)
                self.L.download_storyitem(item, target=f"{profile.username}_stories")
                
                # Clean up metadata files
                self._cleanup_metadata_files(stories_dir)
        
        # Remove empty stories directory if no stories downloaded
        if len(list(stories_dir.glob("*"))) == 0:
            stories_dir.rmdir()
            print("  No stories available")
        else:
            print(f"✅ Stories downloaded to: {stories_dir}")
    
    def _download_highlights(self, profile, main_dir):
        """Download highlights - each highlight gets its own folder"""
        highlights_dir = main_dir / "highlights"
        highlights_dir.mkdir(exist_ok=True)
        
        print("\n🌟 Downloading highlights...")
        highlight_count = 0
        
        # Get all highlights
        for highlight in self.L.get_highlights(user=profile):
            highlight_count += 1
            
            # Get highlight title or use default name
            highlight_title = highlight.title if highlight.title else f"highlight_{highlight_count}"
            
            # Create folder for this highlight
            highlight_folder = highlights_dir / self._sanitize_filename(highlight_title)
            highlight_folder.mkdir(exist_ok=True)
            
            # Download all items in this highlight
            for item in highlight.get_items():
                self.L.dirname_pattern = str(highlight_folder)
                self.L.download_storyitem(item, target=highlight_title)
            
            # Clean up metadata files
            self._cleanup_metadata_files(highlight_folder)
            
            print(f"  Downloaded highlight: {highlight_title}")
        
        if highlight_count == 0:
            highlights_dir.rmdir()
            print("  No highlights available")
        else:
            print(f"✅ Highlights downloaded: {highlight_count}")
    
    def _cleanup_metadata_files(self, directory):
        """Remove all non-media files (JSON, TXT, etc.)"""
        media_extensions = {'.jpg', '.jpeg', '.png', '.mp4', '.webp', '.gif', '.mkv', '.mov'}
        
        for file_path in Path(directory).glob("*"):
            if file_path.suffix.lower() not in media_extensions:
                try:
                    file_path.unlink()
                except:
                    pass
    
    def _sanitize_filename(self, filename):
        """Remove invalid characters from filename"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename.strip()

def main():
    print("=" * 50)
    print("INSTAGRAM DOWNLOADER")
    print("=" * 50)
    
    # Optional login
    use_login = input("Do you want to login? (y/n): ").lower().strip()
    
    username = None
    password = None
    
    if use_login == 'y':
        username = input("Instagram username: ").strip()
        password = input("Instagram password: ").strip()
    
    # Initialize downloader
    downloader = InstagramDownloader(username, password)
    
    # Get target profile
    target = input("\nEnter Instagram username to download: ").strip()
    
    if target:
        downloader.download_profile(target)
    else:
        print("❌ Please enter a valid username")

if __name__ == "__main__":
    main()