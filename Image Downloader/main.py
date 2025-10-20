import requests
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin
import os

# Base Downloads folder in the project folder
base_folder = Path.cwd() / "Downloads"
base_folder.mkdir(exist_ok=True)

url_counter = 1  # For folder numbering

while True:
    url = input("Enter URL (or 'q' to quit): ")
    if url.lower() == 'q':
        break

    folder = base_folder / str(url_counter)
    folder.mkdir(exist_ok=True)

    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(resp.content, "html.parser")

        # Find all images
        imgs = soup.find_all("img")
        if not imgs:
            print(f"No images found for URL {url}")
            continue

        img_counter = 1
        for img in imgs:
            img_url = img.get("src")
            if not img_url:
                continue
            img_url = urljoin(url, img_url)  # handle relative links

            # Skip very small images (like favicons, logos)
            try:
                head = requests.head(img_url, headers={"User-Agent": "Mozilla/5.0"})
                size = int(head.headers.get("Content-Length", 0))
                if size < 40000:  # skip images < 5KB
                    continue
            except:
                pass

            ext = os.path.splitext(img_url)[1].split("?")[0]  # get extension
            if not ext or len(ext) > 5:
                ext = ".jpg"

            try:
                r = requests.get(img_url, stream=True, timeout=5)
                file_path = folder / f"{img_counter}{ext}"
                with open(file_path, "wb") as f:
                    for chunk in r.iter_content(1024):
                        f.write(chunk)
                print(f"Downloaded {file_path.name}")
                img_counter += 1
            except Exception as e:
                print(f"Failed to download image: {img_url}")
                continue

        print(f"Downloaded {img_counter-1} images into folder: {folder}\n")
        url_counter += 1

    except Exception as e:
        print(f"Failed to download from URL: {url}")
