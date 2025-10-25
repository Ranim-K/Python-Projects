import os
import zipfile
from pdf2image import convert_from_path
from PIL import Image
from tkinter import Tk, filedialog
from datetime import datetime
import img2pdf
import platform
import subprocess

# Adjust this if Poppler is not in your PATH
POPPLER_PATH = r"C:\poppler\Library\bin"

# --- Helper to open folders/files safely ---
def open_path(path):
    if not os.path.exists(path):
        print("Path does not exist:", path)
        return
    try:
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.run(["open", path])
        else:  # Linux
            subprocess.run(["xdg-open", path])
    except Exception as e:
        print("Could not open path automatically:", e)

# --- PDF → Images ---
def pdf_to_images(pdf_path, output_folder, image_format="png", dpi=200, zip_option=False, poppler_path=POPPLER_PATH):
    try:
        pages = convert_from_path(pdf_path, dpi=dpi, poppler_path=poppler_path)
    except Exception as e:
        print(f"Error converting {pdf_path} to images:", e)
        return

    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_folder = os.path.join(output_folder, f"{base_name}_{timestamp}")
    os.makedirs(pdf_folder, exist_ok=True)

    image_paths = []
    for i, page in enumerate(pages, start=1):
        img_name = f"{base_name}_page{i}.{image_format}"
        img_path = os.path.join(pdf_folder, img_name)
        page.save(img_path, "JPEG" if image_format.lower() == "jpg" else "PNG")
        image_paths.append(img_path)

    print(f"\nConverted {len(image_paths)} pages for {os.path.basename(pdf_path)} into folder:\n{pdf_folder}")

    open_target = pdf_folder

    if zip_option:
        zip_name = f"{base_name}.zip"
        zip_path = os.path.join(output_folder, zip_name)
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for img in image_paths:
                zipf.write(img, os.path.basename(img))
        print(f"All images zipped here:\n{zip_path}")
        open_target = zip_path

    open_path(open_target)

# --- Images → PDF ---
def images_to_pdf(image_paths, output_folder, pdf_name=None):
    if not image_paths:
        print("No images selected.")
        return
    if pdf_name is None:
        pdf_name = os.path.splitext(os.path.basename(image_paths[0]))[0] + ".pdf"
    pdf_path = os.path.join(output_folder, pdf_name)
    try:
        with open(pdf_path, "wb") as f:
            f.write(img2pdf.convert(image_paths))
        print(f"\nPDF created at:\n{pdf_path}")
        open_path(os.path.dirname(pdf_path))
    except Exception as e:
        print("Error converting images to PDF:", e)

# --- File Dialog Helpers ---
def ask_pdf_files():
    temp_root = Tk()
    temp_root.withdraw()
    pdf_paths = filedialog.askopenfilenames(title="Select PDF(s)", filetypes=[("PDF Files", "*.pdf")])
    temp_root.destroy()
    return pdf_paths

def ask_image_files():
    temp_root = Tk()
    temp_root.withdraw()
    image_paths = filedialog.askopenfilenames(
        title="Select image(s)",
        filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp *.tiff")]
    )
    temp_root.destroy()
    return image_paths

# --- Flows ---
def pdf_to_img_flow():
    pdf_paths = ask_pdf_files()
    if not pdf_paths:
        print("No PDFs selected.")
        return

    image_format = input("Enter image format (png/jpg, default png): ").strip().lower() or "png"
    dpi_input = input("Enter DPI (default 200): ").strip()
    dpi = int(dpi_input) if dpi_input.isdigit() else 200
    output_folder = input("Enter output folder path (leave empty for current): ").strip() or os.getcwd()
    zip_input = input("Do you want to zip the images? (y/n, default n): ").strip().lower()
    zip_option = zip_input == "y"

    for pdf_path in pdf_paths:
        pdf_to_images(pdf_path, output_folder, image_format, dpi, zip_option)

def img_to_pdf_flow():
    image_paths = ask_image_files()
    if not image_paths:
        print("No images selected.")
        return
    output_folder = input("Enter output folder path (leave empty for current): ").strip() or os.getcwd()
    pdf_name = input("Enter PDF file name (leave empty to use first image name): ").strip() or None
    images_to_pdf(image_paths, output_folder, pdf_name)

# --- Main Menu ---
def main():
    while True:
        print("\n=== PDF ↔ Image Converter ===")
        print("1. PDF → Images (optional zip, multiple PDFs allowed)")
        print("2. Images → PDF (multiple images allowed)")
        print("3. Exit")
        choice = input("Choose an option (1-3): ").strip()
        if choice == "1":
            pdf_to_img_flow()
        elif choice == "2":
            img_to_pdf_flow()
        elif choice == "3":
            print("Goodbye!")
            break
        else:
            print("Invalid choice. Try again.")

if __name__ == "__main__":
    main()
