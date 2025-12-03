"""
测试音乐旅程服务
"""

import asyncio
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 加载配置
try:
    from config.settings_loader import load_and_setup_settings
    load_and_setup_settings()
except Exception as e:
    print(f"警告: 无法加载配置: {e}")

from services.journey_service import MusicJourneyService, MoodPoint


async def test_story_journey():
    """测试基于故事的旅程生成"""
    print("=" * 60)
    print("测试1: 基于故事的旅程生成")
    print("=" * 60)
    
    service = MusicJourneyService()
    
    story = "早晨起床→通勤路上→工作中→下班放松→夜晚休息"
    result = await service.generate_journey(
        story=story,
        duration=60
    )
    
    if result.get("success"):
        print(f"\n✅ 旅程生成成功！")
        print(f"总片段数: {len(result.get('segments', []))}")
        print(f"总时长: {result.get('total_duration', 0):.1f}分钟")
        print(f"总歌曲数: {result.get('total_songs', 0)}")
        print(f"\n情绪变化: {' → '.join(result.get('mood_progression', []))}")
        
        print("\n片段详情:")
        for i, segment in enumerate(result.get('segments', [])):
            print(f"\n片段 {i+1}:")
            print(f"  情绪: {segment.get('mood')}")
            print(f"  描述: {segment.get('description')}")
            print(f"  时长: {segment.get('duration'):.1f}分钟")
            print(f"  歌曲数: {segment.get('total_songs', 0)}")
            if segment.get('songs'):
                print(f"  示例歌曲: {segment['songs'][0].get('title', 'N/A')} - {segment['songs'][0].get('artist', 'N/A')}")
    else:
        print(f"\n❌ 旅程生成失败: {result.get('error')}")


async def test_mood_curve_journey():
    """测试基于情绪曲线的旅程生成"""
    print("\n" + "=" * 60)
    print("测试2: 基于情绪曲线的旅程生成")
    print("=" * 60)
    
    service = MusicJourneyService()
    
    # 定义情绪曲线
    mood_points = [
        MoodPoint(time=0.0, mood="放松", intensity=0.6),
        MoodPoint(time=0.3, mood="专注", intensity=0.8),
        MoodPoint(time=0.6, mood="活力", intensity=0.9),
        MoodPoint(time=0.8, mood="平静", intensity=0.5),
        MoodPoint(time=1.0, mood="放松", intensity=0.4),
    ]
    
    result = await service.generate_journey(
        mood_transitions=mood_points,
        duration=90
    )
    
    if result.get("success"):
        print(f"\n✅ 旅程生成成功！")
        print(f"总片段数: {len(result.get('segments', []))}")
        print(f"总时长: {result.get('total_duration', 0):.1f}分钟")
        print(f"总歌曲数: {result.get('total_songs', 0)}")
    else:
        print(f"\n❌ 旅程生成失败: {result.get('error')}")


async def test_similarity():
    """测试歌曲相似度计算"""
    print("\n" + "=" * 60)
    print("测试3: 歌曲相似度计算")
    print("=" * 60)
    
    from tools.music_tools import Song
    
    service = MusicJourneyService()
    
    song1 = Song(
        title="歌曲1",
        artist="艺术家A",
        genre="pop",
        year=2020,
        popularity=80
    )
    
    song2 = Song(
        title="歌曲2",
        artist="艺术家A",
        genre="pop",
        year=2021,
        popularity=75
    )
    
    song3 = Song(
        title="歌曲3",
        artist="艺术家B",
        genre="rock",
        year=1990,
        popularity=60
    )
    
    sim12 = service.calculate_song_similarity(song1, song2)
    sim13 = service.calculate_song_similarity(song1, song3)
    
    print(f"\n歌曲1 vs 歌曲2 (相同艺术家和流派): {sim12:.2f}")
    print(f"歌曲1 vs 歌曲3 (不同艺术家和流派): {sim13:.2f}")


async def main():
    """主测试函数"""
    print("🎵 音乐旅程服务测试")
    print("=" * 60)
    
    # 检查环境变量
    if not os.getenv("SILICONFLOW_API_KEY"):
        print("⚠️  警告: 未设置 SILICONFLOW_API_KEY，某些功能可能无法使用")
    
    try:
        await test_story_journey()
        await test_mood_curve_journey()
        await test_similarity()
        
        print("\n" + "=" * 60)
        print("✅ 所有测试完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

