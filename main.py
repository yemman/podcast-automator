import base64
import os
import requests
from googleapiclient.discovery import build
from google.oauth2 import service_account
from podgen import Podcast, Episode, Media

# --- CONFIG ---
FOLDER_ID = os.environ.get('FOLDER_ID')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
REPO_NAME = "yemman/podcast-automator"
FILE_PATH = "feed.xml" # The path in your repo

def drive_to_spotify(event, context):
    # 1. Auth with Google Drive (using Function's Identity)
    # Ensure the Function Service Account has 'Viewer' access to your Drive Folder
    drive_service = build('drive', 'v3')
    
    query = f"'{FOLDER_ID}' in parents and mimeType contains 'audio/'"
    results = drive_service.files().list(q=query, fields="files(id, name, createdTime, size)").execute()
    files = results.get('files', [])

    # 2. Generate RSS Feed
    p = Podcast(name="The Power Of Silance Podcast", description="Auto-synced from Drive", 
                website="https://github.com/yemman", explicit=False)
    
    for f in files:
        download_url = f"https://drive.google.com/uc?export=download&id={f['id']}"
        e = p.add_episode()
        e.title = f['name']
        e.media = Media(download_url, size=int(f.get('size', 0)))
        e.publication_date = f['createdTime']

    rss_content = p.rss_str()

    # 3. Push to GitHub via API
    url = f"https://api.github.com/repos/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    
    # Get the 'sha' of the existing file (required to update it)
    current_file = requests.get(url, headers=headers).json()
    sha = current_file.get('sha')

    payload = {
        "message": "Automated RSS Update",
        "content": base64.b64encode(rss_content.encode()).decode(),
        "sha": sha
    }
    
    response = requests.put(url, json=payload, headers=headers)
    return f"Status: {response.status_code}"
