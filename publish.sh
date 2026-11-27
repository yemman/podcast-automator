#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAX_EPISODES="${MAX_EPISODES:-5}"
SKIP_DEPLOY=false
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --max-episodes)
      MAX_EPISODES="$2"
      shift 2
      ;;
    --skip-deploy)
      SKIP_DEPLOY=true
      shift
      ;;
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

echo "==> [1/3] Running local RSS ingestion (max_episodes=${MAX_EPISODES})..."
cd "${ROOT_DIR}/backend"
python3 ingest_anchor_feed.py --max-episodes "${MAX_EPISODES}" "${EXTRA_ARGS[@]}"

echo "==> [2/3] Building Angular SSG static bundle..."
cd "${ROOT_DIR}/frontend"
npm run build

if [[ "${SKIP_DEPLOY}" == "true" ]]; then
  echo "==> [3/3] Skipping Firebase deploy (--skip-deploy set)."
  echo "Static site ready at: ${ROOT_DIR}/frontend/dist/frontend/browser"
  exit 0
fi

echo "==> [3/3] Deploying static site to Firebase Hosting..."
cd "${ROOT_DIR}"
firebase deploy --only hosting
