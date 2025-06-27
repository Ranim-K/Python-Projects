# Telegram Downloader

![Telegram](./telegram.gif)


A Python script that lets you download **photos and videos** from any **Telegram group or channel** using either a public `@username` or a private **invite link** like `https://t.me/joinchat/...`.

---

## ✅ Features

- Login with your own Telegram account (via `Telethon`)
- Supports both:
  - `@username` public channels/groups
  - Private invite links (`https://t.me/joinchat/...`)
- Automatically skips "already joined" errors
- Shows:
  - Total number of media files
  - Estimated download size in MB
- Lets you choose how many files to download
- Organizes all files in a `downloads/` folder
- Displays a progress bar (`tqdm`)
- Logs every downloaded file in the terminal

---

## 📦 Requirements

- Python 3.7+
- `Telethon`
- `tqdm`

Install dependencies:

```bash
pip install telethon tqdm
```

---

## 🧠 Usage

```bash
python telegram_downloader.py
```

### Example run:

```
✅ Logged in successfully.
📌 Enter channel @username or invite link: https://t.me/joinchat/abcDEF1234567
📡 Fetching messages...

📊 Total media files found: 248
💾 Estimated total size: 356.72 MB

🔢 Enter how many files to download (1–248): 20

⬇️ Starting download...

✅ [1/20] Downloaded: photo_1.jpg
✅ [2/20] Downloaded: video_2.mp4
...
✅ Download complete.
```

All files will be saved to:

```
./downloads/
```

---

## 🔐 Configuration

Your API credentials are already set in the script:

```python
api_id = 29949213
api_hash = 'cd78d1e37a6666756a5483ec22f6a84a'
```

If needed, you can get your own from [https://my.telegram.org](https://my.telegram.org).

---

## 🗂 File Structure

```
Telegram Downloader/
├── telegram_downloader.py
├── README.md
└── downloads/
    ├── photo_1.jpg
    ├── video_2.mp4
    └── ...
```

---

## ⚠️ Notes

- You must be a member of the group/channel you're downloading from.
- Private channels must allow joining via the provided link.
- The script supports download of both photos and documents (e.g., videos).

---

## 📥 Future Improvements

- Organize files into subfolders (e.g., `photos/`, `videos/`)
- Resume downloads
- GUI interface
- File type filters (e.g., only videos)

---

## 🧑‍💻 Author

Telegram Downloader — Powered by [Telethon](https://github.com/LonamiWebs/Telethon)

