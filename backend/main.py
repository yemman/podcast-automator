"""
100% Local Podcast RSS Ingestion Pipeline using faster-whisper (ivrit-ai) & Ollama.
Outputs static JSON files and SEO sitemaps directly into frontend/public/ for Angular SSG.
"""

import os
import sys
import json
import time
import re
import logging
from logging.handlers import RotatingFileHandler
import hashlib
import tempfile
import argparse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse
from xml.sax.saxutils import escape as xml_escape

import requests
import feedparser
from slugify import slugify

DEFAULT_LOG_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "ingestion.log"))
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logger = logging.getLogger("podcast_ingestion")


def configure_logging(log_file: Optional[str] = None) -> str:
    """
    Configures terminal + rotating file logging (5 MB x 3 backups, UTF-8) without duplicating handlers.
    Returns the resolved log file path.
    """
    target_log = os.path.abspath(log_file or os.environ.get("PODCAST_LOG_FILE") or DEFAULT_LOG_FILE)
    log_dir = os.path.dirname(target_log)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    formatter = logging.Formatter(LOG_FORMAT)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        target_log,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    root_logger.addHandler(stream_handler)
    root_logger.addHandler(file_handler)
    return target_log


configure_logging()

DEFAULT_RSS_FEED_URL = "https://anchor.fm/s/e7fc5d7c/podcast/rss"
DEFAULT_WHISPER_MODEL = "ivrit-ai/whisper-large-v3-turbo-ct2"
DEFAULT_OLLAMA_MODEL = "gemma3:4b"
DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_SITE_URL = "https://silance-podcast-automator.web.app"
DEFAULT_OUTPUT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "data")
)

# Cache loaded WhisperModel instances across episodes in a batch
_WHISPER_MODEL_CACHE: Dict[Tuple[str, str, str, int], Any] = {}


def is_hebrew_text(text: str) -> bool:
    """Detects if text contains Hebrew unicode characters."""
    return any("\u0590" <= ch <= "\u05ff" for ch in (text or ""))


def generate_doc_id(guid: str) -> str:
    """Generates a stable, URL-safe episode ID from an episode GUID."""
    clean_hash = hashlib.sha256(guid.encode("utf-8")).hexdigest()[:24]
    return f"ep_{clean_hash}"


def normalize_published_date(raw_date: str) -> str:
    """Normalizes RSS RFC-2822 or ISO date strings to ISO-8601 UTC."""
    if not raw_date:
        return ""
    raw_date = raw_date.strip()
    try:
        dt = parsedate_to_datetime(raw_date)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        pass
    try:
        dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return raw_date


def _parse_sort_timestamp(date_str: str) -> float:
    """Parses a publishedAt string into a sortable Unix timestamp."""
    if not date_str:
        return 0.0
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).timestamp()
    except Exception:
        try:
            return parsedate_to_datetime(date_str).timestamp()
        except Exception:
            return 0.0


def _atomic_write_text(target_path: str, content: str) -> None:
    """Writes text atomically via a temporary file in the same directory."""
    parent = os.path.dirname(os.path.abspath(target_path))
    os.makedirs(parent, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=parent, prefix=".tmp_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, target_path)
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        raise


def _atomic_write_json(target_path: str, data: Any) -> None:
    """Writes JSON atomically with readable UTF-8 formatting."""
    _atomic_write_text(target_path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _strip_html(raw: str) -> str:
    """Strips HTML tags from RSS descriptions cleanly."""
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", text).strip()


class LocalEpisodeStore:
    """
    File-based episode repository outputting JSON files for Angular SSG:
      - <output_dir>/episodes-index.json (catalog without transcript)
      - <output_dir>/episodes/<id>.json (full episode including transcript)
      - <public_dir>/sitemap.xml and <public_dir>/robots.txt
    """

    def __init__(self, output_dir: str = DEFAULT_OUTPUT_DIR, site_url: str = DEFAULT_SITE_URL):
        self.output_dir = os.path.abspath(output_dir)
        self.episodes_dir = os.path.join(self.output_dir, "episodes")
        self.index_path = os.path.join(self.output_dir, "episodes-index.json")
        self.public_dir = os.path.dirname(self.output_dir)
        self.sitemap_path = os.path.join(self.public_dir, "sitemap.xml")
        self.robots_path = os.path.join(self.public_dir, "robots.txt")
        self.site_url = site_url.rstrip("/")

        os.makedirs(self.episodes_dir, exist_ok=True)

    def load_index(self) -> List[Dict[str, Any]]:
        """Loads the episode catalog index sorted newest-first."""
        if not os.path.exists(self.index_path):
            return []
        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception as err:
            logger.warning(f"Failed to read index at {self.index_path}: {err}")
            return []

    def exists(self, guid: str) -> bool:
        """Checks whether an episode GUID is already present in the local store."""
        doc_id = generate_doc_id(guid)
        if os.path.exists(os.path.join(self.episodes_dir, f"{doc_id}.json")):
            return True
        for item in self.load_index():
            if item.get("guid") == guid or item.get("id") == doc_id:
                return True
        return False

    def save_episode(self, episode: Dict[str, Any]) -> None:
        """Saves full episode JSON, updates episodes-index.json, and regenerates SEO files."""
        ep_id = episode["id"]
        episode_path = os.path.join(self.episodes_dir, f"{ep_id}.json")
        _atomic_write_json(episode_path, episode)

        # Build index entry without full transcript to keep catalog lightweight
        index_entry = {k: v for k, v in episode.items() if k != "transcript"}

        index = self.load_index()
        updated = False
        for idx, existing in enumerate(index):
            if existing.get("id") == ep_id or existing.get("guid") == episode.get("guid"):
                index[idx] = index_entry
                updated = True
                break
        if not updated:
            index.append(index_entry)

        index.sort(key=lambda item: _parse_sort_timestamp(item.get("publishedAt", "")), reverse=True)
        _atomic_write_json(self.index_path, index)
        self.write_seo_files(index)

    def write_seo_files(self, index: Optional[List[Dict[str, Any]]] = None) -> None:
        """Generates sitemap.xml and robots.txt for static hosting SEO."""
        entries = index if index is not None else self.load_index()
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
            "  <url>",
            f"    <loc>{xml_escape(self.site_url)}/</loc>",
            "    <changefreq>weekly</changefreq>",
            "    <priority>1.0</priority>",
            "  </url>",
        ]
        for ep in entries:
            ep_id = ep.get("id")
            if not ep_id:
                continue
            loc = f"{self.site_url}/episode/{ep_id}"
            lastmod = ep.get("publishedAt") or ep.get("ingestedAt") or ""
            lines.append("  <url>")
            lines.append(f"    <loc>{xml_escape(loc)}</loc>")
            if lastmod:
                lines.append(f"    <lastmod>{xml_escape(lastmod)}</lastmod>")
            lines.append("    <changefreq>monthly</changefreq>")
            lines.append("    <priority>0.8</priority>")
            lines.append("  </url>")
        lines.append("</urlset>")

        _atomic_write_text(self.sitemap_path, "\n".join(lines) + "\n")
        robots = (
            "User-agent: *\n"
            "Allow: /\n\n"
            f"Sitemap: {self.site_url}/sitemap.xml\n"
        )
        _atomic_write_text(self.robots_path, robots)


def download_audio_file(audio_url: str, output_path: str, timeout: int = 180) -> int:
    """
    Downloads an audio file from a remote enclosure URL with streaming to prevent memory spikes.
    Supports file:// URLs for local development and testing.
    Returns the downloaded file size in bytes.
    """
    logger.info(f"Downloading audio from {audio_url} to {output_path}...")

    if audio_url.startswith("file://"):
        import shutil
        local_path = audio_url[7:]
        if os.path.exists(local_path):
            shutil.copyfile(local_path, output_path)
            size = os.path.getsize(output_path)
            logger.info(f"Copied local audio file ({size} bytes)")
            return size
        with open(output_path, "wb") as f:
            f.write(b"ID3\x03\x00\x00\x00\x00\x00#DUMMY_MP3_AUDIO_STREAM_DATA")
        return os.path.getsize(output_path)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "*/*"
    }
    with requests.get(audio_url, stream=True, headers=headers, timeout=timeout, allow_redirects=True) as response:
        response.raise_for_status()
        bytes_written = 0
        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
                    bytes_written += len(chunk)

    logger.info(f"Successfully downloaded audio file: {bytes_written} bytes ({bytes_written / (1024 * 1024):.2f} MB)")
    return bytes_written


def _format_timestamp(seconds: float) -> str:
    """Formats seconds into [HH:MM:SS]."""
    total = max(0, int(seconds))
    hrs = total // 3600
    mins = (total % 3600) // 60
    secs = total % 60
    return f"[{hrs:02d}:{mins:02d}:{secs:02d}]"


def _get_whisper_model(model_name: str, device: str, compute_type: str, cpu_threads: int):
    """Loads and caches faster-whisper WhisperModel."""
    key = (model_name, device, compute_type, cpu_threads)
    if key not in _WHISPER_MODEL_CACHE:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "faster-whisper is not installed. Run: pip install -r backend/requirements.txt"
            ) from exc

        logger.info(
            f"Loading faster-whisper model '{model_name}' "
            f"(device={device}, compute_type={compute_type}, cpu_threads={cpu_threads})..."
        )
        _WHISPER_MODEL_CACHE[key] = WhisperModel(
            model_name,
            device=device,
            compute_type=compute_type,
            cpu_threads=cpu_threads,
        )
    return _WHISPER_MODEL_CACHE[key]


def decode_audio_compat(audio_path: str, sampling_rate: int = 16000):
    """
    Decodes an audio file into a 16kHz mono float32 numpy waveform using PyAV.
    Avoids faster-whisper's `metadata_errors="ignore"` kwarg removed in PyAV 19+.
    """
    import gc
    import io
    import itertools
    import av
    import numpy as np

    resampler = av.audio.resampler.AudioResampler(
        format="s16",
        layout="mono",
        rate=sampling_rate,
    )
    raw_buffer = io.BytesIO()
    dtype = None

    def _iter_valid_frames(frames):
        iterator = iter(frames)
        while True:
            try:
                yield next(iterator)
            except StopIteration:
                break
            except av.error.InvalidDataError:
                continue

    def _group_frames(frames, num_samples: int = 500000):
        fifo = av.audio.fifo.AudioFifo()
        for frame in frames:
            frame.pts = None
            fifo.write(frame)
            if fifo.samples >= num_samples:
                yield fifo.read()
        if fifo.samples > 0:
            yield fifo.read()

    with av.open(audio_path, mode="r") as container:
        frames = container.decode(audio=0)
        frames = _iter_valid_frames(frames)
        frames = _group_frames(frames, 500000)
        for grouped in itertools.chain(frames, [None]):
            for resampled in resampler.resample(grouped):
                array = resampled.to_ndarray()
                dtype = array.dtype
                raw_buffer.write(array)

    del resampler
    gc.collect()

    if dtype is None:
        return np.zeros(0, dtype=np.float32)

    audio = np.frombuffer(raw_buffer.getbuffer(), dtype=dtype)
    return audio.astype(np.float32) / 32768.0


def transcribe_audio_local(
    audio_path: str,
    language: Optional[str] = "he",
    model_name: str = DEFAULT_WHISPER_MODEL,
    device: str = "cpu",
    compute_type: str = "int8",
    cpu_threads: Optional[int] = None,
) -> str:
    """
    Transcribes an audio file locally using faster-whisper (ivrit-ai for Hebrew).
    Groups segments into readable paragraphs with [HH:MM:SS] timestamps.
    """
    threads = cpu_threads or min(os.cpu_count() or 4, 8)
    model = _get_whisper_model(model_name, device, compute_type, threads)

    logger.info(f"Decoding and transcribing audio locally ({os.path.basename(audio_path)}, language={language})...")
    audio_waveform = decode_audio_compat(audio_path, sampling_rate=16000)
    segments, info = model.transcribe(
        audio_waveform,
        language=language,
        vad_filter=True,
        beam_size=5,
    )
    logger.info(
        f"Detected language={getattr(info, 'language', language)} "
        f"(prob={getattr(info, 'language_probability', 1.0):.2f})"
    )

    paragraphs: List[str] = []
    current_texts: List[str] = []
    para_start_time: Optional[float] = None

    for seg in segments:
        text = (seg.text or "").strip()
        if not text:
            continue

        if para_start_time is None:
            para_start_time = seg.start

        current_texts.append(text)
        elapsed = seg.end - para_start_time
        if len(current_texts) >= 5 or elapsed >= 45.0:
            paragraphs.append(f"{_format_timestamp(para_start_time)} {' '.join(current_texts)}")
            current_texts = []
            para_start_time = None

    if current_texts and para_start_time is not None:
        paragraphs.append(f"{_format_timestamp(para_start_time)} {' '.join(current_texts)}")

    return "\n\n".join(paragraphs).strip()


def _build_fallback_enrichment(
    title: str,
    transcript: str,
    description: str,
    is_heb: bool,
) -> Dict[str, Any]:
    """Builds a deterministic 2-paragraph summary and keywords when LLM is skipped/offline."""
    clean_desc = _strip_html(description)
    excerpt = re.sub(r"\[\d{2}:\d{2}:\d{2}\]\s*", "", transcript or "").strip()[:320]

    if is_heb:
        p1 = (
            f"בשיעור זה, \"{title}\", מובאים עיקרי הדברים והבירור ההלכתי והמוסרי מתוך סדרת השיעורים. "
            f"{clean_desc}".strip()
        )
        p2 = (
            f"מתוך התמלול המלא: {excerpt}..."
            if excerpt
            else "האזינו לשיעור המלא וקראו את התמלול המפורט בעמוד הפרק."
        )
        keywords = [
            "חפץ חיים",
            "שמירת הלשון",
            "מוסר והלכה",
            "שיעור תורה",
            "תפארת ישראל",
            "רמת גן",
            "מי האיש החפץ חיים",
            "יהדות",
        ]
    else:
        p1 = f"In '{title}', this episode covers key ideas and practical takeaways. {clean_desc}".strip()
        p2 = (
            f"From the full transcript: {excerpt}..."
            if excerpt
            else "Listen to the full episode audio and explore the complete verbatim transcript on this page."
        )
        slug_words = [w.lower() for w in title.replace("-", " ").split() if len(w) > 3][:5]
        keywords = list(dict.fromkeys(["podcast", "transcript", "audio", *slug_words]))

    return {
        "summary": f"{p1}\n\n{p2}",
        "keywords": keywords,
    }


def validate_enrichment_output(
    data: Dict[str, Any],
    fallback_title: str,
    transcript: str = "",
    description: str = "",
    is_heb: bool = True,
) -> Dict[str, Any]:
    """Validates and normalizes local LLM JSON output to ensure 2-paragraph summary and keywords list."""
    fallback = _build_fallback_enrichment(fallback_title, transcript, description, is_heb)

    raw_summary = data.get("summary", "")
    if isinstance(raw_summary, list):
        summary = "\n\n".join(str(p).strip() for p in raw_summary if str(p).strip())
    else:
        summary = str(raw_summary).strip()

    if not summary:
        summary = fallback["summary"]

    keywords = data.get("keywords", [])
    if isinstance(keywords, str):
        keywords = [k.strip().lstrip("#") for k in keywords.split(",") if k.strip()]
    elif isinstance(keywords, list):
        keywords = [str(k).strip().lstrip("#") for k in keywords if str(k).strip()]
    else:
        keywords = []

    if not keywords:
        keywords = fallback["keywords"]

    return {
        "summary": summary,
        "keywords": keywords[:15],
    }


def summarize_with_ollama(
    transcript: str,
    title: str,
    description: str,
    is_heb: bool = True,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    ollama_model: str = DEFAULT_OLLAMA_MODEL,
    skip_llm: bool = False,
) -> Dict[str, Any]:
    """
    Generates a 2-paragraph summary and SEO keywords list from the transcript via local Ollama.
    Falls back cleanly if skip_llm is True or Ollama is unreachable.
    """
    if skip_llm:
        logger.info("Skipping local Ollama LLM step (--skip-llm enabled). Using fallback summary.")
        return _build_fallback_enrichment(title, transcript, description, is_heb)

    clean_desc = _strip_html(description)
    truncated_transcript = (transcript or "")[:18000]
    lang_instruction = (
        "Write BOTH summary paragraphs and all SEO keywords in fluent Hebrew matching the lesson."
        if is_heb
        else "Write BOTH summary paragraphs and SEO keywords in the spoken language of the transcript."
    )

    prompt = f"""You are an expert podcast editor and SEO specialist.
Episode Title: {title}
Episode Description: {clean_desc}
Language Rule: {lang_instruction}

Transcript Excerpt:
\"\"\"
{truncated_transcript}
\"\"\"

Return ONLY a valid JSON object with exactly two keys:
1. "summary": A concise, engaging summary consisting of EXACTLY two paragraphs separated by "\\n\\n".
2. "keywords": An array of 8 to 12 relevant SEO keyword phrases.

Example format:
{{
  "summary": "Paragraph 1...\\n\\nParagraph 2...",
  "keywords": ["keyword1", "keyword2"]
}}
"""

    endpoint = f"{ollama_url.rstrip('/')}/api/generate"
    payload = {
        "model": ollama_model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "num_ctx": 16384,
            "temperature": 0.2,
        },
    }

    try:
        logger.info(f"Generating 2-paragraph summary & SEO keywords with Ollama ({ollama_model})...")
        response = requests.post(endpoint, json=payload, timeout=300)
        response.raise_for_status()
        body = response.json()
        raw_json = body.get("response", "").strip()
        parsed = json.loads(raw_json)
        return validate_enrichment_output(parsed, title, transcript, description, is_heb)
    except Exception as err:
        logger.warning(
            f"Ollama unavailable or returned invalid response ({err}). "
            "Falling back to deterministic summary while preserving full transcript."
        )
        return _build_fallback_enrichment(title, transcript, description, is_heb)


def generate_mock_enrichment(title: str, description: str, is_heb: bool) -> Dict[str, Any]:
    """Produces realistic synthetic transcript, 2-paragraph summary, and keywords for dry runs & tests."""
    clean_desc = _strip_html(description)
    if is_heb:
        first_para = (
            f"בפרק זה מתוך סדרת השיעורים בספר 'חפץ חיים' בבית הכנסת תפארת ישראל, נעסוק בהרחבה בנושא: '{title}'. "
            f"{clean_desc[:250]} השיעור מנתח את מקורות ההלכה והמוסר ומנגיש אותם בצורה בהירה ואקטואלית לחיי היומיום."
        )
        second_para = (
            "בחלקו השני של השיעור מושם דגש על שורשי מידות הנפש וההתמודדות עם יצר הרע, תוך הדגשת מידת הסבלנות, הביטחון ואהבת ישראל. "
            "השיעור נחתם בעצות מעשיות לתיקון המידות, התרחקות מוחלטת מלשון הרע ומחלוקת, והקפדה על דיבור נקי ומקרב."
        )
        keywords = [
            "חפץ חיים",
            "שמירת הלשון",
            "תפארת ישראל",
            "שיעור תורה",
            "מוסר והלכה",
            "לשון הרע",
            "רמת גן",
            "יהדות",
            "מי האיש החפץ חיים",
        ]
        transcript = (
            f"[00:00:01] שיעור בספר חפץ חיים, בית הכנסת תפארת ישראל. פרק: '{title}'.\n\n"
            "[00:00:25] פתיחה: שלום וברכה לכל הלומדים והמאזינים. היום נמשיך בלימודנו בספר הקדוש חפץ חיים, "
            "ונעמיק בביאור שער התבונה ודרכי השמירה על כוח הדיבור.\n\n"
            "[00:05:10] ביאור העניין: חז\"ל לימדו אותנו כי החיים והמוות ביד לשון. כאשר אדם מתבונן במקורות הכעס "
            "והמחלוקת, הוא מגלה שרוב המעידות נובעות מחוסר שימת לב ומאימפולסיביות רגעית.\n\n"
            "[00:15:40] הלכה למעשה: לכן חובתנו לפתח מודעות עצמית מתמדת, לעצור רגע לפני שאנו מוציאים מילה מפינו, "
            "ולשקול האם דברינו בונים או חלילה מקלקלים.\n\n"
            "[00:30:15] סיכום: יהי רצון שנזכה כולנו לנצור לשוננו מרע ושפתינו מדבר מרמה, ונזכה לחיים ארוכים וטובים. "
            "תודה רבה לכל המאזינים וערב מבורך!"
        )
    else:
        first_para = (
            f"In this episode titled '{title}', the discussion explores key themes and practical strategies. "
            f"{clean_desc[:250]} The speakers break down core concepts into actionable takeaways."
        )
        second_para = (
            "The second half focuses on real-world workflows, observability, and long-term sustainability, "
            "concluding with concrete recommendations for listeners."
        )
        slug_words = [w.lower() for w in title.replace("-", " ").split() if len(w) > 3][:5]
        keywords = list(dict.fromkeys(["podcast", "audio transcript", "seo", "local ai", *slug_words]))
        transcript = (
            f"[00:00:00] Welcome back to the podcast. Today's topic is '{title}'.\n\n"
            "[00:01:15] Let's walk through the core architecture and practical insights step by step.\n\n"
            "[00:10:20] Thank you for listening, and we'll see you in the next episode!"
        )

    return {
        "transcript": transcript,
        "summary": f"{first_para}\n\n{second_para}",
        "keywords": keywords,
    }


def find_audio_enclosure(entry: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], Optional[int]]:
    """Extracts audio URL, MIME type, and file length from an RSS entry enclosure."""
    enclosures = entry.get("enclosures", [])
    for enc in enclosures:
        url = enc.get("href") or enc.get("url")
        m_type = enc.get("type", "").lower()
        length = enc.get("length")
        if url and ("audio" in m_type or url.endswith((".mp3", ".m4a", ".aac", ".ogg", ".wav"))):
            return url, m_type or "audio/mpeg", int(length) if length and str(length).isdigit() else None

    for link in entry.get("links", []):
        if link.get("rel") == "enclosure":
            url = link.get("href")
            m_type = link.get("type", "").lower()
            length = link.get("length")
            if url and ("audio" in m_type or url.endswith((".mp3", ".m4a", ".aac", ".ogg", ".wav"))):
                return url, m_type or "audio/mpeg", int(length) if length and str(length).isdigit() else None

    return None, None, None


def process_rss_feed(
    feed_url: str = DEFAULT_RSS_FEED_URL,
    max_episodes: int = 5,
    force_reprocess: bool = False,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    whisper_model: str = DEFAULT_WHISPER_MODEL,
    whisper_device: str = "cpu",
    compute_type: str = "int8",
    cpu_threads: Optional[int] = None,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    ollama_model: str = DEFAULT_OLLAMA_MODEL,
    skip_llm: bool = False,
    site_url: str = DEFAULT_SITE_URL,
    mock_ai: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    100% Local RSS ingestion pipeline:
      1. Parse RSS feed XML
      2. Check LocalEpisodeStore for existing episode GUIDs
      3. Download audio enclosure to temporary file
      4. Transcribe locally with faster-whisper (ivrit-ai) & summarize with Ollama
      5. Save episode JSON + episodes-index.json + sitemap.xml + robots.txt
    """
    use_mock = (
        mock_ai
        if mock_ai is not None
        else os.environ.get("MOCK_LOCAL_AI", "false").lower() == "true"
    )

    logger.info(f"Parsing RSS feed: {feed_url}")
    feed = feedparser.parse(feed_url)

    if feed.bozo and not feed.entries:
        err_msg = f"Failed to parse RSS feed from {feed_url}: {feed.get('bozo_exception', 'Unknown error')}"
        logger.error(err_msg)
        return {
            "status": "error",
            "message": err_msg,
            "feed_url": feed_url,
            "episodes_processed": [],
            "episodes_skipped": 0,
            "episodes_failed": 0,
        }

    feed_meta = feed.get("feed", {})
    podcast_title = feed_meta.get("title", "Untitled Podcast")
    podcast_author = feed_meta.get("author") or feed_meta.get("itunes_author", "Unknown Author")
    feed_image = (
        feed_meta.get("image", {}).get("href")
        or feed_meta.get("itunes_image")
        or (feed_meta.get("image") if isinstance(feed_meta.get("image"), str) else None)
    )
    feed_lang = (feed_meta.get("language") or "he").lower()

    store = LocalEpisodeStore(output_dir=output_dir, site_url=site_url)
    processed_episodes = []
    skipped_count = 0
    failed_count = 0

    entries_to_process = feed.entries[:max_episodes] if max_episodes > 0 else feed.entries

    for entry in entries_to_process:
        guid = entry.get("id") or entry.get("guid") or entry.get("link")
        title = entry.get("title", "Untitled Episode")
        raw_description = entry.get("summary") or entry.get("description") or ""
        clean_description = _strip_html(raw_description)

        if not guid:
            logger.warning(f"Skipping entry '{title}' without GUID/id.")
            skipped_count += 1
            continue

        doc_id = generate_doc_id(guid)

        if not force_reprocess and store.exists(guid):
            logger.info(f"Episode already exists locally (GUID: {guid}, Title: '{title}'). Skipping.")
            skipped_count += 1
            continue

        audio_url, audio_type, audio_length = find_audio_enclosure(entry)
        if not audio_url:
            logger.warning(f"No audio enclosure found for episode '{title}' (GUID: {guid}). Skipping.")
            skipped_count += 1
            continue

        logger.info(f"Processing new episode: '{title}' (GUID: {guid})")

        temp_audio_file = None
        try:
            parsed_url = urlparse(audio_url)
            ext = os.path.splitext(parsed_url.path)[1] or ".m4a"
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                temp_audio_file = tmp.name

            actual_size = download_audio_file(audio_url, temp_audio_file)
            audio_length = audio_length or actual_size

            is_heb = feed_lang.startswith("he") or is_hebrew_text(title) or is_hebrew_text(clean_description)

            if use_mock:
                logger.info(f"MOCK_LOCAL_AI active. Generating mock enrichment for '{title}'.")
                ai_data = generate_mock_enrichment(title, clean_description, is_heb)
            else:
                transcript = transcribe_audio_local(
                    audio_path=temp_audio_file,
                    language="he" if is_heb else None,
                    model_name=whisper_model,
                    device=whisper_device,
                    compute_type=compute_type,
                    cpu_threads=cpu_threads,
                )
                summary_data = summarize_with_ollama(
                    transcript=transcript,
                    title=title,
                    description=clean_description,
                    is_heb=is_heb,
                    ollama_url=ollama_url,
                    ollama_model=ollama_model,
                    skip_llm=skip_llm,
                )
                ai_data = {
                    "transcript": transcript or f"Transcript unavailable for {title}.",
                    "summary": summary_data["summary"],
                    "keywords": summary_data["keywords"],
                }

            raw_pub_date = entry.get("published") or entry.get("pubDate") or ""
            pub_date = normalize_published_date(raw_pub_date)
            itunes_duration = entry.get("itunes_duration") or ""
            episode_image = (
                entry.get("image", {}).get("href")
                or entry.get("itunes_image")
                or feed_image
            )
            slug = slugify(f"{title}-{guid[:8]}") or doc_id

            episode_document = {
                "id": doc_id,
                "guid": guid,
                "title": title,
                "slug": slug,
                "description": clean_description,
                "summary": ai_data["summary"],
                "transcript": ai_data["transcript"],
                "keywords": ai_data["keywords"],
                "audioUrl": audio_url,
                "audioType": audio_type,
                "audioLength": audio_length,
                "duration": str(itunes_duration),
                "publishedAt": pub_date,
                "podcastTitle": podcast_title,
                "podcastAuthor": podcast_author,
                "imageUrl": episode_image or "",
                "sourceFeedUrl": feed_url,
                "ingestedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "status": "published",
            }

            store.save_episode(episode_document)
            logger.info(f"Saved episode locally to '{store.episodes_dir}/{doc_id}.json'")

            processed_episodes.append({
                "id": doc_id,
                "guid": guid,
                "title": title,
                "slug": slug,
                "keywords_count": len(ai_data["keywords"]),
                "summary_length": len(ai_data["summary"]),
                "transcript_length": len(ai_data["transcript"]),
            })

        except Exception as err:
            logger.exception(f"Failed processing episode '{title}': {err}")
            failed_count += 1
        finally:
            if temp_audio_file and os.path.exists(temp_audio_file):
                try:
                    os.unlink(temp_audio_file)
                except OSError:
                    pass

    return {
        "status": "success",
        "feed_title": podcast_title,
        "feed_url": feed_url,
        "output_dir": store.output_dir,
        "total_feed_entries": len(feed.entries),
        "episodes_processed": processed_episodes,
        "episodes_skipped": skipped_count,
        "episodes_failed": failed_count,
    }


def cli_main():
    """Command Line Interface for local podcast ingestion."""
    parser = argparse.ArgumentParser(description="100% Local Podcast RSS Ingestion Pipeline (faster-whisper + Ollama)")
    parser.add_argument("--feed-url", type=str, default=os.environ.get("RSS_FEED_URL", DEFAULT_RSS_FEED_URL), help="RSS Feed URL")
    parser.add_argument("--max-episodes", type=int, default=3, help="Max episodes to process (0 = all)")
    parser.add_argument("--force", action="store_true", help="Force reprocess already ingested episodes")
    parser.add_argument("--mock", action="store_true", help="Use mock transcription & summary for fast dry-run testing")
    parser.add_argument("--skip-llm", action="store_true", help="Skip Ollama summarization and use fallback description summary")
    parser.add_argument("--whisper-model", type=str, default=os.environ.get("WHISPER_MODEL", DEFAULT_WHISPER_MODEL), help="faster-whisper model name or path")
    parser.add_argument("--whisper-device", type=str, default=os.environ.get("WHISPER_DEVICE", "cpu"), help="Device: cpu or cuda")
    parser.add_argument("--compute-type", type=str, default=os.environ.get("WHISPER_COMPUTE_TYPE", "int8"), help="Compute type: int8, float16, float32")
    parser.add_argument("--cpu-threads", type=int, default=None, help="CPU threads for faster-whisper")
    parser.add_argument("--ollama-model", type=str, default=os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL), help="Ollama model tag")
    parser.add_argument("--ollama-url", type=str, default=os.environ.get("OLLAMA_URL", DEFAULT_OLLAMA_URL), help="Ollama server base URL")
    parser.add_argument("--output-dir", type=str, default=os.environ.get("PODCAST_DATA_DIR", DEFAULT_OUTPUT_DIR), help="Directory for episodes-index.json and episodes/")
    parser.add_argument("--site-url", type=str, default=os.environ.get("SITE_URL", DEFAULT_SITE_URL), help="Public site URL for sitemap.xml and robots.txt")
    parser.add_argument("--log-file", type=str, default=os.environ.get("PODCAST_LOG_FILE", DEFAULT_LOG_FILE), help="Path to rotating ingestion log file")
    args = parser.parse_args()

    configure_logging(args.log_file)

    res = process_rss_feed(
        feed_url=args.feed_url,
        max_episodes=args.max_episodes,
        force_reprocess=args.force,
        output_dir=args.output_dir,
        whisper_model=args.whisper_model,
        whisper_device=args.whisper_device,
        compute_type=args.compute_type,
        cpu_threads=args.cpu_threads,
        ollama_url=args.ollama_url,
        ollama_model=args.ollama_model,
        skip_llm=args.skip_llm,
        site_url=args.site_url,
        mock_ai=True if args.mock else None,
    )
    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    cli_main()
