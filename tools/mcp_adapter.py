"""
MCP 客户端适配器
封装 MCP 工具调用，提供统一的接口
"""

import json
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path

# 在导入其他模块之前加载配置
try:
    from config.settings_loader import load_and_setup_settings
    load_and_setup_settings()
except Exception as e:
    print(f"警告: 无法从 setting.json 加载配置: {e}")

from config.logging_config import get_logger
from tools.music_tools import Song
from utils.performance_monitor import timed

try:
    from llms.siliconflow_llm import SiliconFlowLLM  # type: ignore
    _silicon_import_error = ""
except Exception as _silicon_err:  # noqa: BLE001
    SiliconFlowLLM = None  # type: ignore[assignment]
    _silicon_import_error = str(_silicon_err)

logger = get_logger(__name__)


@dataclass
class PlaylistInfo:
    """播放列表信息"""
    id: str
    name: str
    url: str
    description: str
    track_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "description": self.description,
            "track_count": self.track_count
        }


@dataclass
class Artist:
    """艺术家信息"""
    name: str
    id: Optional[str] = None
    genres: Optional[List[str]] = None
    popularity: Optional[int] = None
    external_url: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "id": self.id,
            "genres": self.genres or [],
            "popularity": self.popularity,
            "external_url": self.external_url
        }


class MCPClientAdapter:
    """MCP 客户端适配器 - 直接调用 MCP 服务器函数"""
    
    def __init__(self):
        """初始化适配器"""
        self._spotify_client = None
        self._mcp_server = None
        self._spotify_initialized = False
        self._spotify_init_failed = False
        logger.info("MCPClientAdapter 初始化")
    
    def _get_spotify_client(self):
        """获取 Spotify 客户端（延迟初始化）- 直接使用 Spotipy"""
        if self._spotify_init_failed:
            return None

        if self._spotify_client is None and not self._spotify_initialized:
            try:
                import spotipy
                from spotipy.oauth2 import SpotifyClientCredentials

                client_id = os.getenv("SPOTIFY_CLIENT_ID", "")
                client_secret = os.getenv("SPOTIFY_CLIENT_SECRET", "")

                if not client_id or not client_secret:
                    logger.warning("Spotify 凭证未配置 (SPOTIFY_CLIENT_ID/SPOTIFY_CLIENT_SECRET)")
                    self._spotify_init_failed = True
                    self._spotify_initialized = True
                    return None

                client_credentials_manager = SpotifyClientCredentials(
                    client_id=client_id, client_secret=client_secret
                )
                self._spotify_client = spotipy.Spotify(
                    client_credentials_manager=client_credentials_manager
                )
                self._spotify_initialized = True
                logger.info("Spotify 客户端初始化成功 (Spotipy)")
            except Exception as e:
                self._spotify_init_failed = True
                self._spotify_initialized = True
                logger.error(f"初始化 Spotify 客户端失败: {str(e)}")
                return None
        return self._spotify_client
    
    def _get_mcp_server(self):
        """获取 MCP 服务器模块（延迟初始化）"""
        # MCP 需要 Python 3.10+，在 Python 3.9 下禁用
        logger.warning("MCP 服务器需要 Python 3.10+，当前版本不支持，将直接使用 Spotipy")
        return None
    
    def _spotify_track_to_song(self, track: Dict[str, Any]) -> Song:
        """将 Spotify track 数据转换为内部 Song 格式"""
        artists = track.get("artists", [])
        artist_names = [a.get("name", "") if isinstance(a, dict) else str(a) for a in artists]
        artist_str = ", ".join(artist_names) if artist_names else "未知"
        
        # 尝试从专辑获取年份
        album = track.get("album", {})
        release_date = album.get("release_date", "")
        year = None
        if release_date:
            try:
                year = int(release_date.split("-")[0])
            except:
                pass
        
        # 尝试从艺术家获取流派（需要额外 API 调用，这里先留空）
        genre = None
        
        return Song(
            title=track.get("name", "未知"),
            artist=artist_str,
            album=album.get("name") if isinstance(album, dict) else None,
            genre=genre,
            year=year,
            duration=track.get("duration_ms", 0) // 1000 if track.get("duration_ms") else None,
            popularity=track.get("popularity", 0),
            preview_url=track.get("preview_url"),
            spotify_id=track.get("id")
        )
    
    @timed("spotify_search")
    async def search_tracks(self, query: str, limit: int = 10) -> List[Song]:
        """
        搜索歌曲

        Args:
            query: 搜索关键词
            limit: 返回结果数量

        Returns:
            歌曲列表
        """
        try:
            logger.info(f"搜索歌曲: query='{query}', limit={limit}")
            
            sp = self._get_spotify_client()
            results = sp.search(q=query, type="track", limit=limit)
            tracks = results["tracks"]["items"]
            
            songs = [self._spotify_track_to_song(track) for track in tracks]

            # 去重：基于歌曲名和艺术家
            seen = set()
            unique_songs = []
            for song in songs:
                # 使用歌曲名+艺术家作为唯一键
                key = (song.title.lower().strip(), song.artist.lower().strip())
                if key not in seen:
                    seen.add(key)
                    unique_songs.append(song)

            logger.info(f"搜索到 {len(songs)} 首歌曲，去重后 {len(unique_songs)} 首")

            return unique_songs
            
        except Exception as e:
            error_msg = str(e)
            logger.warning(f"Spotify 搜索失败: {error_msg}，尝试 MusicBrainz")

            # Spotify 失败，尝试 MusicBrainz
            try:
                from tools.musicbrainz_client import get_musicbrainz_client
                mb_client = get_musicbrainz_client()

                mb_recordings = mb_client.search_recordings(query, limit=limit)

                if mb_recordings:
                    songs = []
                    for rec in mb_recordings:
                        song = Song(
                            title=rec.title,
                            artist=rec.artist,
                            album=rec.album,
                            genre=rec.genre[0] if rec.genre else None,
                            year=rec.year,
                            duration=rec.duration,
                            popularity=min(100, (rec.score or 50) + 20),
                            spotify_id=f"mb:{rec.id}"  # 使用 MusicBrainz ID 前缀
                        )
                        songs.append(song)

                    # 去重
                    seen = set()
                    unique_songs = []
                    for song in songs:
                        key = (song.title.lower().strip(), song.artist.lower().strip())
                        if key not in seen:
                            seen.add(key)
                            unique_songs.append(song)

                    logger.info(f"MusicBrainz 搜索到 {len(unique_songs)} 首歌曲")
                    return unique_songs

            except Exception as mb_error:
                logger.error(f"MusicBrainz 搜索也失败: {mb_error}")

            raise  # 都失败，抛出异常
    
    @timed("spotify_recommendations")
    async def get_recommendations(
        self,
        seed_tracks: Optional[List[str]] = None,
        seed_artists: Optional[List[str]] = None,
        seed_genres: Optional[List[str]] = None,
        limit: int = 20
    ) -> List[Song]:
        """
        使用硅基流动API获取音乐推荐

        Args:
            seed_tracks: 种子歌曲 ID 列表（最多5个）
            seed_artists: 种子艺术家 ID 列表（最多5个）
            seed_genres: 种子流派列表（最多5个）
            limit: 推荐数量（1-100）

        Returns:
            推荐歌曲列表
        """
        try:
            logger.info(f"获取推荐: seed_tracks={len(seed_tracks) if seed_tracks else 0}, "
                       f"seed_artists={len(seed_artists) if seed_artists else 0}, "
                       f"seed_genres={len(seed_genres) if seed_genres else 0}, limit={limit}")
            
            sp = self._get_spotify_client()
            
            # 如果 Spotify 客户端不可用，直接返回空列表
            if sp is None:
                return []
            
            # 限制种子数量
            seed_tracks = (seed_tracks or [])[:5]
            seed_artists = (seed_artists or [])[:5]
            seed_genres = (seed_genres or [])[:5]
            
            # 确保至少有一个种子
            if not seed_tracks and not seed_artists and not seed_genres:
                logger.warning("没有提供种子，无法获取推荐")
                return []
            
            # 收集种子信息（歌曲名、艺术家名、流派）
            seed_info = {
                "songs": [],
                "artists": [],
                "genres": seed_genres or []
            }
            
            # 获取种子歌曲信息
            if seed_tracks:
                logger.info(f"获取 {len(seed_tracks)} 首种子歌曲的信息...")
                for track_id in seed_tracks:
                    try:
                        track_info = sp.track(track_id)
                        if track_info and track_info.get("name"):
                            artist_names = [a.get("name", "") for a in track_info.get("artists", [])]
                            seed_info["songs"].append({
                                "name": track_info.get("name"),
                                "artist": ", ".join(artist_names) if artist_names else "Unknown"
                            })
                    except Exception as e:
                        logger.debug(f"获取歌曲 {track_id} 信息失败: {e}")
                        continue
            
            # 获取种子艺术家信息
            if seed_artists:
                logger.info(f"获取 {len(seed_artists)} 个种子艺术家的信息...")
                for artist_id in seed_artists:
                    try:
                        artist_info = sp.artist(artist_id)
                        if artist_info and artist_info.get("name"):
                            seed_info["artists"].append(artist_info.get("name"))
                    except Exception as e:
                        logger.debug(f"获取艺术家 {artist_id} 信息失败: {e}")
                        continue
            
            # 如果只有流派，先搜索该流派的热门歌曲作为种子
            if not seed_info["songs"] and not seed_info["artists"] and seed_genres:
                logger.info(f"只有流派种子，搜索流派 '{seed_genres[0]}' 的热门歌曲作为种子")
                try:
                    # 首先尝试 Spotify
                    search_strategies = [
                        f"genre:{seed_genres[0]}",
                        seed_genres[0],
                        f"tag:{seed_genres[0]}",
                    ]

                    for query in search_strategies:
                        try:
                            search_results = sp.search(q=query, type="track", limit=10)
                            if search_results["tracks"]["items"]:
                                tracks = [
                                    track for track in search_results["tracks"]["items"]
                                    if track.get("popularity", 0) > 0 and track.get("id")
                                ]
                                tracks = sorted(tracks, key=lambda x: x.get("popularity", 0), reverse=True)[:3]

                                for track in tracks:
                                    artist_names = [a.get("name", "") for a in track.get("artists", [])]
                                    seed_info["songs"].append({
                                        "name": track.get("name"),
                                        "artist": ", ".join(artist_names) if artist_names else "Unknown"
                                    })

                                if seed_info["songs"]:
                                    logger.info(f"使用查询 '{query}' 找到 {len(seed_info['songs'])} 首种子歌曲")
                                    break
                        except Exception as e:
                            logger.debug(f"搜索策略 '{query}' 失败: {e}")
                            continue

                    # Spotify 失败，尝试 MusicBrainz
                    if not seed_info["songs"]:
                        logger.info("Spotify 流派搜索失败，尝试 MusicBrainz")
                        from tools.musicbrainz_client import get_musicbrainz_client
                        mb_client = get_musicbrainz_client()

                        mb_recordings = mb_client.search_recordings(
                            query=seed_genres[0],
                            limit=5
                        )

                        # 去重：避免同名但不同艺术家的种子歌曲
                        seen_seed_titles = set()
                        for rec in mb_recordings:
                            title_lower = rec.title.lower().strip()
                            if title_lower not in seen_seed_titles:
                                seen_seed_titles.add(title_lower)
                                seed_info["songs"].append({
                                    "name": rec.title,
                                    "artist": rec.artist
                                })
                            if len(seed_info["songs"]) >= 3:
                                break

                        if seed_info["songs"]:
                            logger.info(f"从 MusicBrainz 找到 {len(seed_info['songs'])} 首种子歌曲(去重后)")

                except Exception as e:
                    logger.warning(f"搜索种子歌曲失败: {e}")
            
            # 如果仍然没有种子信息，无法获取推荐
            if not seed_info["songs"] and not seed_info["artists"] and not seed_info["genres"]:
                logger.error("无法获取种子信息，无法生成推荐")
                return []
            
            # 使用 MusicBrainz/TailyAPI 搜索真实歌曲，而不是用 LLM 生成
            logger.info("Spotify 不可用，使用 MusicBrainz 搜索真实歌曲...")

            recommendations_data = []

            # 1. 如果有种子歌曲，搜索相似风格的歌曲
            if seed_info["songs"]:
                from tools.musicbrainz_client import get_musicbrainz_client
                mb_client = get_musicbrainz_client()

                for seed_song in seed_info["songs"][:2]:  # 取前2首种子
                    try:
                        mb_results = mb_client.search_recordings(
                            query=seed_song["name"],
                            artist=seed_song.get("artist"),
                            limit=3
                        )
                        for rec in mb_results:
                            recommendations_data.append({
                                "song": rec.title,
                                "artist": rec.artist,
                                "source": "musicbrainz_similar"
                            })
                    except Exception as e:
                        logger.debug(f"MusicBrainz 搜索失败: {e}")
                        continue

            # 2. 如果有流派，搜索该流派的歌曲
            if seed_info["genres"] and len(recommendations_data) < limit:
                from tools.musicbrainz_client import get_musicbrainz_client
                mb_client = get_musicbrainz_client()

                for genre in seed_info["genres"][:2]:  # 取前2个流派
                    try:
                        mb_results = mb_client.search_recordings(
                            query=genre,
                            limit=limit - len(recommendations_data)
                        )
                        for rec in mb_results:
                            recommendations_data.append({
                                "song": rec.title,
                                "artist": rec.artist,
                                "source": "musicbrainz_genre"
                            })
                            if len(recommendations_data) >= limit:
                                break
                    except Exception as e:
                        logger.debug(f"MusicBrainz 流派搜索失败: {e}")
                        continue

                    if len(recommendations_data) >= limit:
                        break

            # 去重 - 同时按 (歌曲, 艺术家) 和歌曲名去重
            # 避免推荐同名但不同艺术家的多版本
            seen_full = set()  # (歌曲, 艺术家)
            seen_titles = set()  # 仅歌曲名
            unique_recommendations = []

            for rec in recommendations_data:
                title = rec["song"].lower().strip()
                artist = rec["artist"].lower().strip()
                key_full = (title, artist)

                # 如果 (歌曲, 艺术家) 组合已存在，跳过
                if key_full in seen_full:
                    continue

                # 如果歌曲名已存在（不同艺术家版本），也跳过
                if title in seen_titles:
                    logger.debug(f"跳过同名不同版本: {rec['song']} by {rec['artist']} (已存在其他版本)")
                    continue

                seen_full.add(key_full)
                seen_titles.add(title)
                unique_recommendations.append(rec)

                if len(unique_recommendations) >= limit:
                    break

            recommendations_data = unique_recommendations
            logger.info(f"通过 MusicBrainz 找到 {len(recommendations_data)} 首真实歌曲(去重后)")
            logger.info(f"通过 MusicBrainz 找到 {len(recommendations_data)} 首真实歌曲")
            
            # 使用Spotify搜索API查找推荐的歌曲
            found_songs = []
            def _build_queries(song_name: str, artist_name: Optional[str]) -> List[str]:
                # 尝试多种查询以提高命中率（去除标点、添加引号、不同字段组合）
                import re as _re
                def _normalize(s: str) -> str:
                    return _re.sub(r"[\"'“”‘’·.,，。!?！？()\(\)\[\]【】]", " ", s).strip()
                name_norm = _normalize(song_name)
                artist_norm = _normalize(artist_name) if artist_name else None
                queries = []
                if artist_norm:
                    queries.append(f'track:"{name_norm}" artist:"{artist_norm}"')
                    queries.append(f"{name_norm} {artist_norm}")
                    queries.append(f"track:{name_norm} artist:{artist_norm}")
                queries.append(f'track:"{name_norm}"')
                queries.append(name_norm)
                return queries
            
            for rec in recommendations_data[:limit * 2]:  # 搜索更多以增加找到的概率
                try:
                    song_name = rec.get("song") or rec.get("name") or rec.get("title")
                    artist_name = rec.get("artist") or rec.get("artist_name")
                    
                    if not song_name:
                        continue
                    
                    # 多策略搜索
                    queries = _build_queries(song_name, artist_name)
                    matched = False
                    for q in queries:
                        search_results = sp.search(q=q, type="track", limit=5)
                        tracks = search_results.get("tracks", {}).get("items", [])
                        if tracks:
                            # 按流行度排序取最优
                            tracks = sorted(tracks, key=lambda x: x.get("popularity", 0), reverse=True)
                            for track in tracks:
                                song = self._spotify_track_to_song(track)
                                if song.spotify_id and song.spotify_id not in [s.spotify_id for s in found_songs]:
                                    found_songs.append(song)
                                    matched = True
                                    logger.debug(f"找到推荐歌曲: {song.title} by {song.artist}")
                                    break
                        if matched:
                            break
                    
                    if len(found_songs) >= limit:
                        break
                        
                except Exception as e:
                    logger.debug(f"搜索推荐歌曲失败: {e}")
                    continue
            
            # 如果 Spotify 没有找到歌曲，使用 MusicBrainz 搜索作为回退
            if not found_songs and recommendations_data:
                logger.info("Spotify 搜索无结果，尝试 MusicBrainz 搜索")
                try:
                    from tools.musicbrainz_client import get_musicbrainz_client
                    mb_client = get_musicbrainz_client()

                    for rec in recommendations_data[:limit * 2]:
                        try:
                            song_name = rec.get("song") or rec.get("name") or rec.get("title")
                            artist_name = rec.get("artist") or rec.get("artist_name")

                            if not song_name:
                                continue

                            # 使用 MusicBrainz 搜索
                            mb_recordings = mb_client.search_recordings(
                                query=song_name,
                                artist=artist_name,
                                limit=3
                            )

                            if mb_recordings:
                                mb_rec = mb_recordings[0]  # 取最佳匹配
                                song = Song(
                                    title=mb_rec.title,
                                    artist=mb_rec.artist,
                                    album=mb_rec.album,
                                    genre=mb_rec.genre[0] if mb_rec.genre else None,
                                    year=mb_rec.year,
                                    duration=mb_rec.duration,
                                    popularity=min(100, (mb_rec.score or 50) + 20),
                                    spotify_id=f"mb:{mb_rec.id}"
                                )
                                found_songs.append(song)
                                logger.debug(f"从 MusicBrainz 找到: {song.title} by {song.artist}")

                            if len(found_songs) >= limit:
                                break

                        except Exception as e:
                            logger.debug(f"MusicBrainz 搜索推荐歌曲失败: {e}")
                            continue

                    if found_songs:
                        logger.info(f"从 MusicBrainz 找到 {len(found_songs)} 首推荐歌曲")

                except Exception as mb_error:
                    logger.warning(f"MusicBrainz 搜索失败: {mb_error}")

            # 如果 MusicBrainz 也没有找到，使用 RAG 搜索作为最后回退
            if not found_songs and recommendations_data:
                logger.info("MusicBrainz 搜索无结果，使用 RAG 向量搜索")
                try:
                    from tools.rag_music_search import get_rag_music_search
                    rag_search = get_rag_music_search()

                    # 将 LLM 推荐添加到 RAG 索引
                    rag_search.add_llm_recommendations(recommendations_data)

                    # 构建查询（结合流派和种子信息）
                    query_parts = []
                    if seed_genres:
                        query_parts.extend(seed_genres)
                    if seed_artists:
                        query_parts.extend(seed_artists)
                    query = " ".join(query_parts) if query_parts else "recommended music"

                    # 执行 RAG 搜索
                    rag_results = rag_search.search(query, top_k=limit)

                    if rag_results:
                        for result in rag_results:
                            song = Song(
                                title=result.get("title", "Unknown"),
                                artist=result.get("artist", "Unknown Artist"),
                                album=result.get("album"),
                                genre=result.get("genre") if isinstance(result.get("genre"), str) else None,
                                year=result.get("year"),
                                duration=result.get("duration"),
                                popularity=int(result.get("similarity_score", 0.5) * 100),
                                external_url=result.get("external_url")
                            )
                            found_songs.append(song)

                        logger.info(f"从 RAG 搜索找到 {len(found_songs)} 首推荐歌曲")

                except Exception as rag_error:
                    logger.warning(f"RAG 搜索失败: {rag_error}")

            return found_songs[:limit]

        except Exception as e:
            error_msg = str(e)
            logger.error(f"获取推荐失败: {error_msg}", exc_info=True)
            return []
    
    @timed("spotify_audio_features")
    async def get_audio_features(self, track_ids: List[str]) -> Dict[str, Any]:
        """批量获取 Spotify 音频特征"""
        try:
            sp = self._get_spotify_client()
            if sp is None or not track_ids:
                return {}
            features_list = sp.audio_features(tracks=track_ids[:100])
            features_by_id: Dict[str, Any] = {}
            for feat in features_list or []:
                if feat and feat.get("id"):
                    features_by_id[feat["id"]] = {
                        "danceability": feat.get("danceability"),
                        "energy": feat.get("energy"),
                        "valence": feat.get("valence"),
                        "tempo": feat.get("tempo"),
                        "acousticness": feat.get("acousticness"),
                        "instrumentalness": feat.get("instrumentalness"),
                    }
            return features_by_id
        except Exception as e:
            logger.debug(f"获取音频特征失败: {e}")
            return {}

    async def get_recommendations_by_names(
        self,
        seed_track_names: Optional[List[Dict[str, str]]] = None,
        seed_artist_names: Optional[List[str]] = None,
        seed_genres: Optional[List[str]] = None,
        limit: int = 20
    ) -> List[Song]:
        """
        通过歌曲名和艺术家名获取推荐（自动查找 ID）
        
        Args:
            seed_track_names: 种子歌曲列表 [{"song_name": "...", "artist_name": "..."}]
            seed_artist_names: 种子艺术家名称列表
            seed_genres: 种子流派列表
            limit: 推荐数量
            
        Returns:
            推荐歌曲列表
        """
        try:
            sp = self._get_spotify_client()
            
            # 查找歌曲 ID
            track_ids = []
            if seed_track_names:
                for track_data in seed_track_names[:5]:
                    song_name = track_data.get("song_name", "")
                    artist_name = track_data.get("artist_name", "")
                    
                    query = song_name
                    if artist_name:
                        query += f" artist:{artist_name}"
                    
                    search_results = sp.search(q=query, type="track", limit=1)
                    tracks = search_results["tracks"]["items"]
                    if tracks:
                        track_ids.append(tracks[0]["id"])
            
            # 查找艺术家 ID
            artist_ids = []
            if seed_artist_names:
                for artist_name in seed_artist_names[:5]:
                    search_results = sp.search(q=f"artist:{artist_name}", type="artist", limit=1)
                    artists = search_results["artists"]["items"]
                    if artists:
                        artist_ids.append(artists[0]["id"])
            
            # 使用找到的 ID 获取推荐
            return await self.get_recommendations(
                seed_tracks=track_ids if track_ids else None,
                seed_artists=artist_ids if artist_ids else None,
                seed_genres=seed_genres,
                limit=limit
            )
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"通过名称获取推荐失败: {error_msg}", exc_info=True)
            raise  # 抛出异常，不使用本地数据库
    
    async def get_user_top_tracks(self, limit: int = 20, time_range: str = "medium_term") -> List[Song]:
        """
        获取用户热门歌曲
        
        Args:
            limit: 返回数量（1-50）
            time_range: 时间范围 ("short_term", "medium_term", "long_term")
            
        Returns:
            用户热门歌曲列表
        """
        try:
            logger.info(f"获取用户热门歌曲: limit={limit}, time_range={time_range}")
            
            sp = self._get_spotify_client()
            results = sp.current_user_top_tracks(limit=min(limit, 50), time_range=time_range)
            tracks = results["items"]
            
            songs = [self._spotify_track_to_song(track) for track in tracks]
            logger.info(f"获取到 {len(songs)} 首用户热门歌曲")
            
            return songs
            
        except Exception as e:
            error_msg = str(e)
            # 对于缺少凭证的情况，使用 WARNING 而不是 ERROR
            if "credentials not found" in error_msg.lower() or "spotify credentials" in error_msg.lower():
                logger.warning(f"Spotify 未配置，无法获取用户热门歌曲: {error_msg}。将使用本地数据库。")
            else:
                logger.error(f"获取用户热门歌曲失败: {error_msg}", exc_info=True)
            return []
    
    async def get_user_top_artists(self, limit: int = 20, time_range: str = "medium_term") -> List[Artist]:
        """
        获取用户热门艺术家
        
        Args:
            limit: 返回数量（1-50）
            time_range: 时间范围 ("short_term", "medium_term", "long_term")
            
        Returns:
            用户热门艺术家列表
        """
        try:
            logger.info(f"获取用户热门艺术家: limit={limit}, time_range={time_range}")
            
            sp = self._get_spotify_client()
            results = sp.current_user_top_artists(limit=min(limit, 50), time_range=time_range)
            artists = results["items"]
            
            artist_list = []
            for artist in artists:
                artist_list.append(Artist(
                    name=artist.get("name", "未知"),
                    id=artist.get("id"),
                    genres=artist.get("genres", []),
                    popularity=artist.get("popularity", 0),
                    external_url=artist.get("external_urls", {}).get("spotify") if isinstance(artist.get("external_urls"), dict) else None
                ))
            
            logger.info(f"获取到 {len(artist_list)} 个用户热门艺术家")
            return artist_list
            
        except Exception as e:
            error_msg = str(e)
            # 对于缺少凭证的情况，使用 WARNING 而不是 ERROR
            if "credentials not found" in error_msg.lower() or "spotify credentials" in error_msg.lower():
                logger.warning(f"Spotify 未配置，无法获取用户热门艺术家: {error_msg}。将使用本地数据库。")
            else:
                logger.error(f"获取用户热门艺术家失败: {error_msg}", exc_info=True)
            return []
    
    @timed("spotify_create_playlist")
    async def create_playlist(
        self,
        name: str,
        songs: List[Song],
        description: Optional[str] = None,
        public: bool = False
    ) -> Optional[PlaylistInfo]:
        """
        创建 Spotify 播放列表
        
        Args:
            name: 播放列表名称
            songs: 歌曲列表
            description: 描述
            public: 是否公开
            
        Returns:
            播放列表信息
        """
        try:
            logger.info(f"创建播放列表: name='{name}', songs={len(songs)}, public={public}")
            
            sp = self._get_spotify_client()
            
            # 获取当前用户 ID
            user = sp.current_user()
            user_id = user["id"]
            
            # 创建播放列表
            playlist = sp.user_playlist_create(
                user=user_id,
                name=name,
                public=public,
                description=description or ""
            )
            
            playlist_id = playlist["id"]
            
            # 获取歌曲 URI
            track_uris = []
            for song in songs:
                if song.spotify_id:
                    track_uris.append(f"spotify:track:{song.spotify_id}")
                else:
                    # 如果没有 ID，尝试搜索
                    search_results = sp.search(
                        q=f"track:{song.title} artist:{song.artist}",
                        type="track",
                        limit=1
                    )
                    tracks = search_results["tracks"]["items"]
                    if tracks:
                        track_uris.append(tracks[0]["uri"])
            
            # 添加歌曲到播放列表（分批添加，每批最多100首）
            if track_uris:
                for i in range(0, len(track_uris), 100):
                    batch = track_uris[i:i+100]
                    sp.playlist_add_items(playlist_id, batch)
            
            playlist_info = PlaylistInfo(
                id=playlist_id,
                name=playlist["name"],
                url=playlist["external_urls"]["spotify"],
                description=playlist.get("description", ""),
                track_count=len(track_uris)
            )
            
            logger.info(f"播放列表创建成功: {playlist_info.url}")
            return playlist_info
            
        except Exception as e:
            error_msg = str(e)
            # 对于缺少凭证的情况，使用 WARNING 而不是 ERROR
            if "credentials not found" in error_msg.lower() or "spotify credentials" in error_msg.lower():
                logger.warning(f"Spotify 未配置，无法创建播放列表: {error_msg}。")
            else:
                logger.error(f"创建播放列表失败: {error_msg}", exc_info=True)
            return None
    
    async def analyze_playlist(self, playlist_id: str) -> Dict[str, Any]:
        """
        分析播放列表
        
        Args:
            playlist_id: 播放列表 ID
            
        Returns:
            分析结果
        """
        try:
            logger.info(f"分析播放列表: playlist_id={playlist_id}")
            
            mcp_server = self._get_mcp_server()
            
            # 调用 MCP 服务器的 analyze_playlist 工具
            arguments = {"playlist_id": playlist_id}
            result = await mcp_server.call_tool("analyze_playlist", arguments)
            
            # 解析结果
            if result and len(result) > 0:
                text_content = result[0].text
                analysis = json.loads(text_content)
                return analysis
            else:
                return {}
                
        except Exception as e:
            logger.error(f"分析播放列表失败: {str(e)}", exc_info=True)
            return {}


# 创建全局实例
_mcp_adapter = None

def get_mcp_adapter() -> MCPClientAdapter:
    """获取 MCP 适配器单例"""
    global _mcp_adapter
    if _mcp_adapter is None:
        _mcp_adapter = MCPClientAdapter()
    return _mcp_adapter

