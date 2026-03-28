'use client';

import { useState, FormEvent } from 'react';
import SendButton from './SendButton';
import { theme } from '@/styles/theme';

interface ChatInputProps {
  onSubmit: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  isMobile?: boolean;
}

const quickPrompts = ['晨跑的鼓点', '办公室保持专注', '串联周末的晚风'];

export default function ChatInput({
  onSubmit,
  placeholder = '输入你的问题...',
  disabled = false,
  isMobile = false,
}: ChatInputProps) {
  const [value, setValue] = useState('');

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (value.trim() && !disabled) {
      onSubmit(value.trim());
      setValue('');
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      style={{
        margin: isMobile ? '1.25rem auto 0' : '1.5rem auto 1rem',
        padding: isMobile ? '0 0.25rem' : '0 1rem',
        backgroundColor: 'transparent',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.65rem',
        position: 'sticky',
        bottom: isMobile ? '0.5rem' : '1.5rem',
        width: '100%',
        maxWidth: isMobile ? '520px' : '640px',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.4rem',
          flexWrap: 'wrap',
        }}
      >
        <span
          style={{
            fontSize: '0.82rem',
            color: theme.colors.text.muted,
            marginBottom: '0.15rem',
          }}
        >
          快速提问
        </span>
        {quickPrompts.map((prompt) => (
          <button
            key={prompt}
            type="button"
            onClick={() => setValue(prompt)}
            style={{
              padding: '0.25rem 0.85rem',
              borderRadius: theme.borderRadius.full,
              border: '1px solid rgba(31, 35, 40, 0.08)',
              backgroundColor: theme.colors.background.card,
              color: theme.colors.text.secondary,
              fontSize: '0.8rem',
              cursor: 'pointer',
            }}
          >
            {prompt}
          </button>
        ))}
      </div>
      <div
        style={{
          display: 'flex',
          gap: isMobile ? '0.5rem' : '0.65rem',
          alignItems: 'center',
          flexDirection: isMobile ? 'column' : 'row',
        }}
      >
        <div
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            backgroundColor: theme.colors.background.card,
            borderRadius: theme.borderRadius.full,
            border: '1px solid rgba(31, 35, 40, 0.1)',
            padding: isMobile ? '0.3rem 0.3rem 0.3rem 1rem' : '0.35rem 0.35rem 0.35rem 1.5rem',
          }}
        >
          <input
            type="text"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={placeholder}
            disabled={disabled}
            style={{
              
              flex: 1,
              padding: '0.65rem 0',
              fontSize: '1rem',
              minHeight: '38px',
              border: 'none',
              backgroundColor: 'transparent',
              color: theme.colors.text.primary,
              outline: 'none',
            }}
          />
          <SendButton
            onClick={(e) => {
              e.preventDefault();
              if (value.trim() && !disabled) {
                onSubmit(value.trim());
                setValue('');
              }
            }}
            disabled={disabled || !value.trim()}
          />
        </div>
      </div>
      {!isMobile && (
        <span
          style={{
            fontSize: '0.78rem',
            color: theme.colors.text.muted,
            textAlign: 'right',
          }}
        >
          提示：Shift + Enter 换行
        </span>
      )}
    </form>
  );
}

