# Podcast-to-Spotify Automator: A Serverless Data Pipeline

This project is a cloud-native, automated data pipeline designed to synchronize audio recordings from Google Drive to a Spotify-compatible RSS feed hosted on GitHub. It is built with a focus on **Data Engineering best practices**, utilizing modern serverless architecture and Generative AI for metadata enrichment.

---

## 🏗️ Architecture & Data Engineering Logic

As a pipeline built by a Senior Data Engineer, this project moves beyond simple "scripting" by implementing a robust **Data Lifecycle Management** strategy:

### 1. The "Medallion" Logic (Bronze to Silver)

The pipeline treats Google Drive as a data lake with a structured workflow:

* **Landing Zone (Bronze):** New raw audio files (`.mp3`, `.m4a`, `.wav`) are dropped into a "Source" folder.
* **Processing:** The system extracts duration metadata, generates AI-driven summaries, and updates the GitHub-hosted XML.
* **Archive (Silver):** Once successfully committed to the feed, files are moved to a "Processed" folder to ensure **Idempotency** (no duplicate processing).

### 2. Generative AI Enrichment

Leveraging **Gemini 1.5 Flash**, the pipeline "listens" to each audio file to generate a 2-3 sentence Hebrew description. This transforms a simple file sync into an intelligent content management system.

### 3. Observability & Cost Monitoring

* **Log-Level Metrics:** Detailed logging tracks duration, file sizes, and successful GitHub commits.
* **Unit Economics:** The code includes an integrated cost calculator that logs the estimated USD cost of each AI inference run ($0.00002/sec) to GCP Cloud Logging.

---

## 🛠️ Tech Stack

* **Runtime:** Python 3.14 (utilizing the experimental JIT for performance).
* **Environment:** Dockerized (slim image) deployed on **Google Cloud Run**.
* **Secrets:** Secure cross-project access via **GCP Secret Manager**.
* **API Integrations:** * **Google Drive API v3** (Metadata & File Management).
* **Vertex AI / Gemini API** (Audio Summarization).
* **GitHub REST API** (Automated XML commits).


* **XML Engine:** `lxml` for maintaining strict RSS/iTunes/Anchor.fm namespaces and Hebrew CDATA integrity.

---

## 🚀 Key Features

* **Dynamic Extension Handling:** Automatically detects audio containers (m4a/mp3) and sets correct `enclosure` mime-types.
* **Serverless Scalability:** Scales to zero when not in use, triggered by a Cloud Scheduler (Cron) or Webhook.
* **Hebrew Language Support:** Fully optimized for RTL content and Hebrew character encoding in RSS readers.
* **Security First:** Uses Application Default Credentials (ADC) and IAM roles instead of hardcoded keys.

---

## 🔧 Infrastructure Setup

### Environment Variables

| Key | Description |
| --- | --- |
| `FOLDER_ID` | Landing folder for new recordings. |
| `PROCESSED_FOLDER_ID` | Archive folder for successfully synced files. |
| `GEMINI_API_KEY` | Vertex AI / Google AI Studio key. |
| `GITHUB_TOKEN` | Personal Access Token with repo scope. |

### Deployment

The project is deployed via a Docker container to ensure environment parity between local development and GCP.

```bash
docker build -t podcast-automator .
gcloud run deploy podcast-service --image gcr.io/[PROJECT_ID]/podcast-automator

```

---

## 👨‍💻 Author

**Yannay** *Senior Data Engineer*

---

## ⚠️ Troubleshooting: IAM & Permissions

In a cross-project serverless environment, 90% of deployment failures are identity-related. Below are the most common friction points for this pipeline and how to resolve them.

---

### 1. Error: `403 Forbidden` on Google Drive

**Symptom:** The script can see the files but fails when trying to move them to the `PROCESSED_FOLDER_ID`.

* **The Cause:** Moving a file in Drive requires the `files.update` permission, which is part of the **Editor** role.
* **The Fix:** Ensure the Service Account running your Cloud Run/Function has the **Editor** role (or a custom role with `https://www.googleapis.com/auth/drive`) on **both** the Source and Processed folders.
* *Note:* Sharing the folder with the Service Account's email address in the Google Drive UI is often the fastest way to grant this.



### 2. Error: `Secret Manager` Access Denied

**Symptom:** `google.api_core.exceptions.PermissionDenied: 403 Permission 'secretmanager.versions.access' denied`.

* **The Cause:** This usually happens when the secret is in a different project and the "bridge" hasn't been built.
* **The Fix:** 1.  Get the **Service Account email** from the "Podcast" project.
2.  Go to the **Secret Manager** in the "Security" project.
3.  Select the specific secret -> **Permissions** -> **Add Principal**.
4.  Assign the role: `roles/secretmanager.secretAccessor`.

### 3. Error: `Default Credentials` Not Found

**Symptom:** `google.auth.exceptions.DefaultCredentialsError`.

* **The Cause:** This typically happens during **local development** when the environment doesn't have access to your GCP identity.
* **The Fix:** Run the following command on your local machine to re-authenticate:
```bash
gcloud auth application-default login

```


This creates a local JSON file that the `google-auth` library will automatically detect.

### 4. Error: Gemini API `Quota Exceeded` or `API Not Enabled`

**Symptom:** `429 Too Many Requests` or `403 Generative Language API has not been used...`.

* **The Cause:** The `Generative Language API` must be enabled in the project **associated with the API Key or Service Account** you are using.
* **The Fix:**
1. Go to the [GCP Console API Library](https://console.cloud.google.com/apis/library).
2. Search for **Generative Language API**.
3. Ensure it is **Enabled** in the billing project.



---

### 🛡️ Best Practice: The "Principle of Least Privilege"

Instead of granting `roles/owner` or `roles/editor` at the project level, always bind roles to the specific resource:

* Grant `Secret Accessor` on the **Secret** itself.
* Grant `Drive Editor` on the **Folder** itself.
