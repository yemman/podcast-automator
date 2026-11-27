"""
Unit & Integration Tests for 100% Local RSS Ingestion Pipeline (faster-whisper + Ollama + Local JSON Store)
"""

import os
import json
import tempfile
import unittest
from unittest.mock import patch, MagicMock

import requests

os.environ["MOCK_LOCAL_AI"] = "true"

from main import (
    generate_doc_id,
    find_audio_enclosure,
    validate_enrichment_output,
    is_predominantly_hebrew,
    summarize_with_ollama,
    decode_audio_compat,
    configure_logging,
    DEFAULT_LOG_FILE,
    LocalEpisodeStore,
    process_rss_feed,
)


class TestLocalRssIngestionPipeline(unittest.TestCase):

    def setUp(self):
        self.sample_feed_path = os.path.join(os.path.dirname(__file__), "sample_feed.xml")

    def test_generate_doc_id_consistency(self):
        guid = "unique-episode-guid-12345"
        doc_id1 = generate_doc_id(guid)
        doc_id2 = generate_doc_id(guid)
        self.assertEqual(doc_id1, doc_id2)
        self.assertTrue(doc_id1.startswith("ep_"))
        self.assertEqual(len(doc_id1), 27)

    def test_find_audio_enclosure(self):
        entry_with_enclosure = {
            "enclosures": [
                {
                    "href": "https://cdn.example.com/audio/ep01.mp3",
                    "type": "audio/mpeg",
                    "length": "15420000",
                }
            ]
        }
        url, m_type, length = find_audio_enclosure(entry_with_enclosure)
        self.assertEqual(url, "https://cdn.example.com/audio/ep01.mp3")
        self.assertEqual(m_type, "audio/mpeg")
        self.assertEqual(length, 15420000)

        entry_without_audio = {
            "enclosures": [
                {
                    "href": "https://cdn.example.com/image.jpg",
                    "type": "image/jpeg",
                }
            ]
        }
        url2, _, _ = find_audio_enclosure(entry_without_audio)
        self.assertIsNone(url2)

    def test_validate_enrichment_output(self):
        raw = {
            "summary": "First paragraph.\n\nSecond paragraph.",
            "keywords": ["חפץ חיים", "#שמירת הלשון", "מוסר"],
        }
        result = validate_enrichment_output(raw, "Test Title", is_heb=True)
        self.assertEqual(result["summary"], "First paragraph.\n\nSecond paragraph.")
        self.assertEqual(result["keywords"], ["חפץ חיים", "שמירת הלשון", "מוסר"])

        fallback = validate_enrichment_output({}, "Fallback Title", transcript="שלום לכולם", is_heb=True)
        self.assertIn("Fallback Title", fallback["summary"])
        self.assertIn("\n\n", fallback["summary"])
        self.assertIsInstance(fallback["keywords"], list)
        self.assertGreater(len(fallback["keywords"]), 0)

    def test_local_store_save_dedupe_and_sitemap(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            public_dir = os.path.join(tmpdir, "public")
            data_dir = os.path.join(public_dir, "data")
            store = LocalEpisodeStore(output_dir=data_dir, site_url="https://example.web.app")

            guid = "test-guid-already-ingested"
            doc_id = generate_doc_id(guid)
            self.assertFalse(store.exists(guid))

            episode = {
                "id": doc_id,
                "guid": guid,
                "title": "פרק ניסיון",
                "slug": "perek-nisayon",
                "description": "תיאור",
                "summary": "פסקה 1\n\nפסקה 2",
                "transcript": "[00:00:01] טקסט מלא של התמלול",
                "keywords": ["חפץ חיים", "מוסר"],
                "audioUrl": "https://cdn.example.com/ep.m4a",
                "publishedAt": "2026-09-20T10:00:00Z",
                "podcastTitle": "מי האיש החפץ חיים",
            }
            store.save_episode(episode)

            # Deduplication check
            self.assertTrue(store.exists(guid))

            # Index omits transcript
            index = store.load_index()
            self.assertEqual(len(index), 1)
            self.assertNotIn("transcript", index[0])
            self.assertEqual(index[0]["title"], "פרק ניסיון")

            # Full episode JSON preserves transcript
            ep_file = os.path.join(data_dir, "episodes", f"{doc_id}.json")
            self.assertTrue(os.path.exists(ep_file))
            with open(ep_file, "r", encoding="utf-8") as f:
                saved_full = json.load(f)
            self.assertEqual(saved_full["transcript"], "[00:00:01] טקסט מלא של התמלול")

            # Sitemap and robots.txt generated
            self.assertTrue(os.path.exists(os.path.join(public_dir, "sitemap.xml")))
            self.assertTrue(os.path.exists(os.path.join(public_dir, "robots.txt")))
            with open(os.path.join(public_dir, "sitemap.xml"), "r", encoding="utf-8") as f:
                sitemap_xml = f.read()
            self.assertIn(f"https://example.web.app/episode/{doc_id}", sitemap_xml)

    @patch("main.requests.post")
    def test_summarize_with_ollama_mocked_http(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "response": json.dumps({
                "summary": "סיכום פסקה ראשונה בעברית מלאה.\n\nסיכום פסקה שנייה בעברית מלאה.",
                "keywords": ["חפץ חיים", "לשון הרע", "שמירת הלשון"],
            })
        }
        mock_post.return_value = mock_resp

        res = summarize_with_ollama(
            transcript="[00:00:01] שיעור חפץ חיים",
            title="פרק א",
            description="תיאור",
            is_heb=True,
        )
        self.assertEqual(res["summary"], "סיכום פסקה ראשונה בעברית מלאה.\n\nסיכום פסקה שנייה בעברית מלאה.")
        self.assertEqual(res["keywords"], ["חפץ חיים", "לשון הרע", "שמירת הלשון"])
        self.assertEqual(mock_post.call_args.kwargs["json"]["options"]["num_thread"], 4)

        # Retries when first attempt returns English and succeeds on Hebrew second attempt
        eng_resp = MagicMock()
        eng_resp.raise_for_status.return_value = None
        eng_resp.json.return_value = {
            "response": json.dumps({
                "summary": "This episode delves into speech laws.\n\nSecond paragraph in English.",
                "keywords": ["חפץ חיים"],
            })
        }
        heb_resp = MagicMock()
        heb_resp.raise_for_status.return_value = None
        heb_resp.json.return_value = {
            "response": json.dumps({
                "summary": "הפרק עוסק בשמירת הלשון ובהלכות דיבור.\n\nבחלקו השני מוסברים עיקרי העבודה המוסרית.",
                "keywords": ["שמירת הלשון", "מוסר"],
            })
        }
        mock_post.side_effect = [eng_resp, heb_resp]
        retried_res = summarize_with_ollama(
            transcript="[00:00:01] שיעור חפץ חיים",
            title="פרק א",
            description="תיאור",
            is_heb=True,
        )
        self.assertTrue(is_predominantly_hebrew(retried_res["summary"]))
        self.assertIn("שמירת הלשון", retried_res["summary"])

        # Falls back to Hebrew deterministic summary if both attempts are English
        mock_post.side_effect = [eng_resp, eng_resp]
        eng_fallback = summarize_with_ollama(
            transcript="[00:00:01] שיעור חפץ חיים",
            title="פרק א",
            description="תיאור",
            is_heb=True,
        )
        self.assertTrue(is_predominantly_hebrew(eng_fallback["summary"]))

        # Connection failure gracefully falls back instead of crashing
        mock_post.side_effect = requests.ConnectionError("Ollama not running")
        fallback_res = summarize_with_ollama(
            transcript="[00:00:01] שיעור חפץ חיים",
            title="פרק א",
            description="תיאור",
            is_heb=True,
        )
        self.assertIn("\n\n", fallback_res["summary"])
        self.assertGreater(len(fallback_res["keywords"]), 0)

    def test_is_predominantly_hebrew(self):
        self.assertTrue(is_predominantly_hebrew("בפרק זה אנו לומדים הלכות שמירת הלשון מתוך הספר חפץ חיים."))
        self.assertFalse(is_predominantly_hebrew("This episode delves into the critical concept of speech."))
        self.assertFalse(is_predominantly_hebrew(""))

    @patch("main.download_audio_file")
    def test_process_rss_feed_end_to_end(self, mock_download):
        mock_download.return_value = 1048576

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = os.path.join(tmpdir, "public", "data")
            feed_url = f"file://{os.path.abspath(self.sample_feed_path)}"

            result = process_rss_feed(
                feed_url=feed_url,
                max_episodes=2,
                force_reprocess=False,
                output_dir=data_dir,
                mock_ai=True,
            )

            self.assertEqual(result["status"], "success")
            self.assertEqual(result["total_feed_entries"], 2)
            self.assertEqual(len(result["episodes_processed"]), 2)
            self.assertEqual(result["episodes_skipped"], 0)

            index_path = os.path.join(data_dir, "episodes-index.json")
            self.assertTrue(os.path.exists(index_path))
            with open(index_path, "r", encoding="utf-8") as f:
                index_items = json.load(f)
            self.assertEqual(len(index_items), 2)
            self.assertNotIn("transcript", index_items[0])

            # Second run should deduplicate and skip both episodes
            second_result = process_rss_feed(
                feed_url=feed_url,
                max_episodes=2,
                force_reprocess=False,
                output_dir=data_dir,
                mock_ai=True,
            )
            self.assertEqual(len(second_result["episodes_processed"]), 0)
            self.assertEqual(second_result["episodes_skipped"], 2)

    def test_decode_audio_compat(self):
        import av
        import numpy as np

        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = os.path.join(tmpdir, "tone.wav")
            sample_rate = 16000
            num_samples = 8000  # 0.5 seconds
            t = np.linspace(0, 0.5, num_samples, endpoint=False, dtype=np.float32)
            pcm = (0.25 * np.sin(2 * np.pi * 440.0 * t) * 32767).astype(np.int16)

            with av.open(wav_path, mode="w") as container:
                stream = container.add_stream("pcm_s16le", rate=sample_rate)
                stream.layout = "mono"
                frame = av.AudioFrame.from_ndarray(pcm.reshape(1, -1), format="s16", layout="mono")
                frame.sample_rate = sample_rate
                for packet in stream.encode(frame):
                    container.mux(packet)
                for packet in stream.encode(None):
                    container.mux(packet)

            waveform = decode_audio_compat(wav_path, sampling_rate=16000)
            self.assertEqual(waveform.dtype, np.float32)
            self.assertEqual(waveform.ndim, 1)
            self.assertGreater(waveform.shape[0], 7000)
            self.assertLessEqual(float(np.max(np.abs(waveform))), 1.0)

    def test_configure_logging_writes_utf8_file(self):
        import logging

        test_logger = logging.getLogger("podcast_ingestion")
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "nested", "test_ingestion.log")
            try:
                resolved = configure_logging(log_path)
                self.assertEqual(resolved, os.path.abspath(log_path))
                test_logger.info("בדיקת לוג עברית - episode ingested")
                for handler in logging.getLogger().handlers:
                    handler.flush()

                self.assertTrue(os.path.exists(log_path))
                with open(log_path, "r", encoding="utf-8") as f:
                    contents = f.read()
                self.assertIn("בדיקת לוג עברית - episode ingested", contents)
            finally:
                configure_logging(DEFAULT_LOG_FILE)

    @patch("main.download_audio_file")
    def test_max_episodes_skips_existing_and_processes_next_batch(self, mock_download):
        mock_download.return_value = 1048576

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = os.path.join(tmpdir, "public", "data")
            feed_url = f"file://{os.path.abspath(self.sample_feed_path)}"

            batch1 = process_rss_feed(
                feed_url=feed_url,
                max_episodes=1,
                force_reprocess=False,
                output_dir=data_dir,
                mock_ai=True,
            )
            self.assertEqual(len(batch1["episodes_processed"]), 1)
            self.assertEqual(batch1["episodes_skipped"], 0)

            batch2 = process_rss_feed(
                feed_url=feed_url,
                max_episodes=1,
                force_reprocess=False,
                output_dir=data_dir,
                mock_ai=True,
            )
            self.assertEqual(len(batch2["episodes_processed"]), 1)
            self.assertEqual(batch2["episodes_skipped"], 1)
            self.assertNotEqual(
                batch1["episodes_processed"][0]["guid"],
                batch2["episodes_processed"][0]["guid"],
            )

            batch3 = process_rss_feed(
                feed_url=feed_url,
                max_episodes=1,
                force_reprocess=False,
                output_dir=data_dir,
                mock_ai=True,
            )
            self.assertEqual(len(batch3["episodes_processed"]), 0)
            self.assertEqual(batch3["episodes_skipped"], 2)


if __name__ == "__main__":
    unittest.main()
