#!/usr/bin/env python3
"""
Convert MusicBrainz JSON dumps into RAG-ready text chunks.

Actual file structure after extraction:
  data/raw/recording/recording   (JSONL, one JSON per line)
  data/raw/artist/artist         (JSONL, one JSON per line)

Outputs:
  data/corpus.jsonl              (full corpus for Python benchmarks)
  data/music_corpus.jsonl        (5000-entry subset for Android assets)
"""

import json
import os
import random
from pathlib import Path
from typing import Iterator

RAW_DIR = Path(__file__).parent / "raw"
OUTPUT_DIR = Path(__file__).parent
CHUNK_SIZE = 400       # max characters per chunk
ANDROID_MAX_ENTRIES = 5000

random.seed(42)


def iter_entity_file(entity: str):
    """
    MusicBrainz dump: after extraction, each entity is a file at
    raw/<entity>/<entity>  (one JSON object per line, no extension).
    """
    # Try common locations
    candidates = [
        RAW_DIR / entity / entity,               # raw/recording/recording
        RAW_DIR / entity / f"{entity}.jsonl",    # raw/recording/recording.jsonl
        RAW_DIR / f"{entity}.jsonl",             # raw/recording.jsonl
    ]

    path = next((p for p in candidates if p.exists()), None)
    if path is None:
        print(f"  [WARN] No file found for '{entity}'. Tried: {[str(c) for c in candidates]}")
        return

    print(f"  Reading from: {path}")
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                if lineno <= 5:
                    print(f"  [WARN] Parse error at line {lineno}: {e}")
                continue


def recording_to_text(rec: dict) -> "str | None":
    title = rec.get("title", "").strip()
    if not title:
        return None

    parts = [f"Recording: {title}"]

    # Duration
    length_ms = rec.get("length")
    if length_ms:
        secs = int(length_ms) // 1000
        parts.append(f"Duration: {secs // 60}:{secs % 60:02d}")

    # Artists
    credits = rec.get("artist-credit") or []
    artist_names = []
    for credit in credits:
        if isinstance(credit, dict) and credit.get("artist"):
            name = credit["artist"].get("name", "")
            if name:
                artist_names.append(name)
    if artist_names:
        parts.append(f"By: {', '.join(artist_names)}")

    # Release date
    first_release = rec.get("first-release-date", "")
    if first_release:
        parts.append(f"First released: {first_release}")

    # Genres from recording-level
    genres = [g.get("name", "") for g in (rec.get("genres") or []) if g.get("count", 0) >= 1]
    # Also from artist
    for credit in credits:
        if isinstance(credit, dict) and credit.get("artist"):
            for g in credit["artist"].get("genres") or []:
                name = g.get("name", "")
                if name and name not in genres:
                    genres.append(name)
    if genres:
        parts.append(f"Genres: {', '.join(genres[:6])}")

    # Disambiguation
    dis = rec.get("disambiguation", "")
    if dis:
        parts.append(f"Note: {dis}")

    return ". ".join(parts) + "."


def artist_to_text(rec: dict) -> "str | None":
    name = (rec.get("name") or rec.get("sort-name", "")).strip()
    if not name:
        return None

    parts = [f"Artist: {name}"]

    if rec.get("type"):
        parts.append(f"Type: {rec['type']}")

    area = rec.get("area") or {}
    if area.get("name"):
        parts.append(f"Origin: {area['name']}")

    life = rec.get("life-span") or {}
    if life.get("begin"):
        parts.append(f"Active since: {life['begin']}")
    if life.get("end"):
        parts.append(f"Active until: {life['end']}")

    genres = [g.get("name", "") for g in (rec.get("genres") or []) if g.get("count", 0) >= 1]
    if genres:
        parts.append(f"Genres: {', '.join(genres[:8])}")

    tags = [t.get("name", "") for t in (rec.get("tags") or []) if t.get("count", 0) > 0]
    extra = [t for t in tags if t not in genres]
    if extra:
        parts.append(f"Tags: {', '.join(extra[:5])}")

    aliases = [a.get("name", "") for a in (rec.get("aliases") or [])[:3] if a.get("name")]
    if aliases:
        parts.append(f"Also known as: {', '.join(aliases)}")

    return ". ".join(parts) + "."


CONVERTERS = {
    "recording": recording_to_text,
    "artist": artist_to_text,
}


def process_entity(entity: str, max_items=None) -> list[dict]:
    if entity not in CONVERTERS:
        print(f"  [SKIP] Unknown entity: {entity}")
        return []

    converter = CONVERTERS[entity]
    docs = []
    count = 0

    for rec in iter_entity_file(entity):
        mbid = rec.get("id", f"{entity}_{count}")
        text = converter(rec)
        if not text:
            count += 1
            continue

        # Split long texts into chunks
        if len(text) > CHUNK_SIZE:
            for i, start in enumerate(range(0, len(text), CHUNK_SIZE - 50)):
                chunk = text[start:start + CHUNK_SIZE]
                docs.append({
                    "id": f"{entity}_{mbid}_c{i}",
                    "entity": entity,
                    "text": chunk,
                })
        else:
            docs.append({
                "id": f"{entity}_{mbid}",
                "entity": entity,
                "text": text,
            })

        count += 1
        if max_items and count >= max_items:
            break

        if count % 50000 == 0:
            print(f"  {count:,} records processed...")

    print(f"  {entity}: {count:,} records → {len(docs):,} chunks")
    return docs


def main():
    print("=== MusicBrainz RAG Corpus Builder ===\n")

    all_docs = []

    # Process recording first (always available), then artist if present
    for entity in ["recording", "artist"]:
        entity_path_1 = RAW_DIR / entity / entity
        entity_path_2 = RAW_DIR / entity / f"{entity}.jsonl"
        if not entity_path_1.exists() and not entity_path_2.exists():
            print(f"Skipping '{entity}' (not downloaded yet)\n")
            continue

        print(f"Processing '{entity}'...")
        docs = process_entity(entity)
        all_docs.extend(docs)
        print()

    if not all_docs:
        print("No data found! Run: bash data/download_musicbrainz.sh first")
        return

    random.shuffle(all_docs)

    # Full corpus
    full_path = OUTPUT_DIR / "corpus.jsonl"
    with open(full_path, "w", encoding="utf-8") as f:
        for doc in all_docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")
    print(f"Full corpus: {len(all_docs):,} chunks → {full_path}")

    # Android subset (5000 entries)
    android_docs = all_docs[:ANDROID_MAX_ENTRIES]
    android_path = OUTPUT_DIR / "music_corpus.jsonl"
    with open(android_path, "w", encoding="utf-8") as f:
        for doc in android_docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")
    print(f"Android subset: {len(android_docs):,} chunks → {android_path}")

    print("\nDone!")
    print(f"  Python benchmarks: use corpus.jsonl")
    print(f"  Android: copy music_corpus.jsonl to android/app/src/main/assets/")


if __name__ == "__main__":
    main()
