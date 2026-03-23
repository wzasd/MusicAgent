'use client';

import { useEffect, useState } from 'react';
import MainLayout from '@/components/Layout/MainLayout';
import { theme } from '@/styles/theme';

interface SongBrief {
  title: string;
  artist: string;
}

interface LogEntry {
  action: string;
  original_query: string;
  intent: string;
  parameters: Record<string, string>;
  result_count: number;
  elapsed_ms: number;
  status: string;
  source?: string;
  songs?: SongBrief[];
  error?: string;
  timestamp: string;
}

export default function LogsPage() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchLogs = async () => {
    try {
      const response = await fetch('/api/logs?limit=20');
      if (!response.ok) {
        throw new Error('Failed to fetch logs');
      }
      const data = await response.json();
      if (data.success) {
        setLogs(data.logs);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch logs');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
    const interval = setInterval(fetchLogs, 5000);
    return () => clearInterval(interval);
  }, []);

  const getIntentLabel = (intent: string) => {
    const labels: Record<string, string> = {
      search: '歌曲搜索',
      search_by_lyrics: '歌词搜索',
      search_by_theme: '影视主题曲',
      search_by_topic: '话题搜索',
      recommend_by_mood: '心情推荐',
      recommend_by_activity: '活动推荐',
      recommend_by_genre: '流派推荐',
      recommend_by_artist: '艺术家推荐',
      general_chat: '闲聊',
    };
    return labels[intent] || intent;
  };

  const getSourceType = (source?: string): 'RAG' | 'API' | 'LLM' | 'Web' | 'Theme' | 'Topic' | 'Artist' | 'Local' | 'Mixed' | '未找到' => {
    if (!source) return 'RAG';
    if (source.includes('not_found')) return '未找到';
    if (source === 'llm_lyrics') return 'LLM';
    if (source === 'web_search') return 'Web';
    if (source === 'theme_web_search') return 'Theme';
    if (source === 'topic_web_search') return 'Topic';
    if (source === 'artist_web_search') return 'Artist';
    if (source === 'local_db') return 'Local';
    if (source === 'mixed') return 'Mixed';
    if (source === 'spotify' || source === 'mcp') return 'API';
    return 'RAG';
  };

  const getSourceLabel = (source?: string) => {
    const detail: Record<string, string> = {
      rag_chroma: 'RAG · 语义搜索',
      artist_metadata: 'RAG · 艺术家',
      artist_not_found: '未找到',
      artist_web_search: 'Web · 艺术家',
      local_db: '本地 · 艺术家',
      chroma_db: 'Chroma · 艺术家',
      mixed: '混合 · 艺术家',
      genre_search: 'RAG · 流派',
      genre_not_found: '未找到',
      lyrics_db: 'RAG · 歌词库',
      llm_lyrics: 'LLM · 歌词识别',
      web_search: 'Web · 歌词搜索',
      theme_web_search: 'Web · 影视主题曲',
      topic_web_search: 'Web · 话题搜索',
      activity_recommendation: 'RAG · 活动场景',
      mood_recommendation: 'RAG · 心情',
    };
    return detail[source || ''] || source || '-';
  };

  const getSourceColor = (source?: string) => {
    const type = getSourceType(source);
    switch (type) {
      case 'RAG':    return { bg: '#dbeafe', text: '#1e40af' };
      case 'API':    return { bg: '#d1fae5', text: '#065f46' };
      case 'LLM':    return { bg: '#ede9fe', text: '#5b21b6' };
      case 'Web':    return { bg: '#fce7f3', text: '#9d174d' };
      case 'Theme':  return { bg: '#ffedd5', text: '#9a3412' };
      case 'Topic':  return { bg: '#f0fdf4', text: '#166534' };
      case 'Artist': return { bg: '#e0f2fe', text: '#0369a1' };
      case 'Local':  return { bg: '#fef9c3', text: '#854d0e' };
      case 'Mixed':  return { bg: '#f3e8ff', text: '#7c3aed' };
      case '未找到': return { bg: '#fef3c7', text: '#92400e' };
      default:       return { bg: '#f3f4f6', text: '#374151' };
    }
  };

  const getSearchContent = (log: LogEntry) => {
    const p = log.parameters || {};
    // 影视主题曲搜索显示 country + title
    if (p.title) {
      return p.country ? `${p.country}《${p.title}》` : `《${p.title}》`;
    }
    return p.artist || p.genre || p.lyrics || p.mood || p.activity || p.topic || p.query || '-';
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'success':
        return { bg: '#dcfce7', text: '#166534' };
      case 'error':
        return { bg: '#fee2e2', text: '#991b1b' };
      default:
        return { bg: '#f3f4f6', text: '#374151' };
    }
  };

  return (
    <MainLayout>
      <div style={{ padding: '0.5rem' }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '1.5rem',
          }}
        >
          <h1
            style={{
              fontSize: '1.5rem',
              fontWeight: 600,
              color: theme.colors.text.primary,
              margin: 0,
            }}
          >
            搜索日志
          </h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <button
              onClick={fetchLogs}
              style={{
                padding: '0.5rem 1rem',
                backgroundColor: theme.colors.primary.main,
                color: '#fff',
                border: 'none',
                borderRadius: theme.borderRadius.md,
                cursor: 'pointer',
                fontSize: '0.875rem',
                fontWeight: 500,
              }}
            >
              刷新
            </button>
            <span style={{ fontSize: '0.875rem', color: theme.colors.text.muted }}>
              共 {logs.length} 条记录
            </span>
          </div>
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '3rem', color: theme.colors.text.muted }}>
            加载中...
          </div>
        ) : error ? (
          <div
            style={{
              padding: '1rem',
              backgroundColor: '#fee2e2',
              color: '#991b1b',
              borderRadius: theme.borderRadius.md,
            }}
          >
            错误: {error}
          </div>
        ) : logs.length === 0 ? (
          <div
            style={{
              textAlign: 'center',
              padding: '3rem',
              color: theme.colors.text.muted,
              backgroundColor: '#fff',
              borderRadius: theme.borderRadius.md,
            }}
          >
            暂无日志记录
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {logs.map((log, index) => {
              const statusColor = getStatusColor(log.status);
              return (
                <div
                  key={index}
                  style={{
                    backgroundColor: '#fff',
                    borderRadius: theme.borderRadius.md,
                    padding: '1rem',
                    border: '1px solid rgba(31, 35, 40, 0.08)',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'flex-start',
                      marginBottom: '0.75rem',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span
                        style={{
                          fontSize: '1rem',
                          fontWeight: 500,
                          color: theme.colors.text.primary,
                        }}
                      >
                        {log.original_query}
                      </span>
                      <span
                        style={{
                          padding: '0.25rem 0.5rem',
                          backgroundColor: statusColor.bg,
                          color: statusColor.text,
                          borderRadius: theme.borderRadius.full,
                          fontSize: '0.75rem',
                          fontWeight: 500,
                        }}
                      >
                        {log.status === 'success' ? '成功' : '失败'}
                      </span>
                    </div>
                    <span style={{ fontSize: '0.75rem', color: theme.colors.text.muted }}>
                      {new Date(log.timestamp).toLocaleString('zh-CN')}
                    </span>
                  </div>

                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
                      gap: '0.5rem',
                      fontSize: '0.875rem',
                    }}
                  >
                    <div>
                      <span style={{ color: theme.colors.text.muted }}>意图: </span>
                      <span style={{ fontWeight: 500 }}>{getIntentLabel(log.intent)}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                      <span style={{ color: theme.colors.text.muted }}>搜索源: </span>
                      <span
                        style={{
                          padding: '0.1rem 0.4rem',
                          backgroundColor: getSourceColor(log.source).bg,
                          color: getSourceColor(log.source).text,
                          borderRadius: theme.borderRadius.full,
                          fontSize: '0.75rem',
                          fontWeight: 500,
                        }}
                      >
                        {getSourceLabel(log.source)}
                      </span>
                    </div>
                    <div>
                      <span style={{ color: theme.colors.text.muted }}>搜索内容: </span>
                      <span style={{ fontWeight: 500, color: theme.colors.primary.main }}>
                        {getSearchContent(log)}
                      </span>
                    </div>
                    <div>
                      <span style={{ color: theme.colors.text.muted }}>结果数: </span>
                      <span style={{ fontWeight: 500 }}>{log.result_count}</span>
                    </div>
                    <div>
                      <span style={{ color: theme.colors.text.muted }}>耗时: </span>
                      <span style={{ fontWeight: 500 }}>{log.elapsed_ms}ms</span>
                    </div>
                  </div>

                  {log.parameters && Object.keys(log.parameters).length > 0 && (
                    <div
                      style={{
                        marginTop: '0.75rem',
                        paddingTop: '0.75rem',
                        borderTop: '1px solid rgba(31, 35, 40, 0.06)',
                      }}
                    >
                      <span style={{ fontSize: '0.875rem', color: theme.colors.text.muted }}>
                        提取参数:
                      </span>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.5rem' }}>
                        {Object.entries(log.parameters).map(([key, value]) => (
                          <span
                            key={key}
                            style={{
                              padding: '0.25rem 0.5rem',
                              backgroundColor: '#f3f4f6',
                              borderRadius: theme.borderRadius.full,
                              fontSize: '0.75rem',
                            }}
                          >
                            {key}: {value}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {log.songs && log.songs.length > 0 && (
                    <div
                      style={{
                        marginTop: '0.75rem',
                        paddingTop: '0.75rem',
                        borderTop: '1px solid rgba(31, 35, 40, 0.06)',
                      }}
                    >
                      <span style={{ fontSize: '0.75rem', color: theme.colors.text.muted }}>
                        搜索结果 ({log.songs.length} 首)
                      </span>
                      <div style={{ marginTop: '0.5rem', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                        {log.songs.map((song, i) => (
                          <div
                            key={i}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '0.5rem',
                              fontSize: '0.8rem',
                              padding: '0.2rem 0.5rem',
                              backgroundColor: '#f9fafb',
                              borderRadius: '4px',
                            }}
                          >
                            <span style={{ color: theme.colors.text.muted, minWidth: '1.2rem' }}>{i + 1}.</span>
                            <span style={{ fontWeight: 500, color: theme.colors.text.primary }}>{song.title}</span>
                            <span style={{ color: theme.colors.text.muted }}>—</span>
                            <span style={{ color: theme.colors.text.secondary }}>{song.artist}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {log.error && (
                    <div
                      style={{
                        marginTop: '0.75rem',
                        padding: '0.5rem',
                        backgroundColor: '#fee2e2',
                        borderRadius: theme.borderRadius.md,
                      }}
                    >
                      <span style={{ fontSize: '0.75rem', color: '#991b1b' }}>错误: {log.error}</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </MainLayout>
  );
}
