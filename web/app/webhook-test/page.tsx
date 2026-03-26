'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import MainLayout from '@/components/Layout/MainLayout';
import { theme } from '@/styles/theme';

// Types
interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface StreamInfo {
  streamType: 'start' | 'partial' | 'final';
  streamContent: string;
}

interface Action {
  type: string;
  [key: string]: any;
}

interface WebhookResponse {
  errorCode: number;
  errorMessage: string;
  reply: {
    streamInfo?: StreamInfo;
    action?: Action[];
  };
}

interface HistoryItem {
  id: string;
  timestamp: string;
  sessionId: string;
  messages: Message[];
  response: WebhookResponse | null;
  status: 'pending' | 'success' | 'error';
}

interface TestCase {
  id: string;
  label: string;
  description: string;
  messages: Message[];
  category: 'single' | 'multi' | 'special';
}

// Test cases definition
const testCases: TestCase[] = [
  {
    id: 'direct-play',
    label: '直接播放',
    description: 'Hotel California',
    category: 'single',
    messages: [{ role: 'user', content: 'I want to listen to Hotel California' }],
  },
  {
    id: 'artist-songs',
    label: '艺术家歌曲',
    description: 'Taylor Swift 热门歌曲',
    category: 'single',
    messages: [{ role: 'user', content: 'What are some popular songs by Taylor Swift' }],
  },
  {
    id: 'multi-round-1',
    label: '多轮对话-1',
    description: '推荐跑步歌曲',
    category: 'multi',
    messages: [{ role: 'user', content: 'Recommend some songs for running' }],
  },
  {
    id: 'multi-round-2-first',
    label: '多轮对话-2a',
    description: '选择第一首',
    category: 'multi',
    messages: [
      { role: 'user', content: 'Recommend some songs for running' },
      { role: 'assistant', content: 'Here are some running songs: 1. Eye of the Tiger, 2. Stronger, 3. Can\'t Hold Us' },
      { role: 'user', content: 'the first one' },
    ],
  },
  {
    id: 'multi-round-2-second',
    label: '多轮对话-2b',
    description: '选择第二首',
    category: 'multi',
    messages: [
      { role: 'user', content: 'Recommend some songs for running' },
      { role: 'assistant', content: 'Here are some running songs: 1. Eye of the Tiger, 2. Stronger, 3. Can\'t Hold Us' },
      { role: 'user', content: 'the second one' },
    ],
  },
  {
    id: 'multi-round-2-play',
    label: '多轮对话-2c',
    description: '播放它',
    category: 'multi',
    messages: [
      { role: 'user', content: 'Recommend some songs for running' },
      { role: 'assistant', content: 'Here are some running songs: 1. Eye of the Tiger, 2. Stronger, 3. Can\'t Hold Us' },
      { role: 'user', content: 'play it' },
    ],
  },
  {
    id: 'multi-round-2-last',
    label: '多轮对话-2d',
    description: '选择最后一首',
    category: 'multi',
    messages: [
      { role: 'user', content: 'Recommend some songs for running' },
      { role: 'assistant', content: 'Here are some running songs: 1. Eye of the Tiger, 2. Stronger, 3. Can\'t Hold Us' },
      { role: 'user', content: 'the last one' },
    ],
  },
  {
    id: 'multi-round-2-third',
    label: '多轮对话-2e',
    description: '选择第三首',
    category: 'multi',
    messages: [
      { role: 'user', content: 'Recommend some songs for running' },
      { role: 'assistant', content: 'Here are some running songs: 1. Eye of the Tiger, 2. Stronger, 3. Can\'t Hold Us, 4. Lose Yourself' },
      { role: 'user', content: 'the third one' },
    ],
  },
  {
    id: 'multi-round-cancel-en',
    label: '取消-英文',
    description: 'I don\'t want to listen anymore',
    category: 'multi',
    messages: [
      { role: 'user', content: 'Recommend some songs for running' },
      { role: 'assistant', content: 'Here are some running songs: 1. Eye of the Tiger, 2. Stronger' },
      { role: 'user', content: "I don't want to listen anymore" },
    ],
  },
  {
    id: 'multi-round-cancel-cn',
    label: '取消-中文',
    description: '算了',
    category: 'multi',
    messages: [
      { role: 'user', content: '推荐一些跑步歌曲' },
      { role: 'assistant', content: '这里有一些跑步歌曲：1.  Eye of the Tiger, 2. Stronger' },
      { role: 'user', content: '算了' },
    ],
  },
  {
    id: 'lyrics-search',
    label: '歌词搜索',
    description: 'Every night in my dreams',
    category: 'special',
    messages: [{ role: 'user', content: "I want to hear the song with lyric 'Every night in my dreams'" }],
  },
  {
    id: 'mood-relaxing',
    label: '心情推荐',
    description: '放松音乐',
    category: 'special',
    messages: [{ role: 'user', content: 'Play some relaxing music' }],
  },
  {
    id: 'activity-study',
    label: '活动推荐',
    description: '学习音乐',
    category: 'special',
    messages: [{ role: 'user', content: 'Music for studying' }],
  },
];

// Utility functions
const generateUUID = () => {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
};

const formatTimestamp = (date: Date) => {
  return date.toLocaleTimeString('zh-CN', { hour12: false });
};

// Components
const Card = ({ children, title, style }: { children: React.ReactNode; title?: string; style?: React.CSSProperties }) => (
  <div
    style={{
      backgroundColor: theme.colors.background.card,
      borderRadius: theme.borderRadius.lg,
      border: '1px solid rgba(31, 35, 40, 0.08)',
      overflow: 'hidden',
      ...style,
    }}
  >
    {title && (
      <div
        style={{
          padding: '1rem 1.25rem',
          borderBottom: '1px solid rgba(31, 35, 40, 0.06)',
          backgroundColor: 'rgba(31, 35, 40, 0.02)',
        }}
      >
        <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 600, color: theme.colors.text.primary }}>{title}</h3>
      </div>
    )}
    <div style={{ padding: '1.25rem' }}>{children}</div>
  </div>
);

const Button = ({
  children,
  onClick,
  variant = 'primary',
  size = 'md',
  disabled = false,
  style,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  disabled?: boolean;
  style?: React.CSSProperties;
}) => {
  const baseStyles: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '0.5rem',
    border: 'none',
    borderRadius: theme.borderRadius.md,
    fontWeight: 500,
    cursor: disabled ? 'not-allowed' : 'pointer',
    transition: 'all 0.15s ease',
    opacity: disabled ? 0.5 : 1,
  };

  const sizeStyles = {
    sm: { padding: '0.4rem 0.75rem', fontSize: '0.8rem' },
    md: { padding: '0.6rem 1rem', fontSize: '0.875rem' },
    lg: { padding: '0.75rem 1.25rem', fontSize: '0.95rem' },
  };

  const variantStyles = {
    primary: {
      backgroundColor: theme.colors.primary[600],
      color: '#fff',
    },
    secondary: {
      backgroundColor: theme.colors.primary[100],
      color: theme.colors.primary[700],
    },
    danger: {
      backgroundColor: '#fee2e2',
      color: '#991b1b',
    },
    ghost: {
      backgroundColor: 'transparent',
      color: theme.colors.text.secondary,
    },
  };

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        ...baseStyles,
        ...sizeStyles[size],
        ...variantStyles[variant],
        ...style,
      }}
    >
      {children}
    </button>
  );
};

const Badge = ({ children, color = 'default' }: { children: React.ReactNode; color?: 'default' | 'primary' | 'success' | 'warning' | 'error' }) => {
  const colorMap = {
    default: { bg: '#f3f4f6', text: '#374151' },
    primary: { bg: '#dbeafe', text: '#1e40af' },
    success: { bg: '#dcfce7', text: '#166534' },
    warning: { bg: '#fef3c7', text: '#92400e' },
    error: { bg: '#fee2e2', text: '#991b1b' },
  };

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: '0.2rem 0.5rem',
        backgroundColor: colorMap[color].bg,
        color: colorMap[color].text,
        borderRadius: theme.borderRadius.full,
        fontSize: '0.75rem',
        fontWeight: 500,
      }}
    >
      {children}
    </span>
  );
};

const JsonViewer = ({ data }: { data: any }) => {
  const jsonString = JSON.stringify(data, null, 2);

  const highlightJson = (json: string) => {
    return json
      .replace(/"(.*?)":/g, '<span style="color: #7c3aed">"$1"</span>:')
      .replace(/: "(.*?)"/g, ': <span style="color: #059669">"$1"</span>')
      .replace(/: (\d+)/g, ': <span style="color: #d97706">$1</span>')
      .replace(/: (true|false)/g, ': <span style="color: #dc2626">$1</span>')
      .replace(/: (null)/g, ': <span style="color: #6b7280">$1</span>');
  };

  return (
    <pre
      style={{
        margin: 0,
        padding: '1rem',
        backgroundColor: '#1f2328',
        color: '#e5e7eb',
        borderRadius: theme.borderRadius.md,
        fontSize: '0.8rem',
        lineHeight: 1.5,
        overflow: 'auto',
        maxHeight: '400px',
        fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace',
      }}
      dangerouslySetInnerHTML={{ __html: highlightJson(jsonString) }}
    />
  );
};

// Main Page Component
export default function WebhookTestPage() {
  const [sessionId, setSessionId] = useState<string>('test_session_001');
  const [messages, setMessages] = useState<Message[]>([{ role: 'user', content: '' }]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentResponse, setCurrentResponse] = useState<WebhookResponse | null>(null);
  const [streamContent, setStreamContent] = useState<string>('');
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [selectedHistoryId, setSelectedHistoryId] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Generate new session ID
  const handleGenerateSessionId = () => {
    setSessionId(`test_${generateUUID().slice(0, 8)}`);
  };

  // Clear session
  const handleClearSession = () => {
    setMessages([{ role: 'user', content: '' }]);
    setCurrentResponse(null);
    setStreamContent('');
  };

  // Add message
  const handleAddMessage = () => {
    setMessages([...messages, { role: 'user', content: '' }]);
  };

  // Remove message
  const handleRemoveMessage = (index: number) => {
    if (messages.length <= 1) return;
    setMessages(messages.filter((_, i) => i !== index));
  };

  // Update message
  const handleUpdateMessage = (index: number, field: keyof Message, value: string) => {
    const newMessages = [...messages];
    newMessages[index] = { ...newMessages[index], [field]: value };
    setMessages(newMessages);
  };

  // Load test case
  const handleLoadTestCase = (testCase: TestCase) => {
    setMessages([...testCase.messages]);
    setCurrentResponse(null);
    setStreamContent('');
  };

  // Send webhook request
  const handleSendRequest = useCallback(async () => {
    const validMessages = messages.filter((m) => m.content.trim());
    if (validMessages.length === 0) return;

    setIsStreaming(true);
    setCurrentResponse(null);
    setStreamContent('');

    const historyItem: HistoryItem = {
      id: generateUUID(),
      timestamp: new Date().toISOString(),
      sessionId,
      messages: [...validMessages],
      response: null,
      status: 'pending',
    };

    setHistory((prev) => [historyItem, ...prev]);

    try {
      abortControllerRef.current = new AbortController();

      const response = await fetch('http://159.75.160.65:8501/webhook/MusicAgent', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          messages: validMessages,
          stream: true,
          sessionId,
        }),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let fullResponse: WebhookResponse | null = null;

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.trim().startsWith('data: ')) {
              const dataStr = line.trim().slice(6);
              if (dataStr === '[DONE]') continue;

              try {
                const data: WebhookResponse = JSON.parse(dataStr);
                fullResponse = data;

                if (data.reply?.streamInfo?.streamContent) {
                  setStreamContent((prev) => {
                    const newContent = data.reply!.streamInfo!.streamContent;
                    if (data.reply!.streamInfo!.streamType === 'start') {
                      return newContent;
                    }
                    return prev + newContent;
                  });
                }

                setCurrentResponse(data);
              } catch (e) {
                console.error('Failed to parse SSE data:', e);
              }
            }
          }
        }
      }

      setHistory((prev) =>
        prev.map((item) =>
          item.id === historyItem.id
            ? { ...item, response: fullResponse, status: 'success' }
            : item
        )
      );
    } catch (error) {
      console.error('Webhook request failed:', error);
      setHistory((prev) =>
        prev.map((item) =>
          item.id === historyItem.id
            ? { ...item, status: 'error' }
            : item
        )
      );
    } finally {
      setIsStreaming(false);
      abortControllerRef.current = null;
    }
  }, [messages, sessionId]);

  // Cancel request
  const handleCancelRequest = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setIsStreaming(false);
    }
  };

  // Load from history
  const handleLoadFromHistory = (item: HistoryItem) => {
    setSessionId(item.sessionId);
    setMessages([...item.messages]);
    setCurrentResponse(item.response);
    setSelectedHistoryId(item.id);
  };

  // Clear history
  const handleClearHistory = () => {
    setHistory([]);
    setSelectedHistoryId(null);
  };

  // Get category color
  const getCategoryColor = (category: string) => {
    switch (category) {
      case 'single':
        return { bg: '#dbeafe', text: '#1e40af', label: '单轮' };
      case 'multi':
        return { bg: '#f3e8ff', text: '#7c3aed', label: '多轮' };
      case 'special':
        return { bg: '#fef3c7', text: '#92400e', label: '特殊' };
      default:
        return { bg: '#f3f4f6', text: '#374151', label: '其他' };
    }
  };

  return (
    <MainLayout>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        {/* Header */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '0.5rem 0',
          }}
        >
          <div>
            <h1
              style={{
                margin: 0,
                fontSize: '1.5rem',
                fontWeight: 600,
                color: theme.colors.text.primary,
              }}
            >
              Webhook 测试工具
            </h1>
            <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.875rem', color: theme.colors.text.muted }}>
              测试 Music Agent Webhook API - POST /webhook/MusicAgent
            </p>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <Button variant="secondary" size="sm" onClick={handleClearSession}>
              清空会话
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={handleSendRequest}
              disabled={isStreaming || messages.every((m) => !m.content.trim())}
            >
              {isStreaming ? '发送中...' : '发送请求'}
            </Button>
            {isStreaming && (
              <Button variant="danger" size="sm" onClick={handleCancelRequest}>
                取消
              </Button>
            )}
          </div>
        </div>

        {/* Main Content Grid */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))',
            gap: '1.25rem',
          }}
        >
          {/* Left Column */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            {/* Session Management */}
            <Card title="会话管理">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <div>
                  <label
                    style={{
                      display: 'block',
                      fontSize: '0.8rem',
                      fontWeight: 500,
                      color: theme.colors.text.secondary,
                      marginBottom: '0.375rem',
                    }}
                  >
                    Session ID
                  </label>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <input
                      type="text"
                      value={sessionId}
                      onChange={(e) => setSessionId(e.target.value)}
                      style={{
                        flex: 1,
                        padding: '0.5rem 0.75rem',
                        border: `1px solid ${theme.colors.border.default}`,
                        borderRadius: theme.borderRadius.md,
                        fontSize: '0.875rem',
                        fontFamily: 'ui-monospace, monospace',
                      }}
                    />
                    <Button variant="secondary" size="sm" onClick={handleGenerateSessionId}>
                      生成
                    </Button>
                  </div>
                </div>
              </div>
            </Card>

            {/* Quick Test Cases */}
            <Card title="快速测试用例" style={{ flex: 1 }}>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))',
                  gap: '0.625rem',
                }}
              >
                {testCases.map((testCase) => {
                  const category = getCategoryColor(testCase.category);
                  return (
                    <button
                      key={testCase.id}
                      onClick={() => handleLoadTestCase(testCase)}
                      style={{
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'flex-start',
                        padding: '0.75rem',
                        backgroundColor: '#fff',
                        border: '1px solid rgba(31, 35, 40, 0.08)',
                        borderRadius: theme.borderRadius.md,
                        cursor: 'pointer',
                        transition: 'all 0.15s ease',
                        textAlign: 'left',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.borderColor = theme.colors.primary[400];
                        e.currentTarget.style.boxShadow = theme.shadows.sm;
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.borderColor = 'rgba(31, 35, 40, 0.08)';
                        e.currentTarget.style.boxShadow = 'none';
                      }}
                    >
                      <span
                        style={{
                          fontSize: '0.65rem',
                          fontWeight: 600,
                          padding: '0.15rem 0.4rem',
                          backgroundColor: category.bg,
                          color: category.text,
                          borderRadius: theme.borderRadius.full,
                          marginBottom: '0.375rem',
                        }}
                      >
                        {category.label}
                      </span>
                      <span
                        style={{
                          fontSize: '0.8rem',
                          fontWeight: 500,
                          color: theme.colors.text.primary,
                          lineHeight: 1.3,
                        }}
                      >
                        {testCase.label}
                      </span>
                      <span
                        style={{
                          fontSize: '0.7rem',
                          color: theme.colors.text.muted,
                          marginTop: '0.25rem',
                          lineHeight: 1.3,
                          display: '-webkit-box',
                          WebkitLineClamp: 2,
                          WebkitBoxOrient: 'vertical',
                          overflow: 'hidden',
                        }}
                      >
                        {testCase.description}
                      </span>
                    </button>
                  );
                })}
              </div>
            </Card>

            {/* Message Editor */}
            <Card title="消息编辑">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {messages.map((message, index) => (
                  <div
                    key={index}
                    style={{
                      display: 'flex',
                      gap: '0.5rem',
                      alignItems: 'flex-start',
                      padding: '0.75rem',
                      backgroundColor: 'rgba(31, 35, 40, 0.02)',
                      borderRadius: theme.borderRadius.md,
                      border: '1px solid rgba(31, 35, 40, 0.06)',
                    }}
                  >
                    <select
                      value={message.role}
                      onChange={(e) => handleUpdateMessage(index, 'role', e.target.value)}
                      style={{
                        padding: '0.4rem 0.5rem',
                        border: `1px solid ${theme.colors.border.default}`,
                        borderRadius: theme.borderRadius.sm,
                        fontSize: '0.8rem',
                        backgroundColor: '#fff',
                        minWidth: '90px',
                      }}
                    >
                      <option value="user">user</option>
                      <option value="assistant">assistant</option>
                    </select>
                    <textarea
                      value={message.content}
                      onChange={(e) => handleUpdateMessage(index, 'content', e.target.value)}
                      placeholder="输入消息内容..."
                      rows={2}
                      style={{
                        flex: 1,
                        padding: '0.4rem 0.625rem',
                        border: `1px solid ${theme.colors.border.default}`,
                        borderRadius: theme.borderRadius.sm,
                        fontSize: '0.875rem',
                        resize: 'vertical',
                        fontFamily: 'inherit',
                      }}
                    />
                    <button
                      onClick={() => handleRemoveMessage(index)}
                      disabled={messages.length <= 1}
                      style={{
                        padding: '0.4rem 0.625rem',
                        backgroundColor: messages.length <= 1 ? '#f3f4f6' : '#fee2e2',
                        color: messages.length <= 1 ? '#9ca3af' : '#991b1b',
                        border: 'none',
                        borderRadius: theme.borderRadius.sm,
                        cursor: messages.length <= 1 ? 'not-allowed' : 'pointer',
                        fontSize: '0.8rem',
                      }}
                    >
                      删除
                    </button>
                  </div>
                ))}
                <Button variant="secondary" size="sm" onClick={handleAddMessage} style={{ alignSelf: 'flex-start' }}>
                  + 添加消息
                </Button>
              </div>
            </Card>
          </div>

          {/* Right Column */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            {/* Response Display */}
            <Card title="响应展示">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {/* Stream Content */}
                <div>
                  <label
                    style={{
                      display: 'block',
                      fontSize: '0.8rem',
                      fontWeight: 500,
                      color: theme.colors.text.secondary,
                      marginBottom: '0.375rem',
                    }}
                  >
                    流式内容
                  </label>
                  <div
                    style={{
                      padding: '0.875rem',
                      backgroundColor: isStreaming ? '#f0fdf4' : '#f9fafb',
                      border: `1px solid ${isStreaming ? '#86efac' : 'rgba(31, 35, 40, 0.08)'}`,
                      borderRadius: theme.borderRadius.md,
                      minHeight: '80px',
                      fontSize: '0.875rem',
                      lineHeight: 1.6,
                      color: theme.colors.text.primary,
                      whiteSpace: 'pre-wrap',
                    }}
                  >
                    {streamContent || (
                      <span style={{ color: theme.colors.text.muted, fontStyle: 'italic' }}>
                        {isStreaming ? '等待响应...' : '暂无流式内容'}
                      </span>
                    )}
                    {isStreaming && (
                      <span
                        style={{
                          display: 'inline-block',
                          width: '2px',
                          height: '1em',
                          backgroundColor: theme.colors.primary[600],
                          marginLeft: '2px',
                          animation: 'blink 1s infinite',
                        }}
                      />
                    )}
                  </div>
                </div>

                {/* Action Display */}
                {currentResponse?.reply?.action && currentResponse.reply.action.length > 0 && (
                  <div>
                    <label
                      style={{
                        display: 'block',
                        fontSize: '0.8rem',
                        fontWeight: 500,
                        color: theme.colors.text.secondary,
                        marginBottom: '0.375rem',
                      }}
                    >
                      Action 指令
                    </label>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                      {currentResponse.reply.action.map((action, idx) => (
                        <div
                          key={idx}
                          style={{
                            padding: '0.75rem',
                            backgroundColor: '#eff6ff',
                            border: '1px solid #dbeafe',
                            borderRadius: theme.borderRadius.md,
                          }}
                        >
                          <Badge color="primary">{action.type}</Badge>
                          <div
                            style={{
                              marginTop: '0.5rem',
                              fontSize: '0.8rem',
                              fontFamily: 'ui-monospace, monospace',
                              color: theme.colors.text.secondary,
                            }}
                          >
                            {JSON.stringify(action, null, 2)}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Full JSON Response */}
                {currentResponse && (
                  <div>
                    <label
                      style={{
                        display: 'block',
                        fontSize: '0.8rem',
                        fontWeight: 500,
                        color: theme.colors.text.secondary,
                        marginBottom: '0.375rem',
                      }}
                    >
                      完整响应 JSON
                    </label>
                    <JsonViewer data={currentResponse} />
                  </div>
                )}
              </div>
            </Card>

            {/* History */}
            <Card title="历史记录">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {history.length === 0 ? (
                  <div
                    style={{
                      textAlign: 'center',
                      padding: '2rem',
                      color: theme.colors.text.muted,
                      fontSize: '0.875rem',
                    }}
                  >
                    暂无历史记录
                  </div>
                ) : (
                  <>
                    <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                      <Button variant="ghost" size="sm" onClick={handleClearHistory}>
                        清空历史
                      </Button>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '300px', overflow: 'auto' }}>
                      {history.map((item) => (
                        <button
                          key={item.id}
                          onClick={() => handleLoadFromHistory(item)}
                          style={{
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'flex-start',
                            padding: '0.75rem',
                            backgroundColor: selectedHistoryId === item.id ? '#eff6ff' : '#fff',
                            border: `1px solid ${selectedHistoryId === item.id ? '#3b82f6' : 'rgba(31, 35, 40, 0.08)'}`,
                            borderRadius: theme.borderRadius.md,
                            cursor: 'pointer',
                            textAlign: 'left',
                            width: '100%',
                            transition: 'all 0.15s ease',
                          }}
                        >
                          <div
                            style={{
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center',
                              width: '100%',
                              marginBottom: '0.375rem',
                            }}
                          >
                            <span style={{ fontSize: '0.75rem', color: theme.colors.text.muted }}>
                              {formatTimestamp(new Date(item.timestamp))}
                            </span>
                            <Badge
                              color={
                                item.status === 'success' ? 'success' : item.status === 'error' ? 'error' : 'warning'
                              }
                            >
                              {item.status === 'success' ? '成功' : item.status === 'error' ? '失败' : '进行中'}
                            </Badge>
                          </div>
                          <span
                            style={{
                              fontSize: '0.8rem',
                              fontWeight: 500,
                              color: theme.colors.text.primary,
                              lineHeight: 1.4,
                              display: '-webkit-box',
                              WebkitLineClamp: 2,
                              WebkitBoxOrient: 'vertical',
                              overflow: 'hidden',
                            }}
                          >
                            {item.messages[item.messages.length - 1]?.content || '无内容'}
                          </span>
                          <span
                            style={{
                              fontSize: '0.7rem',
                              color: theme.colors.text.muted,
                              marginTop: '0.25rem',
                              fontFamily: 'ui-monospace, monospace',
                            }}
                          >
                            {item.sessionId}
                          </span>
                        </button>
                      ))}
                    </div>
                  </>
                )}
              </div>
            </Card>
          </div>
        </div>
      </div>

      <style jsx global>{`
        @keyframes blink {
          0%, 50% { opacity: 1; }
          51%, 100% { opacity: 0; }
        }
      `}</style>
    </MainLayout>
  );
}
