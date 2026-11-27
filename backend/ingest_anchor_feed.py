#!/usr/bin/env python3
"""
Dedicated Local Ingestion Script for the Anchor.fm Podcast Feed:
'מי האיש החפץ חיים' (https://anchor.fm/s/e7fc5d7c/podcast/rss)

Transcribes locally with faster-whisper (ivrit-ai), summarizes with Ollama,
and writes static JSON + sitemap files into frontend/public/ for Angular SSG.
"""

import sys
import os
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import (
    process_rss_feed,
    resummarize_existing_episodes,
    configure_logging,
    DEFAULT_RSS_FEED_URL,
    DEFAULT_WHISPER_MODEL,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OLLAMA_URL,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_SITE_URL,
    DEFAULT_LOG_FILE,
    DEFAULT_CPU_THREADS,
)


def main():
    parser = argparse.ArgumentParser(
        description="Local AI Ingestion for 'מי האיש החפץ חיים' Anchor.fm Podcast Feed"
    )
    parser.add_argument("--feed-url", type=str, default=DEFAULT_RSS_FEED_URL, help="RSS Feed URL")
    parser.add_argument("--max-episodes", type=int, default=5, help="Number of latest episodes to ingest (0 = all)")
    parser.add_argument("--force", action="store_true", help="Force re-ingestion of already processed GUIDs")
    parser.add_argument("--mock", action="store_true", help="Run with mock local AI for fast dry-run testing")
    parser.add_argument("--skip-llm", action="store_true", help="Skip Ollama summarization and use fallback description summary")
    parser.add_argument("--resummarize-english", action="store_true", help="Re-summarize saved episodes whose summaries are currently in English")
    parser.add_argument("--whisper-model", type=str, default=os.environ.get("WHISPER_MODEL", DEFAULT_WHISPER_MODEL), help="faster-whisper model name")
    parser.add_argument("--whisper-device", type=str, default=os.environ.get("WHISPER_DEVICE", "cpu"), help="Whisper device (cpu/cuda)")
    parser.add_argument("--compute-type", type=str, default=os.environ.get("WHISPER_COMPUTE_TYPE", "int8"), help="Whisper compute type (int8/float16/float32)")
    parser.add_argument("--cpu-threads", type=int, default=DEFAULT_CPU_THREADS, help="CPU threads for faster-whisper and Ollama")
    parser.add_argument("--ollama-model", type=str, default=os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL), help="Ollama model tag")
    parser.add_argument("--ollama-url", type=str, default=os.environ.get("OLLAMA_URL", DEFAULT_OLLAMA_URL), help="Ollama server URL")
    parser.add_argument("--output-dir", type=str, default=os.environ.get("PODCAST_DATA_DIR", DEFAULT_OUTPUT_DIR), help="Target static data directory")
    parser.add_argument("--site-url", type=str, default=os.environ.get("SITE_URL", DEFAULT_SITE_URL), help="Public site URL for sitemap.xml")
    parser.add_argument("--log-file", type=str, default=os.environ.get("PODCAST_LOG_FILE", DEFAULT_LOG_FILE), help="Path to rotating ingestion log file")
    args = parser.parse_args()

    resolved_log_file = configure_logging(args.log_file)

    if args.resummarize_english:
        print("================================================================")
        print(" Re-summarizing Non-Hebrew Episode Summaries")
        print(f" Ollama     : {args.ollama_model} ({args.ollama_url})")
        print(f" Output Dir : {args.output_dir}")
        print(f" Log File   : {resolved_log_file}")
        print("================================================================")

        result = resummarize_existing_episodes(
            output_dir=args.output_dir,
            ollama_url=args.ollama_url,
            ollama_model=args.ollama_model,
            only_non_hebrew=True,
            site_url=args.site_url,
            cpu_threads=args.cpu_threads,
        )
        print("\n--- RE-SUMMARIZATION RESULT ---")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    mode_label = (
        "DRY RUN (Mock Local AI)"
        if args.mock
        else f"100% LOCAL AI ({args.whisper_model} + {'skip-llm' if args.skip_llm else args.ollama_model})"
    )

    print("================================================================")
    print(" Starting Local RSS Ingestion Pipeline")
    print(f" Feed URL   : {args.feed_url}")
    print(f" Mode       : {mode_label}")
    print(f" Output Dir : {args.output_dir}")
    print(f" Log File   : {resolved_log_file}")
    print(f" CPU Threads: {args.cpu_threads}")
    print(f" Max Eps    : {args.max_episodes}")
    print("================================================================")

    result = process_rss_feed(
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

    print("\n--- INGESTION RESULT ---")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if result.get("status") == "success":
        print(
            f"\nSuccessfully finished! Processed: {len(result.get('episodes_processed', []))}, "
            f"Skipped: {result.get('episodes_skipped')}, Failed: {result.get('episodes_failed')}"
        )
    else:
        print(f"\nIngestion encountered issues: {result.get('message')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
