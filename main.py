import base64
import os
import requests
import logging
import google.auth
from datetime import datetime
from lxml import etree
from googleapiclient.discovery import build
import google.generativeai as genai

# --- LOGGING CONFIGURATION ---
# Formatted for GCP Cloud Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

class PodcastAutomator:
    def __init__(self):
        # Configuration from Environment Variables
        self.source_folder = os.environ.get('FOLDER_ID')
        self.processed_folder = os.environ.get('PROCESSED_FOLDER_ID')
        self.github_token = os.environ.get('GITHUB_TOKEN')
        # self.prompt = os.environ.get('PROMPT')
        self.repo_name = "yemman/podcast-automator"
        self.file_path = "feed.xml"
        self.gh_api_url = f"https://api.github.com/repos/{self.repo_name}/contents/{self.file_path}"
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
        
        
        # Anchor.fm & iTunes standard namespaces
        self.nsmap = {
            'dc': "http://purl.org/dc/elements/1.1/",
            'content': "http://purl.org/rss/1.0/modules/content/",
            'itunes': "http://www.itunes.com/dtds/podcast-1.0.dtd",
            'anchor': "https://anchor.fm/xmlns",
            'atom': "http://www.w3.org/2005/Atom"
        }

    def get_drive_service(self):
        """Initializes Drive API with Application Default Credentials."""
        credentials, _ = google.auth.default()
        return build('drive', 'v3', credentials=credentials)

    def get_new_audio_files(self):
        """Fetches all audio files (mp3, m4a, etc) from the landing folder."""
        logger.info(f"Scanning source folder: {self.source_folder}")
        service = self.get_drive_service()
        
        query = f"'{self.source_folder}' in parents and mimeType contains 'audio/'"
        fields = "files(id, name, createdTime, size, mimeType, videoMediaMetadata)"
        
        results = service.files().list(q=query, fields=fields).execute()
        files = results.get('files', [])
        logger.info(f"Found {len(files)} new files in landing zone.")
        return files

    def move_to_processed(self, file_id):
        """Moves a file from Source to Processed folder after successful sync."""
        service = self.get_drive_service()
        file = service.files().get(fileId=file_id, fields='parents').execute()
        previous_parents = ",".join(file.get('parents'))

        service.files().update(
            fileId=file_id,
            addParents=self.processed_folder,
            removeParents=previous_parents,
            fields='id, parents'
        ).execute()
        logger.info(f"Archived file ID {file_id} to folder {self.processed_folder}")

    def fetch_current_feed(self):
        """Downloads existing feed.xml from GitHub."""
        logger.info("Fetching current feed.xml from GitHub...")
        headers = {"Authorization": f"token {self.github_token}"}
        resp = requests.get(self.gh_api_url, headers=headers)
        
        if resp.status_code == 200:
            data = resp.json()
            raw_xml = base64.b64decode(data['content'])
            return etree.fromstring(raw_xml), data['sha']
        
        logger.error(f"GitHub fetch failed: {resp.status_code}")
        return None, None

    def format_duration(self, millis_str):
        """Converts Drive's durationMillis to iTunes HH:MM:SS."""
        try:
            total_seconds = int(millis_str) // 1000
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            if hours > 0:
                return f"{hours:02}:{minutes:02}:{seconds:02}"
            return f"{minutes:02}:{seconds:02}"
        except (TypeError, ValueError):
            return "00:00"
            
    def get_ai_description(self, file_id, file_name):
        """Downloads audio and asks Gemini to summarize it."""
        try:
            logger.info(f"Generating AI description for {file_name}...")
            service = self.get_drive_service()
            
            # 1. Download audio to memory
            request = service.files().get_media(fileId=file_id)
            audio_data = request.execute()

            # 2. Call Gemini
            prompt = f"זהו שיעור תורה בעניין שמירת הלשון בשם '{file_name}'. הקשב לאודיו וסכם את עיקרי הדברים ב-2-3 משפטים עבור תיאור הפודקאסט."
            
            response = self.model.generate_content([
                prompt,
                {"mime_type": "audio/mpeg", "data": audio_data}
            ])
            
            return response.text.strip()
        except Exception as e:
            logger.warning(f"AI summary failed for {file_name}: {e}")
            raise Exception("Could not retrieve ai_description.")
            #return f"שיעור בנושא {file_name}" # Fallback

    def create_item(self, f):
        """Constructs a new <item> element with full metadata."""
        item = etree.Element("item")

        # Extract the extension from the filename (e.g., 'lesson.m4a' -> '.m4a')
        # If no extension is found, default to .mp3
        full_file_name = f.get('name', '')
        file_name, extension = os.path.splitext(full_file_name)
        if not extension:
            extension = ".mp3"
        
        # SET DYNAMIC DESCRIPTION USING AI
        ai_desc = self.get_ai_description(f['id'], file_name)
        
        # Title & Description (CDATA for Hebrew support)
        title = etree.SubElement(item, "title")
        title.text = etree.CDATA(file_name)
        
        desc = etree.SubElement(item, "description")
        desc.text = etree.CDATA(ai_desc) # The AI summary
        
        # Enclosure (The Direct Download URL)
        url = f"https://drive.google.com/uc?export=download&id={f['id']}&ext={extension}"
        etree.SubElement(item, "enclosure", 
                         url=url, 
                         length=str(f.get('size', 0)), 
                         type=f.get('mimeType', 'audio/mpeg'))
        
        # Basic Metadata
        etree.SubElement(item, "guid", isPermaLink="false").text = f['id']
        etree.SubElement(item, "pubDate").text = f['createdTime']
        
        # iTunes Metadata
        etree.SubElement(item, "{%s}explicit" % self.nsmap['itunes']).text = "false"
        
        # Duration from Drive Metadata
        vmm = f.get('videoMediaMetadata', {})
        if vmm.get('durationMillis'):
            duration = self.format_duration(vmm['durationMillis'])
            etree.SubElement(item, "{%s}duration" % self.nsmap['itunes']).text = duration

        return item

    def sync(self):
        """Main execution logic."""
        # 1. Check for files
        new_files = self.get_new_audio_files()
        if not new_files:
            logger.info("Pipeline idle: No new files to process.")
            return "No changes"

        # 2. Get existing XML
        root, sha = self.fetch_current_feed()
        if root is None:
            raise Exception("Could not retrieve base XML from GitHub.")

        # 3. Inject new items
        channel = root.find("channel")
        for f in new_files:
            new_item = self.create_item(f)
            # Insert at top of the list (after channel header info)
            channel.insert(10, new_item)

        # 4. Update Build Date
        lbd = channel.find("lastBuildDate")
        if lbd is not None:
            lbd.text = datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")

        # 5. Push to GitHub
        logger.info("Pushing updated XML to GitHub...")
        updated_xml = etree.tostring(root, encoding='UTF-8', xml_declaration=True, pretty_print=True)
        
        headers = {"Authorization": f"token {self.github_token}"}
        payload = {
            "message": f"🤖 Automated Update: Added {len(new_files)} episodes",
            "content": base64.b64encode(updated_xml).decode(),
            "sha": sha
        }
        
        put_resp = requests.put(self.gh_api_url, json=payload, headers=headers)
        
        if put_resp.status_code in [200, 201]:
            logger.info("GitHub successfully updated.")
            # 6. Archive files in Drive
            for f in new_files:
                self.move_to_processed(f['id'])
            return f"Processed {len(new_files)} episodes."
        else:
            raise Exception(f"GitHub push failed: {put_resp.text}")

# --- GCP ENTRY POINT ---
def drive_to_spotify(request):
    try:
        automator = PodcastAutomator()
        result = automator.sync()
        return (result, 200)
    except Exception as e:
        logger.error(f"CRITICAL ERROR: {str(e)}", exc_info=True)
        return (f"Internal Error: {str(e)}", 500)
