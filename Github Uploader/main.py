import os
import base64
import requests
from dotenv import load_dotenv

# --- Setup ---
load_dotenv()
TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_USERNAME = "Ranim-K"

if not TOKEN:
    print("❌ GitHub token not found. Add it to your .env file as GITHUB_TOKEN=your_token")
    exit()

# --- Helper Functions ---
def repo_exists(repo_name):
    """Check if a repository already exists."""
    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}"
    headers = {"Authorization": f"token {TOKEN}"}
    response = requests.get(url, headers=headers)
    return response.status_code == 200

def create_repo(repo_name):
    """Create a new GitHub repository."""
    url = "https://api.github.com/user/repos"
    headers = {"Authorization": f"token {TOKEN}"}
    data = {"name": repo_name, "auto_init": False, "private": False}
    response = requests.post(url, json=data, headers=headers)
    
    if response.status_code == 201:
        print(f"✅ Repository '{repo_name}' created successfully.")
        return True
    elif response.status_code == 422:
        print(f"⚠️ Repository '{repo_name}' already exists.")
        return False
    else:
        print("❌ Error creating repository:", response.json())
        return False

def upload_file(repo, file_path, base_folder, commit_message, target_folder="", branch="main"):
    """Upload a single file to GitHub repo, optionally inside a subfolder."""
    with open(file_path, "rb") as f:
        content = base64.b64encode(f.read()).decode("utf-8")

    rel_path = os.path.relpath(file_path, start=base_folder).replace("\\", "/")

    # Add subfolder prefix if user requested it
    if target_folder:
        rel_path = f"{target_folder.rstrip('/')}/{rel_path}"

    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo}/contents/{rel_path}"
    headers = {"Authorization": f"token {TOKEN}"}

    # Check if file exists (to update instead of create)
    get_resp = requests.get(url, headers=headers)
    if get_resp.status_code == 200:
        sha = get_resp.json()["sha"]
        data = {"message": commit_message, "content": content, "branch": branch, "sha": sha}
    else:
        data = {"message": commit_message, "content": content, "branch": branch}

    response = requests.put(url, json=data, headers=headers)
    if response.status_code in [200, 201]:
        print(f"📁 Uploaded: {rel_path}")
    else:
        print(f"❌ Failed to upload {rel_path}: {response.json()}")

# --- Main Logic ---
repo_name = input("Enter the repository name: ").strip().replace(" ", "-")
base_folder = input("Enter the local folder path to upload: ").strip()
commit_message = input("Enter a commit message: ").strip()

# Ask if user wants to upload the folder as a subfolder
as_subfolder = input("Do you want to upload this folder as a subfolder inside the repo? (y/n): ").lower().strip()
target_folder = ""
if as_subfolder == "y":
    folder_name = os.path.basename(os.path.normpath(base_folder))
    custom_folder = input(f"Enter subfolder name (default: {folder_name}): ").strip()
    target_folder = custom_folder if custom_folder else folder_name

# Check repo
if repo_exists(repo_name):
    print(f"📦 Repository '{repo_name}' exists. Adding files...")
else:
    print(f"🆕 Repository '{repo_name}' does not exist. Creating...")
    if not create_repo(repo_name):
        exit()

# Upload all files
for root, _, files in os.walk(base_folder):
    for file in files:
        full_path = os.path.join(root, file)
        upload_file(repo_name, full_path, base_folder, commit_message, target_folder)

print("\n✅ Done! Check your repo at:")
print(f"https://github.com/{GITHUB_USERNAME}/{repo_name}")
