# Image Downloader

## Idea

This project is a simple script to download images from any given webpage URL. It focuses on downloading **main content images** while avoiding small images like favicons, logos, or avatars. Each set of images from a URL is organized neatly into a numeric folder.

---

## Workflow

1. **Input URL**  
   - User provides a webpage URL via the script input.

2. **Create Folder**  
   - A new folder with a numeric name (1, 2, 3...) is automatically created inside the `Downloads` folder of the project.

3. **Fetch Images**  
   - The script parses the webpage and finds all `<img>` tags.  
   - Relative URLs are converted to absolute URLs.

4. **Filter Small Images**  
   - Tiny images (like favicons or icons smaller than 5KB) are skipped automatically.

5. **Download and Save**  
   - Each image is downloaded and saved inside the numeric folder.  
   - Images are named numerically (1.jpg, 2.png, 3.jpg, ...).  
   - The script prints a clean log for each downloaded image.

6. **Next URL**  
   - The script waits for the next URL input, repeating the process.  
   - User can quit by typing `q`.

