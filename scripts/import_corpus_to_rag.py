#!/usr/bin/env python3
"""
将 data/corpus.jsonl 导入 ChromaDB RAG 系统

用法:
    python3 scripts/import_corpus_to_rag.py                    # 导入 music_corpus.jsonl (5k)
    python3 scripts/import_corpus_to_rag.py --all              # 导入 corpus.jsonl (147k)
    python3 scripts/import_corpus_to_rag.py --limit 10000      # 导入前 10000 条
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.logging_config import get_logger

logger = get_logger(__name__)

CHECKPOINT_FILE = project_root / "data" / ".import_checkpoint.json"
CHROMA_DIR = str(project_root / "data" / "chroma_db")
COLLECTION_NAME = "music_songs"


def parse_recording_text(text: str) -> Dict:
    """
    解析 corpus.jsonl 中的文本格式：
    "Recording: Title. Duration: X:XX. By: Artist. Genres: genre1, genre2."
    """
    result = {"title": "", "artist": "", "genres": [], "duration_str": ""}

    # Title
    title_match = re.match(r"Recording:\s+(.+?)(?:\.|$)", text)
    if title_match:
        result["title"] = title_match.group(1).strip().rstrip(".")

    # Duration
    dur_match = re.search(r"Duration:\s+([\d:]+)", text)
    if dur_match:
        result["duration_str"] = dur_match.group(1)
        parts = dur_match.group(1).split(":")
        try:
            if len(parts) == 2:
                result["duration"] = int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3:
                result["duration"] = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        except ValueError:
            pass

    # Artist
    artist_match = re.search(r"By:\s+(.+?)(?:\.|Genres:|$)", text)
    if artist_match:
        result["artist"] = artist_match.group(1).strip().rstrip(".")

    # Genres
    genre_match = re.search(r"Genres:\s+(.+?)(?:\.|Note:|$)", text)
    if genre_match:
        genres_raw = genre_match.group(1).strip().rstrip(".")
        result["genres"] = [g.strip() for g in genres_raw.split(",") if g.strip()]

    return result


def build_embedding_text(entry: Dict, parsed: Dict) -> str:
    """构建用于生成 embedding 的文本"""
    parts = []
    if parsed["title"]:
        parts.append(parsed["title"])
    if parsed["artist"]:
        parts.append(parsed["artist"])
    if parsed["genres"]:
        parts.append(" ".join(parsed["genres"]))
    # 原始 text 作为补充
    parts.append(entry.get("text", ""))
    return " ".join(filter(None, parts))


def load_checkpoint() -> set:
    """加载已处理的 ID 集合"""
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE) as f:
            data = json.load(f)
        return set(data.get("processed_ids", []))
    return set()


def save_checkpoint(processed_ids: set):
    """保存断点"""
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump({"processed_ids": list(processed_ids)}, f)


def load_jsonl(path: str, limit: Optional[int] = None) -> List[Dict]:
    entries = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            if limit and i >= limit:
                break
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


def import_to_chroma(entries: List[Dict], openai_client, embed_model: str, batch_size: int = 32, rate_limit_sleep: float = 0.0):
    """批量生成 embedding 并存入 ChromaDB"""
    import chromadb
    from chromadb.config import Settings

    client = chromadb.PersistentClient(
        path=CHROMA_DIR,
        settings=Settings(anonymized_telemetry=False),
    )
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    # 已存在的 ID
    existing_ids = set()
    try:
        existing = collection.get(include=[])
        existing_ids = set(existing["ids"])
        logger.info(f"ChromaDB 已有 {len(existing_ids)} 条记录")
    except Exception:
        pass

    # 过滤掉已存在的
    new_entries = [e for e in entries if e["id"] not in existing_ids]
    logger.info(f"本次需要导入: {len(new_entries)} 条（跳过已存在 {len(entries) - len(new_entries)} 条）")

    if not new_entries:
        logger.info("无新数据需要导入")
        return 0

    total = len(new_entries)
    imported = 0
    failed = 0

    for batch_start in range(0, total, batch_size):
        batch = new_entries[batch_start: batch_start + batch_size]

        ids = []
        texts_for_embed = []
        documents = []
        metadatas = []

        for entry in batch:
            parsed = parse_recording_text(entry.get("text", ""))
            if not parsed["title"] or not parsed["artist"]:
                failed += 1
                continue

            embed_text = build_embedding_text(entry, parsed)
            ids.append(entry["id"])
            texts_for_embed.append(embed_text)
            documents.append(entry.get("text", ""))
            metadatas.append({
                "title": parsed["title"],
                "artist": parsed["artist"],
                "genre": json.dumps(parsed["genres"], ensure_ascii=False),
                "mood": "[]",
                "scenes": "[]",
                "description": "",
                "year": 0,
                "duration": parsed.get("duration", 0),
                "source": "musicbrainz",
            })

        if not ids:
            continue

        # 生成 embeddings（批量）
        try:
            resp = openai_client.embeddings.create(model=embed_model, input=texts_for_embed)
            embeddings = [item.embedding for item in resp.data]
        except Exception as e:
            logger.error(f"Batch {batch_start}-{batch_start+batch_size} embedding 失败: {e}")
            failed += len(ids)
            time.sleep(2)
            continue

        # 存入 ChromaDB
        try:
            collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )
            imported += len(ids)
        except Exception as e:
            logger.error(f"ChromaDB 写入失败: {e}")
            failed += len(ids)
            continue

        progress = batch_start + len(batch)
        logger.info(f"进度: {progress}/{total} ({100*progress//total}%) | 已导入: {imported} | 失败: {failed}")

        if rate_limit_sleep > 0:
            time.sleep(rate_limit_sleep)

    logger.info(f"\n完成! 导入: {imported}, 失败: {failed}, ChromaDB 总量: {collection.count()}")
    return imported


def main():
    parser = argparse.ArgumentParser(description="导入 corpus.jsonl 到 ChromaDB RAG")
    parser.add_argument("--all", action="store_true", help="使用完整 corpus.jsonl (147k)")
    parser.add_argument("--limit", type=int, default=None, help="限制导入条数")
    parser.add_argument("--local", action="store_true", help="使用本地 Ollama embedding（默认 bge-m3）")
    parser.add_argument("--local-model", default="bge-m3:latest", help="Ollama 模型名，默认 bge-m3:latest")
    args = parser.parse_args()

    if args.all:
        corpus_path = project_root / "data" / "corpus.jsonl"
        desc = "corpus.jsonl (完整)"
    else:
        corpus_path = project_root / "data" / "music_corpus.jsonl"
        desc = "music_corpus.jsonl (5k)"

    if not corpus_path.exists():
        print(f"文件不存在: {corpus_path}")
        sys.exit(1)

    limit = args.limit
    logger.info(f"数据源: {desc}, 限制: {limit or '无'}")

    entries = load_jsonl(str(corpus_path), limit=limit)
    logger.info(f"读取 {len(entries)} 条记录")

    logger.info("初始化 embedding 模型...")
    from openai import OpenAI
    if args.local:
        base_url = "http://localhost:11434/v1"
        api_key = "ollama"
        embed_model = args.local_model
        logger.info(f"使用本地 Ollama: {embed_model}")
    else:
        from config.settings_loader import load_settings_from_json
        settings = load_settings_from_json()
        api_key = os.getenv("SILICONFLOW_API_KEY") or settings.get("SILICONFLOW_API_KEY")
        base_url = settings.get("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
        embed_model = settings.get("SILICONFLOW_EMBED_MODEL", "BAAI/bge-m3")
        logger.info(f"使用 SiliconFlow API: {embed_model}")
    client = OpenAI(api_key=api_key, base_url=base_url)

    sleep = 0.0 if args.local else 0.3
    count = import_to_chroma(entries, client, embed_model, rate_limit_sleep=sleep)
    print(f"\n✅ 导入完成，新增 {count} 条到 ChromaDB")


if __name__ == "__main__":
    main()
