'use client';

import { theme } from '@/styles/theme';

interface WelcomeScreenProps {
  title?: string;
  description?: string;
  badgeLabel?: string;
  subtitle?: string;
  onPrimaryAction?: () => void;
  onSecondaryAction?: () => void;
}

const metricCards = [
  {
    label: '智能理解',
    value: '心情 / 场景 / 流派',
    detail: '基于大模型自动解析你的自然语言需求',
  },
  {
    label: '推荐来源',
    value: 'Spotify + 网络',
    detail: '综合在线乐库与本地示例库进行多路推荐',
  },
  {
    label: '交互体验',
    value: 'SSE 流式输出',
    detail: '推荐说明与歌曲逐步流式返回，实时刷新界面',
  },
];

export default function WelcomeScreen({
  title = '音乐推荐 Agent',
  description = '用一句自然语言描述你的心情、场景或喜欢的歌手，AI 会自动理解你的需求，联动 Spotify / 网络搜索与本地数据，为你生成解释清晰的个性化音乐推荐。',
  badgeLabel = 'SSE 流式推荐 · 实时响应',
  subtitle = '推荐页支持流式 AI 讲解与逐首推荐，搜索页提供按关键词与流派的快速歌曲发现。',
  onPrimaryAction,
  onSecondaryAction,
}: WelcomeScreenProps) {
  return (
    <section
      style={{
        width: '100%',
        padding: '3rem 1.5rem 4rem',
        background: 'linear-gradient(180deg, #f8f8f1 0%, #fafaf7 65%, #ffffff 100%)',
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: `${theme.layout.contentMaxWidth}px`,
          margin: '0 auto',
          display: 'flex',
          flexDirection: 'column',
          gap: '2rem',
          alignItems: 'center',
          textAlign: 'center',
        }}
      >
        <div
          style={{
            padding: '0.35rem 1rem',
            borderRadius: theme.borderRadius.full,
            backgroundColor: '#ececf5',
            color: '#43338b',
            fontSize: '0.82rem',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.4rem',
            boxShadow: '0 6px 12px rgba(67, 51, 139, 0.08)',
          }}
        >
          <span
            style={{
              width: '6px',
              height: '6px',
              borderRadius: '50%',
              backgroundColor: '#5b21b6',
            }}
          />
          {badgeLabel}
        </div>

        <div style={{ maxWidth: '720px' }}>
          <h1
            style={{
              margin: '1rem 0 0.5rem',
              fontSize: '2.2rem',
              lineHeight: 1.3,
              fontWeight: 600,
              color: theme.colors.text.primary,
            }}
          >
            {title}
          </h1>
          <p
            style={{
              margin: '0 auto',
              fontSize: '1rem',
              lineHeight: 1.75,
              color: theme.colors.text.secondary,
              maxWidth: '56ch',
            }}
          >
            {description}
          </p>
        </div>

        <div
          style={{
            position: 'relative',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.75rem',
            alignItems: 'center',
            width: '100%',
            maxWidth: '640px',
            backgroundColor: '#ffffff',
            borderRadius: '28px',
            border: `1px solid ${theme.colors.border.default}`,
            padding: '2rem 1.5rem',
            boxShadow: '0 25px 60px rgba(23, 23, 23, 0.08)',
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              position: 'absolute',
              inset: 0,
              borderRadius: 'inherit',
              background: 'radial-gradient(circle at 30% 20%, rgba(119, 102, 205, 0.12), transparent 60%)',
              pointerEvents: 'none',
            }}
          />

          <div
            style={{
              display: 'flex',
              gap: '1rem',
              flexWrap: 'wrap',
              justifyContent: 'center',
              position: 'relative',
            }}
          >
            <button
              type="button"
              onClick={onPrimaryAction}
              style={{
                borderRadius: theme.borderRadius.full,
                border: 'none',
                padding: '0.85rem 1.8rem',
                fontWeight: 600,
                fontSize: '0.95rem',
                cursor: 'pointer',
                color: '#fff',
                background: 'linear-gradient(135deg, #4c1d95, #6b4ef5)',
                boxShadow: '0 12px 25px rgba(76, 29, 149, 0.35)',
              }}
            >
              开始智能推荐
            </button>
            <button
              type="button"
              onClick={onSecondaryAction}
              style={{
                borderRadius: theme.borderRadius.full,
                border: `1px solid ${theme.colors.border.default}`,
                padding: '0.85rem 1.6rem',
                fontWeight: 500,
                fontSize: '0.95rem',
                cursor: 'pointer',
                color: theme.colors.text.primary,
                backgroundColor: '#fff',
              }}
            >
              查看使用指南
            </button>
          </div>
          <p
            style={{
              margin: 0,
              fontSize: '0.88rem',
              color: theme.colors.text.secondary,
            }}
          >
            {subtitle}
          </p>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '1rem',
            width: '100%',
            maxWidth: '960px',
          }}
        >
          {metricCards.map((metric) => (
            <div
              key={metric.label}
              style={{
                padding: '1.1rem',
                borderRadius: '20px',
                border: `1px solid ${theme.colors.border.default}`,
                backgroundColor: '#fff',
                textAlign: 'left' as const,
                boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.6)',
              }}
            >
              <p
                style={{
                  margin: 0,
                  fontSize: '0.78rem',
                  color: theme.colors.text.muted,
                  letterSpacing: '0.08em',
                  textTransform: 'uppercase',
                }}
              >
                {metric.label}
              </p>
              <p
                style={{
                  margin: '0.35rem 0 0.2rem',
                  fontSize: '1.3rem',
                  fontWeight: 600,
                  color: theme.colors.text.primary,
                }}
              >
                {metric.value}
              </p>
              <p
                style={{
                  margin: 0,
                  fontSize: '0.82rem',
                  color: theme.colors.text.secondary,
                  lineHeight: 1.5,
                }}
              >
                {metric.detail}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

