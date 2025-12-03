/**
 * 绿色主题配置
 */
export const theme = {
  colors: {
    primary: {
      50: '#f7f7f2',
      100: '#eceee7',
      200: '#d9dccf',
      300: '#c5c7b8',
      400: '#a2a79a',
      500: '#7c8475',
      600: '#60685b',
      700: '#474d44',
      800: '#30332d',
      900: '#23251f',
    },
    text: {
      primary: '#1f2328',
      secondary: '#4b505a',
      muted: '#70757f',
    },
    background: {
      main: '#f7f7f2',
      card: '#ffffff',
      hover: '#eeefe8',
    },
    border: {
      default: '#dfe1d7',
      focus: '#9ba08f',
    },
  },
  gradients: {
    primary: 'linear-gradient(135deg, #4d544b 0%, #23251f 100%)',
    accent: 'linear-gradient(135deg, #7c8475 0%, #4d544b 100%)',
    background: '#f7f7f2',
  },
  spacing: {
    xs: '0.5rem',
    sm: '1rem',
    md: '1.5rem',
    lg: '2rem',
    xl: '3rem',
  },
  borderRadius: {
    sm: '0.5rem',
    md: '0.75rem',
    lg: '1rem',
    full: '9999px',
  },
  shadows: {
    sm: '0 3px 6px rgba(15, 23, 42, 0.04)',
    md: '0 8px 20px rgba(15, 23, 42, 0.08)',
    lg: '0 20px 45px rgba(15, 23, 42, 0.12)',
  },
  layout: {
    sidebarWidth: 232,
    contentMaxWidth: 1120,
    maxWidth: 1440,
  },
};

