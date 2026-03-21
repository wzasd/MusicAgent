#!/usr/bin/env python3
"""
构建本地 RAG 音乐数据库
从多个来源抓取数据并构建可持久化的向量索引
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.logging_config import get_logger
from llms.siliconflow_llm import get_chat_model, get_embeddings
from tools.music_tools import get_music_search_tool

logger = get_logger(__name__)

# 种子查询列表 - 用于构建初始数据库
SEED_QUERIES = [
    # 流派
    "流行音乐", "摇滚", "民谣", "电子音乐", "爵士", "古典", "说唱", "R&B",
    "国风", "古风", "轻音乐", "独立音乐", "金属", "朋克", "蓝调",
    # 情绪
    "开心", "放松", "专注", "悲伤", "浪漫", "治愈", "振奋", "平静",
    "怀旧", "温暖", "孤独", "希望", "激情", "慵懒", "清新",
    # 场景
    "运动时听", "学习背景音乐", "工作专注", "睡前放松", "开车提神",
    "派对音乐", "咖啡馆氛围", "雨天听的歌", "周末愉快", "清晨清醒",
    # 艺术家（示例）
    "周杰伦", "林俊杰", "陈奕迅", "薛之谦", "毛不易", "邓紫棋",
    "Taylor Swift", "Ed Sheeran", "The Weeknd", "Bruno Mars",
]


class RAGDatabaseBuilder:
    """RAG 数据库构建器"""

    def __init__(self, output_path: str = "data/music_database.json"):
        self.output_path = Path(output_path)
        self.songs_cache: Dict[str, Dict] = {}  # 去重缓存
        self.embedding_model = get_embeddings()  # 使用 SiliconFlow Embedding

    async def fetch_from_tailyapi(self, query: str, limit: int = 20) -> List[Dict]:
        """从 TailyAPI 获取歌曲"""
        try:
            search_tool = get_music_search_tool()
            songs = await search_tool.taily_search(query, limit=limit)

            results = []
            for song in songs:
                song_dict = {
                    "id": song.id if hasattr(song, 'id') else f"{song.title}_{song.artist}",
                    "title": song.title,
                    "artist": song.artist,
                    "album": getattr(song, 'album', None),
                    "genre": getattr(song, 'genre', []),
                    "year": getattr(song, 'year', None),
                    "duration": getattr(song, 'duration', None),
                    "source": "tailyapi",
                    "query_context": query,
                }
                results.append(song_dict)

            logger.info(f"TailyAPI '{query}': {len(results)} 首")
            return results

        except Exception as e:
            logger.error(f"TailyAPI 搜索失败 '{query}': {e}")
            return []

    async def enrich_with_llm(self, song: Dict) -> Dict:
        """使用 LLM 为歌曲生成描述、情绪、场景标签"""
        try:
            llm = get_chat_model()

            prompt = f"""分析这首歌曲，生成结构化标签：

歌曲: {song['title']}
艺术家: {song['artist']}
专辑: {song.get('album', '未知')}
流派: {song.get('genre', '未知')}

请生成:
1. 情绪标签 (mood): 如 开心、放松、悲伤、浪漫、治愈、振奋 等
2. 场景标签 (scenes): 如 运动、学习、工作、睡前、开车、派对 等
3. 简短描述 (description): 歌曲风格和特点描述，50字以内

以JSON格式返回:
{{
    "mood": ["标签1", "标签2"],
    "scenes": ["场景1", "场景2"],
    "description": "描述文字"
}}"""

            response = await llm.ainvoke(prompt)

            # 解析 JSON
            import re
            json_match = re.search(r'\{[^}]+\}', response.content, re.DOTALL)
            if json_match:
                enriched = json.loads(json_match.group())
                song.update(enriched)

        except Exception as e:
            logger.debug(f"LLM 增强失败: {e}")

        return song

    async def generate_embedding(self, song: Dict) -> List[float]:
        """为歌曲生成向量嵌入"""
        try:
            # 构建歌曲描述文本
            text_parts = [
                song.get('title', ''),
                song.get('artist', ''),
                ' '.join(song.get('genre', [])) if isinstance(song.get('genre'), list) else str(song.get('genre', '')),
                ' '.join(song.get('mood', [])) if isinstance(song.get('mood'), list) else str(song.get('mood', '')),
                song.get('description', ''),
            ]
            text = ' '.join(filter(None, text_parts))

            if not text.strip():
                return []

            # 调用 SiliconFlow Embedding API
            embedding = await self.embedding_model.aembed_query(text)
            return embedding

        except Exception as e:
            logger.error(f"生成嵌入失败: {e}")
            return []

    def deduplicate(self, songs: List[Dict]) -> List[Dict]:
        """歌曲去重"""
        unique_songs = []

        for song in songs:
            key = f"{song.get('title', '').lower().strip()}_{song.get('artist', '').lower().strip()}"

            if key not in self.songs_cache:
                self.songs_cache[key] = song
                unique_songs.append(song)

        logger.info(f"去重: {len(songs)} -> {len(unique_songs)} 首")
        return unique_songs

    async def build_database(self, max_songs: int = 1000):
        """构建完整数据库"""
        logger.info("=" * 50)
        logger.info("开始构建 RAG 音乐数据库")
        logger.info("=" * 50)

        all_songs = []

        # 1. 从多个种子查询获取数据
        logger.info("\n[阶段 1] 抓取歌曲数据...")
        for query in SEED_QUERIES:
            songs = await self.fetch_from_tailyapi(query, limit=15)
            all_songs.extend(songs)

            # 简单去重
            all_songs = self.deduplicate(all_songs)

            if len(all_songs) >= max_songs:
                logger.info(f"达到目标数量 {max_songs}")
                break

            await asyncio.sleep(0.5)  # 避免请求过快

        all_songs = all_songs[:max_songs]
        logger.info(f"\n抓取完成: {len(all_songs)} 首唯一歌曲")

        # 2. LLM 增强标签
        logger.info("\n[阶段 2] LLM 增强歌曲标签...")
        enriched_songs = []
        for i, song in enumerate(all_songs):
            enriched = await self.enrich_with_llm(song)
            enriched_songs.append(enriched)

            if (i + 1) % 10 == 0:
                logger.info(f"已处理 {i + 1}/{len(all_songs)}")

            await asyncio.sleep(0.3)  # 控制 LLM 调用频率

        # 3. 生成向量嵌入
        logger.info("\n[阶段 3] 生成向量嵌入...")
        songs_with_embeddings = []
        for i, song in enumerate(enriched_songs):
            embedding = await self.generate_embedding(song)
            if embedding:
                song['embedding'] = embedding
                songs_with_embeddings.append(song)

            if (i + 1) % 10 == 0:
                logger.info(f"已嵌入 {i + 1}/{len(enriched_songs)}")

        # 4. 保存数据库
        logger.info("\n[阶段 4] 保存数据库...")
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        db_data = {
            "version": "1.0",
            "total_songs": len(songs_with_embeddings),
            "songs": songs_with_embeddings,
            "metadata": {
                "sources": ["tailyapi"],
                "embedding_model": "siliconflow",
                "embedding_dim": len(songs_with_embeddings[0]['embedding']) if songs_with_embeddings else 0,
            }
        }

        with open(self.output_path, 'w', encoding='utf-8') as f:
            json.dump(db_data, f, ensure_ascii=False, indent=2)

        logger.info(f"\n✅ 数据库构建完成!")
        logger.info(f"   保存路径: {self.output_path.absolute()}")
        logger.info(f"   歌曲数量: {len(songs_with_embeddings)}")
        logger.info(f"   向量维度: {db_data['metadata']['embedding_dim']}")

        return len(songs_with_embeddings)


async def main():
    """主函数"""
    builder = RAGDatabaseBuilder()
    count = await builder.build_database(max_songs=500)
    print(f"\n成功构建数据库，包含 {count} 首歌曲")


if __name__ == "__main__":
    asyncio.run(main())
