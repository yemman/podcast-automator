# 🎙️ My Automated Podcast Feed

This repository hosts the live RSS feed for my podcast, which is automatically synchronized from a Google Drive folder using Google Cloud Platform (GCP).

## 🚀 How it Works

1.  **Storage:** Audio files are uploaded to a specific folder in **Google Drive**.
2.  **Automation:** A **Google Cloud Function** runs on a daily schedule (via Cloud Scheduler).
3.  **Processing:** The script scans the Drive folder, generates a compliant Podcast RSS 2.0 XML file, and pushes it to this repository.
4.  **Distribution:** This GitHub repository serves the `feed.xml` file, which is consumed by **Spotify for Podcasters**.

## 🔗 The Feed URL
If you are setting this up in Spotify, use the "Raw" link to the feed:
`https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO_NAME/main/feed.xml`

## 🛠️ Tech Stack
* **Source:** Google Drive API
* **Logic:** Python 3.10 (running on GCP Cloud Functions)
* **Hosting:** GitHub Pages / GitHub Actions
* **RSS Standard:** Podcast RSS 2.0 (via `podgen`)

## 📁 Repository Structure
* `feed.xml`: The auto-generated RSS feed (do not edit manually).
* `README.md`: Project documentation.

## ⚠️ Maintenance Notes
* **File Formats:** Only `.mp3`, `.m4a`, or `.wav` files in the Drive folder will be included.
* **Permissions:** Ensure the Drive folder is shared with the GCP Service Account email and set to "Anyone with the link can view."
* **Sync Time:** The feed updates once every 24 hours at midnight UTC.

---
*Last updated: 01/03/2026*
