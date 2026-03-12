import base64
import os
import requests
import logging
import google.auth
from googleapiclient.discovery import build
from podgen import Podcast, Media

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PodcastAutomator:
    def __init__(self):
        self.folder_id = os.environ.get('FOLDER_ID')
        self.github_token = os.environ.get('GITHUB_TOKEN')
        self.repo_name = "yemman/podcast-automator"
        self.file_path = "feed.xml"
        self.github_base_url = f"https://api.github.com/repos/{self.repo_name}/contents/{self.file_path}"

    def get_drive_files(self):
        """Fetches audio files from the specified Google Drive folder."""
        logger.info(f"Fetching files from Drive folder: {self.folder_id}")
        credentials, _ = google.auth.default()
        service = build('drive', 'v3', credentials=credentials)
        
        query = f"'{self.folder_id}' in parents and mimeType contains 'audio/'"
        results = service.files().list(q=query, fields="files(id, name, createdTime, size)").execute()
        return results.get('files', [])

    def generate_rss(self, files):
        """Creates the RSS XML string using podgen."""
        logger.info(f"Generating RSS for {len(files)} files.")
        p = Podcast(
            name="The Power Of Silance Podcast",
            description="Auto-synced from Drive",
            website="https://github.com/yemman",
            explicit=False
        )
        
        for f in files:
            # We append &ext=.mp3 to satisfy podgen's validation
            download_url = f"https://drive.google.com/uc?export=download&id={f['id']}&ext=.m4a"
            
            e = p.add_episode()
            e.title = f['name']
            e.media = Media(download_url, size=int(f.get('size', 0)))
            e.publication_date = f['createdTime']
        
        return p.rss_str()

    def update_github(self, content):
        """Pushes the XML content to GitHub, handling SHA for updates."""
        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }

        # Step A: Get current file SHA if it exists
        resp = requests.get(self.github_base_url, headers=headers)
        sha = resp.json().get('sha') if resp.status_code == 200 else None
        
        # Step B: Prepare Payload
        payload = {
            "message": "Automated RSS Update",
            "content": base64.b64encode(content.encode()).decode()
        }
        if sha:
            payload["sha"] = sha

        # Step C: Push Update
        put_resp = requests.put(self.github_base_url, json=payload, headers=headers)
        return put_resp.status_code

# --- GCP Entry Point ---
def drive_to_spotify(request):
    """The main function called by GCP."""
    automator = PodcastAutomator()

    # 1. Validation
    if not automator.github_token or not automator.folder_id:
        logger.error("Missing Environment Variables.")
        return ("Config Error", 503)

    try:
        # 2. Execution Pipeline
        files = automator.get_drive_files()
        rss_xml = automator.generate_rss(files)
        status = automator.update_github(rss_xml)

        if status in [200, 201]:
            logger.info("Successfully synced.")
            return ("Success", 200)
        else:
            logger.error(f"GitHub Update Failed with status: {status}")
            return ("GitHub Error", 502)

    except Exception as e:
        logger.error(f"Critical Failure: {e}", exc_info=True)
        return ("Internal Server Error", 500)
