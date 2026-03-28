/**
 * 现代科技感音乐主题配置
 * 基于绿色系 + Tailwind CSS 设计系统
 */
export const theme = {
  colors: {
    // 主色调 - 翡翠绿
    primary: {
      50: '#f0fdf4',
      100: '#dcfce7',
      200: '#bbf7d0',
      300: '#86efac',
      400: '#4ade80',
      500: '#22c55e',
      600: '#16a34a',
      700: '#15803d',
      800: '#166534',
      900: '#14532d',
      950: '#052e16',
    },
    // 深色系
    dark: {
      primary: '#0f1410',
      secondary: '#1a1f1a',
      tertiary: '#252b25',
    },
    // 浅色系
    light: {
      primary: '#faf9f5',
      secondary: '#f5f4f0',
      tertiary: '#eeefe8',
    },
    // 文本颜色
    text: {
      primary: '#0f1410',
      secondary: '#4b505a',
      muted: '#70757f',
      inverse: '#faf9f5',
    },
    // 边框颜色
    border: {
      default: '#dfe1d7',
      focus: '#4ade80',
      hover: '#86efac',
    },
    // 强调色
    accent: {
      orange: '#d97757',
      blue: '#6a9bcc',
    },
  },
  gradients: {
    primary: 'linear-gradient(135deg, #16a34a 0%, #0f1410 100%)',
    accent: 'linear-gradient(135deg, #4ade80 0%, #16a34a 100%)',
    mesh: `
      radial-gradient(at 40% 20%, rgba(16, 185, 129, 0.3) 0px, transparent 50%),
      radial-gradient(at 80% 0%, rgba(26, 163, 156, 0.3) 0px, transparent 50%),
      radial-gradient(at 0% 50%, rgba(16, 185, 129, 0.2) 0px, transparent 50%)
    `,
    glow: 'radial-gradient(circle, rgba(74, 222, 128, 0.4) 0%, transparent 70%)',
  },
  spacing: {
    xs: '0.25rem',
    sm: '0.5rem',
    md: '1rem',
    lg: '1.5rem',
    xl: '2rem',
    '2xl': '3rem',
    '3xl': '4rem',
  },
  borderRadius: {
    sm: '0.375rem',
    md: '0.5rem',
    lg: '0.75rem',
    xl: '1rem',
    '2xl': '1.5rem',
    '3xl': '2rem',
    full: '9999px',
  },
  shadows: {
    sm: '0 2px 4px rgba(15, 20, 16, 0.05)',
    md: '0 4px 12px rgba(15, 20, 16, 0.08)',
    lg: '0 8px 24px rgba(15, 20, 16, 0.12)',
    xl: '0 16px 48px rgba(15, 20, 16, 0.16)',
    glow: '0 0 40px rgba(16, 185, 129, 0.4)',
    glowLg: '0 0 60px rgba(16, 185, 129, 0.6)',
  },
  layout: {
    sidebarWidth: 240,
    contentMaxWidth: 1200,
    maxWidth: 1440,
  },
  animation: {
    spring: {
      type: 'spring',
      stiffness: 150,
      damping: 20,
    },
    snappy: {
      type: 'spring',
      stiffness: 300,
      damping: 30,
    },
    smooth: {
      duration: 0.3,
      ease: [0.16, 1, 0.3, 1],
    },
  },
};

