#!/usr/bin/env python3
"""
📁 File Organizer - All-in-One File Management Tool
Version: 2.0
Author: Your Name
Description: A comprehensive tool to organize, clean, and manage files with multiple functions.
"""

import os
import re
import shutil
import sys
import calendar
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Dict
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


# ======================== CORE ORGANIZER CLASS ========================
class FileOrganizer:
    def __init__(self):
        self.supported_video = {'.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.webm'}
        self.supported_image = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
        self.supported_audio = {'.mp3', '.wav', '.aac', '.flac', '.ogg', '.m4a'}
    
    # ======================== UTILITY FUNCTIONS ========================
    @staticmethod
    def safe_move(src, dst):
        """Safely move a file, handling duplicates."""
        src_path = Path(src)
        dst_path = Path(dst)
        
        if not src_path.exists():
            return False, f"Source file doesn't exist: {src}"
        
        if dst_path.exists():
            base = dst_path.stem
            ext = dst_path.suffix
            counter = 1
            while dst_path.exists():
                dst_path = dst_path.parent / f"{base}_{counter}{ext}"
                counter += 1
        
        try:
            shutil.move(str(src_path), str(dst_path))
            return True, f"Moved: {src_path.name}"
        except Exception as e:
            return False, f"Failed to move {src_path.name}: {str(e)}"
    
    @staticmethod
    def create_folder(path):
        """Create folder if it doesn't exist."""
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            return True, f"Created folder: {path}"
        except Exception as e:
            return False, f"Failed to create folder: {str(e)}"
    
    # ======================== MAIN FUNCTIONS ========================
    
    # 1. ORGANIZE BY DATE
    def organize_by_date(self, folder_path):
        """
        Organize files by date extracted from filename or creation date.
        Creates Year → Month Name → Day structure.
        """
        main_path = Path(folder_path)
        
        if not main_path.exists():
            return False, "Folder doesn't exist!"
        
        results = []
        
        # Step 1: Move all files from subfolders to main folder
        for root, _, files in os.walk(main_path):
            root_path = Path(root)
            for file in files:
                file_path = root_path / file
                if file_path.parent != main_path:
                    success, msg = self.safe_move(file_path, main_path / file)
                    results.append(msg)
        
        # Step 2: Sort files by date
        date_pattern = re.compile(r'(19|20)\d{2}[-_/.]\d{2}[-_/.]\d{2}')
        
        for file in main_path.iterdir():
            if not file.is_file():
                continue
            
            # Clean filename
            clean_name = file.name.strip().replace('\u202a', '').replace('\u202c', '')
            
            # Try to extract date from filename
            match = date_pattern.search(clean_name)
            if match:
                date_str = match.group().replace('_', '-').replace('/', '-').replace('.', '-')
                try:
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                    date_source = "filename"
                except ValueError:
                    # Fallback to file creation date
                    created_time = file.stat().st_ctime
                    date_obj = datetime.fromtimestamp(created_time)
                    date_source = "creation date"
            else:
                # Use file creation date
                created_time = file.stat().st_ctime
                date_obj = datetime.fromtimestamp(created_time)
                date_source = "creation date"
            
            # Create folder structure
            year = str(date_obj.year)
            month_name = calendar.month_name[date_obj.month]
            day = f"{date_obj.day:02d}"
            
            dest_folder = main_path / year / month_name / day
            success, msg = self.create_folder(dest_folder)
            if success:
                success, move_msg = self.safe_move(file, dest_folder / file.name)
                results.append(f"{move_msg} (from {date_source})")
        
        return True, "\n".join(results[:20])  # Show first 20 results
    
    # 2. GROUP CONSECUTIVE FILES
    def group_consecutive(self, folder_path, file_type="video"):
        """
        Group files with consecutive numbers in their names.
        """
        folder = Path(folder_path)
        
        if not folder.exists():
            return False, "Folder doesn't exist!"
        
        # Determine file extensions
        if file_type == "video":
            extensions = self.supported_video
        elif file_type == "image":
            extensions = self.supported_image
        elif file_type == "audio":
            extensions = self.supported_audio
        else:
            extensions = {'.*'}  # All files
        
        # Get relevant files
        files = []
        for ext in extensions:
            files.extend(list(folder.glob(f"*{ext}")))
        
        # Extract numbers from filenames
        num_map = {}
        for file in files:
            numbers = re.findall(r'\d+', file.stem)
            if numbers:
                main_num = int(max(numbers, key=lambda x: int(x)))
                num_map[file] = main_num
        
        if not num_map:
            return False, "No numeric identifiers found in filenames!"
        
        # Sort by number
        sorted_items = sorted(num_map.items(), key=lambda x: x[1])
        
        # Group consecutive numbers
        groups = []
        current_group = [sorted_items[0]]
        
        for i in range(1, len(sorted_items)):
            prev_num = sorted_items[i-1][1]
            curr_num = sorted_items[i][1]
            
            if curr_num == prev_num + 1:
                current_group.append(sorted_items[i])
            else:
                groups.append(current_group)
                current_group = [sorted_items[i]]
        groups.append(current_group)
        
        # Create folders and move files
        results = []
        for group in groups:
            if len(group) > 1:
                start = group[0][1]
                end = group[-1][1]
                folder_name = f"Group_{start:04d}-{end:04d}"
                dest_path = folder / folder_name
                
                success, msg = self.create_folder(dest_path)
                if success:
                    for file_obj, _ in group:
                        success, move_msg = self.safe_move(file_obj, dest_path / file_obj.name)
                        results.append(move_msg)
        
        return True, f"Created {len(groups)} groups\n" + "\n".join(results[:15])
    
    # 3. EXTRACT FROM SUBFOLDERS
    def extract_from_subfolders(self, source_folder, destination_folder=None):
        """
        Extract all files from subfolders into one folder.
        """
        source = Path(source_folder)
        
        if not source.exists():
            return False, "Source folder doesn't exist!"
        
        if destination_folder is None:
            destination = source / "EXTRACTED_FILES"
        else:
            destination = Path(destination_folder)
        
        success, msg = self.create_folder(destination)
        if not success:
            return False, msg
        
        moved_count = 0
        results = []
        
        for root, _, files in os.walk(source):
            root_path = Path(root)
            
            # Skip destination folder
            if destination in root_path.parents or root_path == destination:
                continue
            
            for file in files:
                src_path = root_path / file
                
                # Skip the script itself
                if src_path.samefile(__file__):
                    continue
                
                # Handle duplicate names
                dest_path = destination / file
                counter = 1
                while dest_path.exists():
                    dest_path = destination / f"{src_path.stem}_{counter}{src_path.suffix}"
                    counter += 1
                
                success, move_msg = self.safe_move(src_path, dest_path)
                if success:
                    moved_count += 1
                    results.append(f"Extracted: {file}")
        
        return True, f"Extracted {moved_count} files to {destination}\n" + "\n".join(results[:15])
    
    # 4. CREATE MULTIPLE FOLDERS
    def create_multiple_folders(self, base_folder, folder_names):
        """
        Create multiple folders at once.
        """
        base = Path(base_folder)
        
        if not base.exists():
            return False, "Base folder doesn't exist!"
        
        results = []
        created_count = 0
        
        for name in folder_names:
            if name.strip():  # Skip empty names
                folder_path = base / name.strip()
                success, msg = self.create_folder(folder_path)
                results.append(msg)
                if success:
                    created_count += 1
        
        return True, f"Created {created_count} folders\n" + "\n".join(results)
    
    # 5. SPLIT INTO GROUPS
    def split_into_groups(self, folder_path, group_size=10):
        """
        Split files into numbered groups.
        """
        folder = Path(folder_path)
        
        if not folder.exists():
            return False, "Folder doesn't exist!"
        
        # Get all files (not folders)
        files = [f for f in folder.iterdir() if f.is_file()]
        
        if not files:
            return False, "No files found in folder!"
        
        results = []
        group_num = 1
        file_index = 0
        
        while file_index < len(files):
            group_folder = folder / f"Group_{group_num:03d}"
            success, msg = self.create_folder(group_folder)
            
            if not success:
                results.append(f"Failed to create {group_folder.name}")
                break
            
            for _ in range(group_size):
                if file_index >= len(files):
                    break
                
                file = files[file_index]
                success, move_msg = self.safe_move(file, group_folder / file.name)
                results.append(move_msg)
                file_index += 1
            
            group_num += 1
        
        return True, f"Split {len(files)} files into groups\n" + "\n".join(results[:15])
    
    # 6. CLEAN SMALL FILES
    def clean_small_files(self, folder_path, max_size_kb=500):
        """
        Move small files to a separate folder.
        """
        folder = Path(folder_path)
        
        if not folder.exists():
            return False, "Folder doesn't exist!"
        
        small_files_folder = folder / "SMALL_FILES"
        success, msg = self.create_folder(small_files_folder)
        
        if not success:
            return False, msg
        
        moved_count = 0
        results = []
        
        for root, _, files in os.walk(folder):
            root_path = Path(root)
            
            # Skip the small files folder
            if small_files_folder in root_path.parents or root_path == small_files_folder:
                continue
            
            for file in files:
                file_path = root_path / file
                
                # Get file size in KB
                try:
                    size_kb = file_path.stat().st_size / 1024
                    if size_kb <= max_size_kb:
                        success, move_msg = self.safe_move(file_path, small_files_folder / file_path.name)
                        if success:
                            moved_count += 1
                            results.append(f"Moved: {file_path.name} ({size_kb:.1f} KB)")
                except Exception:
                    continue
        
        return True, f"Moved {moved_count} small files\n" + "\n".join(results[:15])
    
    # 7. SORT BY TYPE
    def sort_by_type(self, folder_path):
        """
        Sort files into Video, Image, Audio, and Other folders.
        """
        folder = Path(folder_path)
        
        if not folder.exists():
            return False, "Folder doesn't exist!"
        
        # Create category folders
        categories = {
            "VIDEOS": self.supported_video,
            "IMAGES": self.supported_image,
            "AUDIO": self.supported_audio,
            "OTHER": set()
        }
        
        for category in categories:
            success, msg = self.create_folder(folder / category)
            if not success:
                return False, msg
        
        moved_counts = {category: 0 for category in categories}
        results = []
        
        for item in folder.iterdir():
            if not item.is_file():
                continue
            
            ext = item.suffix.lower()
            moved = False
            
            # Find the right category
            for category, extensions in categories.items():
                if category == "OTHER":
                    dest_category = "OTHER"
                    break
                elif ext in extensions:
                    dest_category = category
                    break
            else:
                dest_category = "OTHER"
            
            dest_path = folder / dest_category / item.name
            success, move_msg = self.safe_move(item, dest_path)
            
            if success:
                moved_counts[dest_category] += 1
                results.append(f"Sorted to {dest_category}: {item.name}")
        
        summary = "\n".join([f"{cat}: {count} files" for cat, count in moved_counts.items()])
        return True, f"Sorting complete!\n{summary}\n" + "\n".join(results[:10])
    
    # 8. EXTRACT MEDIA FILES
    def extract_media_files(self, source_folder, destination_folder=None):
        """
        Extract and organize media files by type.
        """
        source = Path(source_folder)
        
        if not source.exists():
            return False, "Source folder doesn't exist!"
        
        if destination_folder is None:
            destination = source.parent / f"{source.name}_EXTRACTED_MEDIA"
        else:
            destination = Path(destination_folder)
        
        success, msg = self.create_folder(destination)
        if not success:
            return False, msg
        
        # Create media subfolders
        media_folders = {
            "Videos": self.supported_video,
            "Images": self.supported_image,
            "Audio": self.supported_audio,
            "Documents": {'.pdf', '.doc', '.docx', '.txt', '.xls', '.xlsx', '.ppt', '.pptx'},
            "Archives": {'.zip', '.rar', '.7z', '.tar', '.gz'},
            "Other": set()
        }
        
        for folder_name in media_folders:
            success, msg = self.create_folder(destination / folder_name)
            if not success:
                return False, msg
        
        counts = {category: 0 for category in media_folders}
        results = []
        
        for root, _, files in os.walk(source):
            root_path = Path(root)
            
            for file in files:
                src_path = root_path / file
                ext = src_path.suffix.lower()
                
                # Find the right category
                dest_category = "Other"
                for category, extensions in media_folders.items():
                    if ext in extensions:
                        dest_category = category
                        break
                
                dest_path = destination / dest_category / file
                success, move_msg = self.safe_move(src_path, dest_path)
                
                if success:
                    counts[dest_category] += 1
                    results.append(f"Copied to {dest_category}: {file}")
        
        summary = "\n".join([f"{cat}: {count} files" for cat, count in counts.items() if count > 0])
        return True, f"Media extraction complete!\n{summary}\n" + "\n".join(results[:15])
    
    # 9. SPLIT FOLDERS AND MEDIA
    def split_folders_and_media(self, folder_path):
        """
        Separate folders and media files into different directories.
        """
        folder = Path(folder_path)
        
        if not folder.exists():
            return False, "Folder doesn't exist!"
        
        # Create destination folders
        folders_dir = folder / "FOLDERS"
        media_dir = folder / "MEDIA_FILES"
        
        success, msg = self.create_folder(folders_dir)
        if not success:
            return False, msg
        
        success, msg = self.create_folder(media_dir)
        if not success:
            return False, msg
        
        results = []
        folder_count = 0
        file_count = 0
        
        for item in folder.iterdir():
            # Skip the newly created folders
            if item.name in ["FOLDERS", "MEDIA_FILES"]:
                continue
            
            if item.is_dir():
                dest = folders_dir / item.name
                success, move_msg = self.safe_move(item, dest)
                if success:
                    folder_count += 1
                    results.append(f"Moved folder: {item.name}")
            else:
                dest = media_dir / item.name
                success, move_msg = self.safe_move(item, dest)
                if success:
                    file_count += 1
                    results.append(f"Moved file: {item.name}")
        
        return True, f"Moved {folder_count} folders and {file_count} files\n" + "\n".join(results[:15])


# ======================== GUI APPLICATION ========================
class FileOrganizerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("📁 File Organizer Pro")
        self.root.geometry("800x600")
        
        # Initialize organizer
        self.organizer = FileOrganizer()
        
        # Configure styles
        self.setup_styles()
        
        # Create main frame
        self.main_frame = ttk.Frame(root, padding="20")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(
            self.main_frame,
            text="📁 FILE ORGANIZER PRO",
            font=("Arial", 24, "bold")
        )
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 30))
        
        # Folder selection
        ttk.Label(self.main_frame, text="Working Folder:").grid(row=1, column=0, sticky=tk.W, pady=5)
        
        self.folder_var = tk.StringVar()
        self.folder_entry = ttk.Entry(self.main_frame, textvariable=self.folder_var, width=50)
        self.folder_entry.grid(row=1, column=1, padx=5, pady=5, sticky=(tk.W, tk.E))
        
        self.browse_btn = ttk.Button(self.main_frame, text="Browse...", command=self.browse_folder)
        self.browse_btn.grid(row=1, column=2, padx=5, pady=5)
        
        # Separator
        ttk.Separator(self.main_frame, orient=tk.HORIZONTAL).grid(
            row=2, column=0, columnspan=3, pady=20, sticky=(tk.W, tk.E)
        )
        
        # Function buttons frame
        self.buttons_frame = ttk.Frame(self.main_frame)
        self.buttons_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E))
        
        # Create buttons for each function
        buttons = [
            ("📅 Organize by Date", self.organize_by_date_gui),
            ("🔢 Group Consecutive", self.group_consecutive_gui),
            ("📤 Extract from Subfolders", self.extract_subfolders_gui),
            ("📁 Create Multiple Folders", self.create_folders_gui),
            ("✂️ Split into Groups", self.split_groups_gui),
            ("🧹 Clean Small Files", self.clean_small_gui),
            ("🗂️ Sort by Type", self.sort_by_type_gui),
            ("🎬 Extract Media Files", self.extract_media_gui),
            ("📂 Split Folders & Files", self.split_folders_files_gui),
        ]
        
        for i, (text, command) in enumerate(buttons):
            row = i // 3
            col = i % 3
            btn = ttk.Button(self.buttons_frame, text=text, command=command, width=25)
            btn.grid(row=row, column=col, padx=5, pady=5, sticky=(tk.W, tk.E))
        
        # Results area
        ttk.Label(self.main_frame, text="Results:").grid(row=4, column=0, sticky=tk.W, pady=(20, 5))
        
        self.results_text = tk.Text(self.main_frame, height=10, width=80, wrap=tk.WORD)
        self.results_text.grid(row=5, column=0, columnspan=3, pady=5, sticky=(tk.W, tk.E))
        
        scrollbar = ttk.Scrollbar(self.main_frame, orient=tk.VERTICAL, command=self.results_text.yview)
        scrollbar.grid(row=5, column=3, sticky=(tk.N, tk.S))
        self.results_text.configure(yscrollcommand=scrollbar.set)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        self.status_bar = ttk.Label(self.main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        self.status_bar.grid(row=6, column=0, columnspan=3, pady=(20, 0), sticky=(tk.W, tk.E))
        
    def setup_styles(self):
        """Configure custom styles for the GUI."""
        style = ttk.Style()
        style.configure("TButton", padding=6)
        style.configure("Title.TLabel", font=("Arial", 24, "bold"))
        
    def browse_folder(self):
        """Open folder browser dialog."""
        folder = filedialog.askdirectory(title="Select Folder")
        if folder:
            self.folder_var.set(folder)
    
    def log_result(self, success, message):
        """Log results to the text widget."""
        self.results_text.insert(tk.END, "\n" + "="*60 + "\n")
        if success:
            self.results_text.insert(tk.END, "✅ SUCCESS:\n")
            self.status_var.set("Operation completed successfully!")
        else:
            self.results_text.insert(tk.END, "❌ ERROR:\n")
            self.status_var.set("Operation failed!")
        
        self.results_text.insert(tk.END, message + "\n")
        self.results_text.see(tk.END)
    
    def organize_by_date_gui(self):
        """GUI wrapper for organize_by_date."""
        folder = self.folder_var.get()
        if not folder:
            messagebox.showerror("Error", "Please select a folder first!")
            return
        
        success, message = self.organizer.organize_by_date(folder)
        self.log_result(success, message)
    
    def group_consecutive_gui(self):
        """GUI wrapper for group_consecutive."""
        folder = self.folder_var.get()
        if not folder:
            messagebox.showerror("Error", "Please select a folder first!")
            return
        
        # Ask for file type
        file_type = tk.simpledialog.askstring(
            "File Type",
            "Enter file type (video/image/audio/all):",
            initialvalue="video"
        )
        
        if file_type:
            success, message = self.organizer.group_consecutive(folder, file_type.lower())
            self.log_result(success, message)
    
    def extract_subfolders_gui(self):
        """GUI wrapper for extract_from_subfolders."""
        folder = self.folder_var.get()
        if not folder:
            messagebox.showerror("Error", "Please select a folder first!")
            return
        
        dest_folder = filedialog.askdirectory(
            title="Select Destination Folder (optional)",
            mustexist=False
        )
        
        success, message = self.organizer.extract_from_subfolders(folder, dest_folder)
        self.log_result(success, message)
    
    def create_folders_gui(self):
        """GUI wrapper for create_multiple_folders."""
        folder = self.folder_var.get()
        if not folder:
            messagebox.showerror("Error", "Please select a folder first!")
            return
        
        # Open dialog for multiple folder names
        folder_names = tk.simpledialog.askstring(
            "Create Folders",
            "Enter folder names (separated by commas):"
        )
        
        if folder_names:
            names = [name.strip() for name in folder_names.split(",") if name.strip()]
            if names:
                success, message = self.organizer.create_multiple_folders(folder, names)
                self.log_result(success, message)
    
    def split_groups_gui(self):
        """GUI wrapper for split_into_groups."""
        folder = self.folder_var.get()
        if not folder:
            messagebox.showerror("Error", "Please select a folder first!")
            return
        
        group_size = tk.simpledialog.askinteger(
            "Group Size",
            "Enter number of files per group:",
            initialvalue=10,
            minvalue=1,
            maxvalue=100
        )
        
        if group_size:
            success, message = self.organizer.split_into_groups(folder, group_size)
            self.log_result(success, message)
    
    def clean_small_gui(self):
        """GUI wrapper for clean_small_files."""
        folder = self.folder_var.get()
        if not folder:
            messagebox.showerror("Error", "Please select a folder first!")
            return
        
        max_size = tk.simpledialog.askinteger(
            "Maximum Size",
            "Enter maximum file size in KB:",
            initialvalue=500,
            minvalue=1,
            maxvalue=10000
        )
        
        if max_size:
            success, message = self.organizer.clean_small_files(folder, max_size)
            self.log_result(success, message)
    
    def sort_by_type_gui(self):
        """GUI wrapper for sort_by_type."""
        folder = self.folder_var.get()
        if not folder:
            messagebox.showerror("Error", "Please select a folder first!")
            return
        
        success, message = self.organizer.sort_by_type(folder)
        self.log_result(success, message)
    
    def extract_media_gui(self):
        """GUI wrapper for extract_media_files."""
        folder = self.folder_var.get()
        if not folder:
            messagebox.showerror("Error", "Please select a folder first!")
            return
        
        dest_folder = filedialog.askdirectory(
            title="Select Destination Folder for Media",
            mustexist=False
        )
        
        success, message = self.organizer.extract_media_files(folder, dest_folder)
        self.log_result(success, message)
    
    def split_folders_files_gui(self):
        """GUI wrapper for split_folders_and_media."""
        folder = self.folder_var.get()
        if not folder:
            messagebox.showerror("Error", "Please select a folder first!")
            return
        
        success, message = self.organizer.split_folders_and_media(folder)
        self.log_result(success, message)


# ======================== COMMAND LINE INTERFACE ========================
def show_cli_menu():
    """Display command line interface menu."""
    organizer = FileOrganizer()
    
    while True:
        print("\n" + "="*60)
        print("📁 FILE ORGANIZER PRO - Command Line Interface")
        print("="*60)
        print("1. 📅 Organize files by date")
        print("2. 🔢 Group consecutive numbered files")
        print("3. 📤 Extract files from subfolders")
        print("4. 📁 Create multiple folders")
        print("5. ✂️ Split files into groups")
        print("6. 🧹 Clean small files")
        print("7. 🗂️ Sort files by type")
        print("8. 🎬 Extract media files")
        print("9. 📂 Split folders and files")
        print("10. 🚪 Exit")
        print("="*60)
        
        choice = input("\nSelect an option (1-10): ").strip()
        
        if choice == "10":
            print("\nGoodbye! 👋")
            break
        
        folder_path = input("Enter folder path: ").strip()
        
        if not os.path.exists(folder_path):
            print("❌ Error: Folder doesn't exist!")
            continue
        
        try:
            if choice == "1":
                success, message = organizer.organize_by_date(folder_path)
            elif choice == "2":
                file_type = input("File type (video/image/audio/all): ").strip().lower()
                success, message = organizer.group_consecutive(folder_path, file_type)
            elif choice == "3":
                dest = input("Destination folder (press Enter for default): ").strip()
                dest = None if dest == "" else dest
                success, message = organizer.extract_from_subfolders(folder_path, dest)
            elif choice == "4":
                names_input = input("Enter folder names (comma-separated): ").strip()
                names = [n.strip() for n in names_input.split(",") if n.strip()]
                if names:
                    success, message = organizer.create_multiple_folders(folder_path, names)
                else:
                    print("❌ No folder names provided!")
                    continue
            elif choice == "5":
                try:
                    group_size = int(input("Files per group (default 10): ").strip() or "10")
                    success, message = organizer.split_into_groups(folder_path, group_size)
                except ValueError:
                    print("❌ Invalid number!")
                    continue
            elif choice == "6":
                try:
                    max_size = int(input("Max file size in KB (default 500): ").strip() or "500")
                    success, message = organizer.clean_small_files(folder_path, max_size)
                except ValueError:
                    print("❌ Invalid number!")
                    continue
            elif choice == "7":
                success, message = organizer.sort_by_type(folder_path)
            elif choice == "8":
                dest = input("Destination folder (press Enter for default): ").strip()
                dest = None if dest == "" else dest
                success, message = organizer.extract_media_files(folder_path, dest)
            elif choice == "9":
                success, message = organizer.split_folders_and_media(folder_path)
            else:
                print("❌ Invalid choice!")
                continue
            
            print("\n" + ("✅ SUCCESS:" if success else "❌ ERROR:"))
            print(message)
            
        except Exception as e:
            print(f"❌ An error occurred: {str(e)}")
        
        input("\nPress Enter to continue...")


# ======================== MAIN ENTRY POINT ========================
def main():
    """Main entry point for the application."""
    print("📁 File Organizer Pro - Starting...")
    
    # Check if GUI mode is requested
    if len(sys.argv) > 1 and sys.argv[1].lower() == "--cli":
        show_cli_menu()
    else:
        try:
            # Try to start GUI
            root = tk.Tk()
            app = FileOrganizerGUI(root)
            root.mainloop()
        except tk.TclError:
            print("GUI not available. Falling back to CLI mode...")
            show_cli_menu()


if __name__ == "__main__":
    main()