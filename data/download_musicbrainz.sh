#!/usr/bin/env bash
# Download MusicBrainz JSON Dumps
# Source: https://data.metabrainz.org/pub/musicbrainz/data/json-dumps/
# License: Core data CC0, Supplementary CC BY-NC-SA 3.0

set -e

# Auto-detect latest dump version
BASE_URL="https://data.metabrainz.org/pub/musicbrainz/data/json-dumps"
DEST_DIR="$(dirname "$0")/raw"

mkdir -p "$DEST_DIR"

echo "=== MusicBrainz JSON Dumps Downloader ==="

# Find latest version
LATEST=$(curl -s "${BASE_URL}/" | grep -o 'href="[0-9][^"]*"' | tr -d 'href="' | sort | tail -1 | tr -d '/')
if [ -z "$LATEST" ]; then
    echo "[ERROR] Could not detect latest dump version"
    exit 1
fi
echo "Latest dump: $LATEST"
DUMP_URL="${BASE_URL}/${LATEST}"
echo "Destination: $DEST_DIR"
echo ""

# Choose which entities to download
# recording: ~31MB   ← always included (fast test)
# artist:    ~1.56GB ← included by default
# release:   ~20GB   ← SKIP by default (too large)
ENTITIES=("recording" "artist")

# Uncomment to also download release (20GB):
# ENTITIES=("recording" "artist" "release")

for entity in "${ENTITIES[@]}"; do
    FILENAME="${entity}.tar.xz"
    URL="${DUMP_URL}/${FILENAME}"
    DEST="${DEST_DIR}/${FILENAME}"

    if [ -f "$DEST" ]; then
        echo "[SKIP] $FILENAME already downloaded"
    else
        echo "[DOWNLOAD] $FILENAME from $URL ..."
        curl -L --progress-bar -o "$DEST" "$URL"
        echo "[OK] Downloaded $FILENAME"
    fi
done

echo ""
echo "=== Extracting archives ==="

for entity in "${ENTITIES[@]}"; do
    ARCHIVE="${DEST_DIR}/${entity}.tar.xz"
    EXTRACT_DIR="${DEST_DIR}/${entity}"

    if [ -d "$EXTRACT_DIR" ] && [ "$(ls -A "$EXTRACT_DIR" 2>/dev/null)" ]; then
        echo "[SKIP] $entity already extracted"
        continue
    fi

    if [ ! -f "$ARCHIVE" ]; then
        echo "[WARN] $ARCHIVE not found, skipping"
        continue
    fi

    echo "[EXTRACT] $entity ..."
    mkdir -p "$EXTRACT_DIR"
    tar -xJf "$ARCHIVE" -C "$EXTRACT_DIR" --strip-components=1
    echo "[OK] Extracted $entity"
done

echo ""
echo "=== Done! ==="
echo "Files in: $DEST_DIR"
echo "Next step: python data/prepare_rag_corpus.py"
