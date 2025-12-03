'use client';

import { theme } from '@/styles/theme';

interface ProductIntroProps {
  onPrimaryAction?: () => void;
  onSecondaryAction?: () => void;
  onQuickExampleSelect?: (prompt: string) => void;
}

const insightStats = [
  { label: '理解能力', value: '心情 / 场景 / 流派', hint: 'LangGraph + LLM 意图识别' },
  { label: '推荐链路', value: 'Spotify + 网络搜索', hint: 'MCP 直连官方 API' },
  { label: '交互体验', value: 'SSE 流式输出', hint: '逐词推荐说明 + 逐首上屏' },
];

const quickExamples = [
  { title: '给加班夜写代码的人推荐稳态节奏', meta: '心情：专注 / 场景：深夜' },
  { title: '我想在雨天窗边听些治愈的独立民谣', meta: '联动心情 + 流派' },
  { title: '根据周杰伦帮我找一些同样浪漫的中文 R&B', meta: '歌手 + 风格' },
];

const heroTags = ['心情理解', '场景推荐', 'SSE 流式', 'Spotify 接入'];

export default function ProductIntro({ onPrimaryAction, onSecondaryAction, onQuickExampleSelect }: ProductIntroProps) {
  return (
    <section
      style={{
        flex: 1,
        width: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '2rem 1.5rem 3rem',
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: `${theme.layout.contentMaxWidth}px`,
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 0.9fr)',
          gap: '1.75rem',
        }}
      >
        <div
          style={{
            borderRadius: theme.borderRadius.lg,
            background: 'linear-gradient(135deg, #11160d 0%, #4d544b 60%, #7c8475 100%)',
            padding: '2.5rem',
            color: '#fff',
            position: 'relative',
            overflow: 'hidden',
            boxShadow: theme.shadows.lg,
          }}
        >
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.45rem',
              padding: '0.4rem 0.95rem',
              borderRadius: theme.borderRadius.full,
              backgroundColor: 'rgba(255, 255, 255, 0.08)',
              fontSize: '0.82rem',
            }}
          >
            <span
              style={{
                display: 'inline-block',
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: '#9de68a',
                boxShadow: '0 0 8px rgba(157, 230, 138, 0.65)',
              }}
            />
            音乐推荐 Agent 已就绪
          </span>

          <h1
            style={{
              margin: '1.5rem 0 0',
              fontSize: '2.6rem',
              lineHeight: 1.25,
              fontWeight: 600,
              letterSpacing: '-0.02em',
            }}
          >
            用一句自然语言
            <br />
            即刻生成专属音乐推荐。
          </h1>

          <p
            style={{
              marginTop: '1rem',
              maxWidth: '34rem',
              fontSize: '1rem',
              lineHeight: 1.8,
              color: 'rgba(255,255,255,0.82)',
            }}
          >
            基于 LangGraph 工作流 + Spotify/MCP + Tavily 搜索，自动理解心情、场景和喜好，串联搜索、推荐与解释，让每一首歌的理由都清晰可见。
          </p>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.6rem', marginTop: '1.5rem' }}>
            {heroTags.map((tag) => (
              <span
                key={tag}
                style={{
                  padding: '0.35rem 0.9rem',
                  borderRadius: theme.borderRadius.full,
                  fontSize: '0.82rem',
                  border: '1px solid rgba(255,255,255,0.15)',
                  backgroundColor: 'rgba(255,255,255,0.05)',
                }}
              >
                {tag}
              </span>
            ))}
          </div>

          <div
            style={{
              marginTop: '2rem',
              display: 'flex',
              flexWrap: 'wrap',
              gap: '0.8rem',
              alignItems: 'center',
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
                color: '#0f140c',
                backgroundColor: '#cdf8c0',
                boxShadow: '0 15px 35px rgba(0,0,0,0.25)',
              }}
            >
              进入推荐体验
            </button>
            <button
              type="button"
              onClick={onSecondaryAction}
              style={{
                borderRadius: theme.borderRadius.full,
                border: '1px solid rgba(255,255,255,0.35)',
                padding: '0.85rem 1.6rem',
                fontWeight: 500,
                fontSize: '0.95rem',
                cursor: 'pointer',
                color: '#fff',
                backgroundColor: 'transparent',
              }}
            >
              查看使用指南
            </button>
          </div>

          <div
            style={{
              position: 'absolute',
              inset: 'auto 2rem 2rem auto',
              width: '180px',
              height: '180px',
              borderRadius: '32px',
              background: 'radial-gradient(circle, rgba(255,255,255,0.8), rgba(255,255,255,0))',
              opacity: 0.15,
            }}
          />
        </div>

        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '1.1rem',
            padding: '0.35rem',
          }}
        >
          <div
            style={{
              borderRadius: theme.borderRadius.lg,
              backgroundColor: theme.colors.background.card,
              border: `1px solid ${theme.colors.border.default}`,
              padding: '1.6rem',
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
              gap: '1rem',
            }}
          >
            {insightStats.map((stat) => (
              <div
                key={stat.label}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.3rem',
                }}
              >
                <span style={{ fontSize: '0.78rem', letterSpacing: '0.12em', color: theme.colors.text.muted }}>
                  {stat.label}
                </span>
                <strong style={{ fontSize: '1.2rem', color: theme.colors.text.primary }}>{stat.value}</strong>
                <span style={{ fontSize: '0.85rem', color: theme.colors.text.secondary }}>{stat.hint}</span>
              </div>
            ))}
          </div>

          <div
            style={{
              borderRadius: theme.borderRadius.lg,
              background: theme.colors.background.main,
              border: `1px solid ${theme.colors.border.default}`,
              padding: '1.5rem',
              boxShadow: theme.shadows.sm,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <div>
                <p style={{ margin: 0, fontSize: '1.05rem', fontWeight: 600, color: theme.colors.text.primary }}>快速灵感</p>
                <span style={{ fontSize: '0.85rem', color: theme.colors.text.muted }}>点击示例即可注入输入框</span>
              </div>
              <span style={{ fontSize: '0.8rem', color: theme.colors.text.muted }}>Shift + Enter 换行</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
              {quickExamples.map((example) => (
                <div
                  key={example.title}
                  style={{
                    borderRadius: theme.borderRadius.md,
                    padding: '0.95rem 1.1rem',
                    backgroundColor: '#fff',
                    border: `1px solid ${theme.colors.border.default}`,
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}
                >
                  <div>
                    <p style={{ margin: 0, fontWeight: 600, color: theme.colors.text.primary }}>{example.title}</p>
                    <span style={{ fontSize: '0.85rem', color: theme.colors.text.secondary }}>{example.meta}</span>
                  </div>
                  <button
                    type='button'
                    onClick={() => onQuickExampleSelect?.(example.title)}
                    style={{
                      border: 'none',
                      background: theme.colors.background.hover,
                      color: theme.colors.text.primary,
                      borderRadius: theme.borderRadius.full,
                      padding: '0.4rem 0.9rem',
                      fontSize: '0.82rem',
                      cursor: 'pointer',
                    }}
                  >
                    注入提示
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div
            style={{
              borderRadius: theme.borderRadius.lg,
              backgroundColor: theme.colors.background.card,
              border: `1px solid ${theme.colors.border.default}`,
              padding: '1.25rem 1.5rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '1rem',
            }}
          >
            <div>
              <p style={{ margin: 0, fontWeight: 600, color: theme.colors.text.primary }}>流程提示</p>
              <span style={{ fontSize: '0.86rem', color: theme.colors.text.secondary }}>先从「产品首页」了解流转，再进入场景操作。</span>
            </div>
            <button
              type='button'
              style={{
                borderRadius: theme.borderRadius.full,
                border: `1px solid ${theme.colors.border.default}`,
                padding: '0.5rem 1.2rem',
                background: theme.colors.background.hover,
                cursor: 'pointer',
              }}
            >
              查看 Demo
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
