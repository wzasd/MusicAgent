'use client';

import { ReactNode } from 'react';
import NavItem from './NavItem';
import { theme } from '@/styles/theme';

interface NavItemConfig {
  href: string;
  label: string;
  description: string;
  icon: ReactNode;
}

interface NavGroup {
  title: string;
  subtitle: string;
  items: NavItemConfig[];
}

interface SidebarProps {
  isMobile?: boolean;
  isOpen?: boolean;
  onClose?: () => void;
}

const navGroups: NavGroup[] = [
  {
    title: '核心流程',
    subtitle: '从入门到推荐',
    items: [
      {
        href: '/',
        label: '产品首页',
        description: '概览与流程',
        icon: (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
            <path d="M3 9.5L12 3l9 6.5" />
            <path d="M5 11v9h14v-9" />
          </svg>
        ),
      },
      {
        href: '/recommendations',
        label: '音乐推荐',
        description: '语义生成',
        icon: (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
            <path d="M9 18V5l12-2v13" />
            <circle cx="6" cy="18" r="3" />
            <circle cx="18" cy="16" r="3" />
          </svg>
        ),
      },
    ],
  },
  {
    title: '创作工具',
    subtitle: '深度定制',
    items: [
      {
        href: '/search',
        label: '歌曲搜索',
        description: '多模态检索',
        icon: (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
        ),
      },
      {
        href: '/playlist',
        label: '歌单创作',
        description: '风格编排器',
        icon: (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
            <rect x="3" y="4" width="18" height="4" rx="1" />
            <rect x="3" y="12" width="13" height="4" rx="1" />
            <circle cx="18" cy="14" r="2" />
          </svg>
        ),
      },
      {
        href: '/journey',
        label: '音乐旅程',
        description: '听歌轨迹',
        icon: (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
            <path d="M3 17l6-6 4 4 8-8" />
            <path d="M14 7h7v7" />
          </svg>
        ),
      },
    ],
  },
];

export default function Sidebar({ isMobile = false, isOpen = true, onClose }: SidebarProps) {
  if (isMobile && !isOpen) {
    return null;
  }

  const commonStyles = {
    height: '100vh',
    background: 'linear-gradient(180deg, #131711 0%, #1b2116 45%, #21271b 100%)',
    borderRight: `1px solid rgba(255,255,255,0.08)`,
    padding: '2.2rem 1.75rem',
    overflowY: 'auto' as const,
    zIndex: 10,
    color: '#fff',
  };

  const asideStyles = isMobile
    ? {
        ...commonStyles,
        position: 'fixed' as const,
        left: 0,
        top: 0,
        width: '78vw',
        maxWidth: '320px',
        transform: isOpen ? 'translateX(0)' : 'translateX(-100%)',
        transition: 'transform 0.25s ease',
        borderRadius: '0 20px 20px 0',
      }
    : {
        ...commonStyles,
        position: 'fixed' as const,
        left: 0,
        top: 0,
        width: `${theme.layout.sidebarWidth}px`,
      };

  return (
    <aside style={asideStyles}>
      {isMobile && (
        <button
          type="button"
          onClick={onClose}
          style={{
            position: 'absolute',
            top: '1rem',
            right: '1rem',
            border: 'none',
            background: 'transparent',
            fontSize: '1rem',
            color: theme.colors.text.muted,
            cursor: 'pointer',
          }}
        >
          关闭
        </button>
      )}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '0.8rem',
          marginBottom: '2.5rem',
        }}
      >
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.75rem',
          }}
        >
          <div
            style={{
              width: '60px',
              height: '60px',
              borderRadius: theme.borderRadius.full,
              background: 'linear-gradient(135deg, #d0ffc2 0%, #8ef2c1 100%)',
              color: '#0f180c',
              fontWeight: 700,
              fontSize: '1rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 10px 25px rgba(0,0,0,0.2)',
            }}
          >
            DS
          </div>
          <div>
            <p style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600 }}>Deep Search</p>
            <span style={{ fontSize: '0.85rem', color: 'rgba(255,255,255,0.6)' }}>音乐体验工作台</span>
          </div>
        </div>
        <div
          style={{
            borderRadius: theme.borderRadius.md,
            padding: '0.9rem 1rem',
            backgroundColor: 'rgba(255,255,255,0.04)',
            border: '1px solid rgba(255,255,255,0.06)',
            fontSize: '0.85rem',
            color: 'rgba(255,255,255,0.78)',
            lineHeight: 1.6,
          }}
        >
          <strong style={{ display: 'block', fontSize: '0.78rem', letterSpacing: '0.18em', color: '#c0f0a5' }}>
            LIVE MODE
          </strong>
          推荐引擎实时同步节奏数据库，适合在展览与现场活动快速应用。
        </div>
      </div>

      <nav style={{ display: 'flex', flexDirection: 'column', gap: '1.35rem' }}>
        {navGroups.map((group) => (
          <div key={group.title} style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
              <span style={{ fontSize: '0.8rem', letterSpacing: '0.18em', color: 'rgba(255,255,255,0.5)' }}>
                {group.title}
              </span>
              <span style={{ fontSize: '0.85rem', color: 'rgba(255,255,255,0.65)' }}>{group.subtitle}</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem' }}>
              {group.items.map((item) => (
                <NavItem key={item.href} {...item} />
              ))}
            </div>
          </div>
        ))}
      </nav>

      <div
        style={{
          marginTop: '2.5rem',
          padding: '1.2rem',
          borderRadius: theme.borderRadius.lg,
          background: 'rgba(255,255,255,0.03)',
          border: '1px solid rgba(255,255,255,0.05)',
        }}
      >
        <p style={{ color: '#fff', fontSize: '0.95rem', marginBottom: '0.35rem', fontWeight: 600 }}>快速导览</p>
        <p style={{ color: 'rgba(255,255,255,0.65)', fontSize: '0.82rem', lineHeight: 1.6 }}>
          推荐先看「产品首页」的视频导览，再进入「音乐推荐」体验生成流程。
        </p>
        <button
          type="button"
          style={{
            width: '100%',
            borderRadius: theme.borderRadius.full,
            border: 'none',
            padding: '0.7rem 1rem',
            background: '#c6f7a9',
            color: '#0f120d',
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          打开引导
        </button>
      </div>
    </aside>
  );
}


