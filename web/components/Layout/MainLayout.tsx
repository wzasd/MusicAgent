'use client';

import { ReactNode, useState } from 'react';
import Header from './Header';
import Sidebar from '../Navigation/Sidebar';
import ChatInput from '../Input/ChatInput';
import { theme } from '@/styles/theme';
import { useMediaQuery } from '@/hooks/useMediaQuery';

interface MainLayoutProps {
  children: ReactNode;
  onInputSubmit?: (value: string) => void;
  inputPlaceholder?: string;
  inputDisabled?: boolean;
}

export default function MainLayout({
  children,
  onInputSubmit,
  inputPlaceholder,
  inputDisabled = false,
}: MainLayoutProps) {
  const isMobile = useMediaQuery('(max-width: 960px)');
  const [isSidebarOpen, setSidebarOpen] = useState(false);
  const sidebarWidth = isMobile ? 0 : theme.layout.sidebarWidth;
  const containerPadding = isMobile ? '1rem' : '2rem';

  return (
    <div
      style={{
        minHeight: '100vh',
        backgroundColor: theme.colors.light.primary,
      }}
    >
      {isMobile && isSidebarOpen && (
        <div
          onClick={() => setSidebarOpen(false)}
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.35)',
            zIndex: 9,
            backdropFilter: 'blur(4px)',
          }}
        />
      )}
      <Sidebar
        isMobile={isMobile}
        isOpen={isMobile ? isSidebarOpen : true}
        onClose={() => setSidebarOpen(false)}
      />
      <div
        style={{
          marginLeft: isMobile ? 0 : `${sidebarWidth}px`,
          display: 'flex',
          flexDirection: 'column',
          minHeight: '100vh',
          padding: containerPadding,
          gap: '1.75rem',
        }}
      >
        <Header
          onMenuToggle={isMobile ? () => setSidebarOpen((prev) => !prev) : undefined}
          isMobile={isMobile}
        />
        <main
          style={{
            flex: 1,
            width: '100%',
            alignSelf: 'center',
            maxWidth: `${theme.layout.contentMaxWidth}px`,
            margin: '0 auto',
            padding: 0,
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <div
            style={{
              flex: 1,
              width: '100%',
              backgroundColor: '#f1f4ed',
              borderRadius: isMobile ? '0.75rem' : '1.15rem',
              border: `1px solid rgba(31, 35, 40, 0.06)`,
              padding: isMobile ? '1.25rem' : '2.5rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '1.25rem',
            }}
          >
            {children}
          </div>
        </main>
        {onInputSubmit && (
          <ChatInput
            onSubmit={onInputSubmit}
            placeholder={inputPlaceholder}
            disabled={inputDisabled}
            isMobile={isMobile}
          />
        )}
      </div>
    </div>
  );
}


