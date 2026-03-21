#!/usr/bin/env python3
"""
快速初始化本地 RAG 数据库
使用简单数据 + 关键词嵌入，无需 LLM 调用，立即可用
"""

import json
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 预设歌曲数据（包含常见的中文歌曲）
PRESET_SONGS = [
    # 周杰伦
    {"title": "晴天", "artist": "周杰伦", "genre": ["流行"], "mood": ["青春", "回忆", "温暖"], "scenes": ["休闲", "开车"], "year": 2003},
    {"title": "七里香", "artist": "周杰伦", "genre": ["流行"], "mood": ["浪漫", "甜蜜"], "scenes": ["约会", "散步"], "year": 2004},
    {"title": "稻香", "artist": "周杰伦", "genre": ["流行", "民谣"], "mood": ["治愈", "温暖", "怀旧"], "scenes": ["休闲", "睡前"], "year": 2008},
    {"title": "夜曲", "artist": "周杰伦", "genre": ["流行", "古典"], "mood": ["忧伤", "浪漫"], "scenes": ["夜晚", "独处"], "year": 2005},
    {"title": "听妈妈的话", "artist": "周杰伦", "genre": ["流行"], "mood": ["温暖", "感人"], "scenes": ["家庭", "休闲"], "year": 2006},

    # 林俊杰
    {"title": "江南", "artist": "林俊杰", "genre": ["流行"], "mood": ["浪漫", "唯美"], "scenes": ["约会", "雨天"], "year": 2004},
    {"title": "小酒窝", "artist": "林俊杰", "genre": ["流行"], "mood": ["甜蜜", "幸福"], "scenes": ["约会", "婚礼"], "year": 2008},
    {"title": "修炼爱情", "artist": "林俊杰", "genre": ["流行"], "mood": ["伤感", "深情"], "scenes": ["独处", "夜晚"], "year": 2013},

    # 陈奕迅
    {"title": "十年", "artist": "陈奕迅", "genre": ["流行"], "mood": ["怀旧", "感慨"], "scenes": ["独处", "夜晚"], "year": 2003},
    {"title": "好久不见", "artist": "陈奕迅", "genre": ["流行"], "mood": ["思念", "忧伤"], "scenes": ["独处", "雨天"], "year": 2007},
    {"title": "浮夸", "artist": "陈奕迅", "genre": ["流行", "摇滚"], "mood": ["激情", "宣泄"], "scenes": ["运动", "派对"], "year": 2005},

    # 毛不易
    {"title": "消愁", "artist": "毛不易", "genre": ["民谣", "流行"], "mood": ["治愈", "感慨"], "scenes": ["独处", "夜晚", "咖啡馆"], "year": 2017},
    {"title": "像我这样的人", "artist": "毛不易", "genre": ["民谣", "流行"], "mood": ["温暖", "励志"], "scenes": ["独处", "工作"], "year": 2017},
    {"title": "平凡的一天", "artist": "毛不易", "genre": ["民谣", "流行"], "mood": ["平静", "治愈"], "scenes": ["休闲", "早晨"], "year": 2018},

    # 邓紫棋
    {"title": "光年之外", "artist": "邓紫棋", "genre": ["流行"], "mood": ["深情", "宏大"], "scenes": ["运动", "开车"], "year": 2016},
    {"title": "喜欢你", "artist": "邓紫棋", "genre": ["流行", "摇滚"], "mood": ["热情", "甜蜜"], "scenes": ["派对", "约会"], "year": 2014},

    # 薛之谦
    {"title": "演员", "artist": "薛之谦", "genre": ["流行"], "mood": ["伤感", "深情"], "scenes": ["独处", "夜晚"], "year": 2015},
    {"title": "丑八怪", "artist": "薛之谦", "genre": ["流行"], "mood": ["自嘲", "洒脱"], "scenes": ["休闲", "独处"], "year": 2013},

    # 民谣
    {"title": "成都", "artist": "赵雷", "genre": ["民谣"], "mood": ["温暖", "怀旧", "治愈"], "scenes": ["咖啡馆", "夜晚", "旅行"], "year": 2016},
    {"title": "南山南", "artist": "马頔", "genre": ["民谣"], "mood": ["忧伤", "诗意"], "scenes": ["独处", "夜晚"], "year": 2014},
    {"title": "理想", "artist": "赵雷", "genre": ["民谣"], "mood": ["励志", "感慨"], "scenes": ["工作", "独处"], "year": 2016},

    # 纯音乐/轻音乐
    {"title": "River Flows in You", "artist": "Yiruma", "genre": ["纯音乐", "钢琴"], "mood": ["平静", "治愈"], "scenes": ["学习", "工作", "睡前"], "year": 2001},
    {"title": "Kiss the Rain", "artist": "Yiruma", "genre": ["纯音乐", "钢琴"], "mood": ["忧伤", "唯美"], "scenes": ["雨天", "独处", "学习"], "year": 2003},
    {"title": "天空之城", "artist": "久石让", "genre": ["纯音乐", "交响"], "mood": ["梦幻", "纯净"], "scenes": ["学习", "睡前", "冥想"], "year": 1986},

    # 国际流行
    {"title": "Shape of You", "artist": "Ed Sheeran", "genre": ["流行"], "mood": ["活力", "节奏"], "scenes": ["运动", "派对"], "year": 2017},
    {"title": "Perfect", "artist": "Ed Sheeran", "genre": ["流行", "抒情"], "mood": ["浪漫", "甜蜜"], "scenes": ["约会", "婚礼"], "year": 2017},
    {"title": "Blinding Lights", "artist": "The Weeknd", "genre": ["流行", "电子"], "mood": ["动感", "复古"], "scenes": ["运动", "开车", "派对"], "year": 2019},
    {"title": "Levitating", "artist": "Dua Lipa", "genre": ["流行", "迪斯科"], "mood": ["活力", "快乐"], "scenes": ["运动", "派对", "开车"], "year": 2020},

    # 摇滚/独立
    {"title": "海阔天空", "artist": "Beyond", "genre": ["摇滚"], "mood": ["励志", "激情"], "scenes": ["运动", "KTV"], "year": 1993},
    {"title": "光辉岁月", "artist": "Beyond", "genre": ["摇滚"], "mood": ["励志", "怀旧"], "scenes": ["运动", "独处"], "year": 1990},
]


def generate_simple_embedding(song: dict) -> list:
    """生成简单的关键词嵌入向量"""
    # 定义关键词维度 (比原来更丰富的维度)
    keywords = [
        # 流派 (0-9)
        "流行", "摇滚", "民谣", "电子", "古典", "说唱", "爵士", "纯音乐", "国风", "独立",
        # 情绪 (10-19)
        "开心", "放松", "专注", "忧伤", "浪漫", "治愈", "激情", "平静", "怀旧", "温暖",
        # 场景 (20-29)
        "运动", "学习", "工作", "睡前", "开车", "约会", "派对", "独处", "雨天", "咖啡馆",
        # 风格 (30-39)
        "节奏感", "抒情", "轻快", "沉重", "复古", "现代", "柔和", "强烈", "梦幻", "诗意",
    ]

    # 构建描述文本
    text_parts = [
        song.get("title", ""),
        song.get("artist", ""),
        " ".join(song.get("genre", [])),
        " ".join(song.get("mood", [])),
        " ".join(song.get("scenes", [])),
    ]
    text = " ".join(filter(None, text_parts))
    text_lower = text.lower()

    import numpy as np
    import re

    # 创建向量
    vector = np.zeros(len(keywords))
    for i, keyword in enumerate(keywords):
        # 计算关键词匹配度
        if keyword in text_lower:
            vector[i] = 1.0
        # 部分匹配
        elif len(keyword) > 2 and keyword[:2] in text_lower:
            vector[i] = 0.5

    # 扩展到 768 维 (SiliconFlow 标准维度)
    target_dim = 768
    extended = np.zeros(target_dim)
    extended[:len(keywords)] = vector

    # 使用正弦/余弦扩展剩余维度，保持向量结构
    for i in range(len(keywords), target_dim):
        idx = (i - len(keywords)) % len(keywords)
        extended[i] = vector[idx] * np.sin(i * 0.1) * 0.3

    # 归一化
    norm = np.linalg.norm(extended)
    if norm > 0:
        extended = extended / norm

    return extended.tolist()


def init_database():
    """初始化数据库"""
    print("=" * 50)
    print("快速初始化本地 RAG 音乐数据库")
    print("=" * 50)

    # 确保目录存在
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    db_path = data_dir / "music_database.json"

    # 为每首歌生成嵌入
    songs_with_embedding = []
    for song in PRESET_SONGS:
        song_data = song.copy()
        song_data["id"] = f"{song['artist']}_{song['title']}"
        song_data["source"] = "preset"
        song_data["embedding"] = generate_simple_embedding(song)
        songs_with_embedding.append(song_data)

    # 构建数据库结构
    db_data = {
        "version": "1.0-quick",
        "total_songs": len(songs_with_embedding),
        "songs": songs_with_embedding,
        "metadata": {
            "sources": ["preset"],
            "embedding_model": "simple_keyword_v2",
            "embedding_dim": 768,
        }
    }

    # 保存
    with open(db_path, 'w', encoding='utf-8') as f:
        json.dump(db_data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 数据库初始化完成!")
    print(f"   路径: {db_path.absolute()}")
    print(f"   歌曲数: {len(songs_with_embedding)}")
    print(f"   向量维度: 768")
    print(f"\n包含艺术家: 周杰伦, 林俊杰, 陈奕迅, 毛不易, 邓紫棋, 薛之谦, Beyond, 赵雷 等")
    print(f"\n可以使用 RAG 搜索了!")

    return len(songs_with_embedding)


if __name__ == "__main__":
    init_database()
