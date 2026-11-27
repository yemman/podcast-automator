#!/usr/bin/env bash
set -euo pipefail

NVM_BIN="$(ls -d "${HOME}"/.nvm/versions/node/*/bin 2>/dev/null | sort -V | tail -n 1 || true)"
export PATH="${NVM_BIN:+${NVM_BIN}:}${HOME}/.local/bin:/usr/local/bin:/usr/bin:/bin"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BATCH_SIZE="${BATCH_SIZE:-5}"
CPU_THREADS="${CPU_THREADS:-4}"
AUTO_DEPLOY="${AUTO_DEPLOY:-false}"
LOCK_FILE="/tmp/podcast_ingest.lock"
INDEX_FILE="${ROOT_DIR}/frontend/public/data/episodes-index.json"
PENDING_FILE="${ROOT_DIR}/.pending_deploy"

export OMP_NUM_THREADS="${CPU_THREADS}"
export OPENBLAS_NUM_THREADS="${CPU_THREADS}"

exec 9>"${LOCK_FILE}"
if ! /usr/bin/flock -n 9; then
  echo "$(date -Iseconds) [INFO] Previous ingestion batch still running; skipping this trigger."
  exit 0
fi

CUSTOM_OUTPUT=false
for arg in "$@"; do
  if [[ "$arg" == "--output-dir" ]]; then
    CUSTOM_OUTPUT=true
  fi
done

BEFORE_MTIME=0
if [[ -f "${INDEX_FILE}" ]]; then
  BEFORE_MTIME="$(stat -c %Y "${INDEX_FILE}")"
fi

echo "================================================================"
echo "$(date -Iseconds) Starting scheduled batch (max_episodes=${BATCH_SIZE}, cpu_threads=${CPU_THREADS}, auto_deploy=${AUTO_DEPLOY})"
cd "${ROOT_DIR}/backend"
nice -n 15 python3 ingest_anchor_feed.py --max-episodes "${BATCH_SIZE}" --cpu-threads "${CPU_THREADS}" "$@"

if [[ "${CUSTOM_OUTPUT}" == "true" ]]; then
  echo "$(date -Iseconds) Custom --output-dir specified; skipping frontend build & deploy."
  exit 0
fi

AFTER_MTIME=0
if [[ -f "${INDEX_FILE}" ]]; then
  AFTER_MTIME="$(stat -c %Y "${INDEX_FILE}")"
fi

if [[ "${AFTER_MTIME}" -gt "${BEFORE_MTIME}" ]]; then
  echo "$(date -Iseconds) New episodes detected; rebuilding Angular SSG (nice -n 15)..."
  cd "${ROOT_DIR}/frontend"
  nice -n 15 npm run build
  touch "${PENDING_FILE}"
else
  echo "$(date -Iseconds) No new episodes ingested; skipping Angular SSG rebuild."
fi

if [[ "${AUTO_DEPLOY}" == "true" ]]; then
  if [[ -f "${PENDING_FILE}" ]]; then
    echo "$(date -Iseconds) AUTO_DEPLOY=true and pending changes found; deploying to Firebase Hosting..."
    cd "${ROOT_DIR}"
    firebase deploy --only hosting && rm -f "${PENDING_FILE}"
  else
    echo "$(date -Iseconds) AUTO_DEPLOY=true, but no pending build to deploy."
  fi
fi
