import React from 'react';
import type { Message } from '../types';
import { ReasoningPanel } from './ReasoningPanel';

interface MessageBubbleProps {
  message: Message;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  if (message.role === 'user') {
    return (
      <div style={{ display: 'flex', justifyContent: 'flex-end' }} className="animate-fade-up">
        <div
          style={{
            maxWidth: '70%',
            padding: '0.625rem 1rem',
            borderRadius: '1.5rem',
            background: 'var(--user-bubble)',
            color: 'var(--foreground)',
            fontSize: '1rem',
            lineHeight: '1.7',
            wordBreak: 'break-word',
          }}
        >
          {message.content}
        </div>
      </div>
    );
  }

  if (message.loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem', padding: '0.35rem 0' }} className="animate-fade-up">
        <span style={{ display: 'flex', gap: '0.3rem', alignItems: 'center' }}>
          <span className="dot-1" style={{ width: 9, height: 9, borderRadius: '50%', display: 'inline-block', background: '#bbb' }} />
          <span className="dot-2" style={{ width: 9, height: 9, borderRadius: '50%', display: 'inline-block', background: '#bbb' }} />
          <span className="dot-3" style={{ width: 9, height: 9, borderRadius: '50%', display: 'inline-block', background: '#bbb' }} />
        </span>
        <span style={{ fontSize: '0.825rem', color: '#888', fontStyle: 'italic' }}>Thinking</span>
      </div>
    );
  }

  if (message.isError) {
    const isRateLimit = !!message.rateLimitReset;
    return (
      <div
        className="animate-fade-up"
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: '0.75rem',
          padding: '0.875rem 1rem',
          borderRadius: '0.875rem',
          background: 'rgba(239,68,68,0.08)',
          border: '1px solid rgba(239,68,68,0.25)',
        }}
      >
        <span style={{ fontSize: '1.1rem', lineHeight: 1, marginTop: '0.1rem', flexShrink: 0 }}>
          {isRateLimit ? '🚫' : '⚠️'}
        </span>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#f87171', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
            {isRateLimit ? 'Limit reached' : 'Request failed'}
          </span>
          <span style={{ fontSize: '0.9rem', color: '#d1d1d1', lineHeight: 1.6 }}>
            {message.content}
          </span>
          <span style={{ fontSize: '0.8rem', color: '#888', marginTop: '0.25rem' }}>
            {isRateLimit
              ? `Resets on ${message.rateLimitReset}`
              : 'Check that the backend is running, then try again.'}
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="animate-fade-up" style={{ color: '#ececec', fontSize: '1rem', lineHeight: '1.8' }}>
      {(message.reasoning_steps?.length || message.thinking) && (
        <div style={{ marginBottom: '1.25rem' }}>
          <ReasoningPanel steps={message.reasoning_steps ?? []} thinking={message.thinking} />
        </div>
      )}
      {renderContent(message.content)}
    </div>
  );
}

function renderContent(raw: string) {
  const lines = raw.trim().split('\n');
  return lines.map((line, i) => {
    if (line.startsWith('#### ')) return <Heading4 key={i}>{renderInline(line.slice(5))}</Heading4>;
    if (line.startsWith('### '))  return <Heading3 key={i}>{renderInline(line.slice(4))}</Heading3>;
    if (line.startsWith('## '))   return <Heading2 key={i}>{renderInline(line.slice(3))}</Heading2>;

    const numMatch = line.match(/^(\d+\.\s)(.*)$/);
    if (numMatch) {
      return (
        <div key={i} style={{ display: 'flex', gap: '0.625rem', margin: '0.3rem 0', paddingLeft: '2px' }}>
          <span style={{ flexShrink: 0, fontWeight: 600, color: '#ffffff', minWidth: '1.5rem' }}>{numMatch[1]}</span>
          <span style={{ color: '#ececec' }}>{renderInline(numMatch[2])}</span>
        </div>
      );
    }

    if (line.startsWith('- ') || line.startsWith('* ')) {
      return (
        <div key={i} style={{ display: 'flex', gap: '0.625rem', margin: '0.3rem 0', paddingLeft: '2px' }}>
          <span style={{ flexShrink: 0, color: '#ececec', marginTop: '0.1rem' }}></span>
          <span style={{ color: '#ececec' }}>{renderInline(line.slice(2))}</span>
        </div>
      );
    }

    if (line.trim() === '') return <div key={i} style={{ height: '0.6rem' }} />;
    return <p key={i} style={{ margin: '0.1rem 0', color: '#ececec' }}>{renderInline(line)}</p>;
  });
}

function renderInline(text: string): React.ReactNode {
  const parts = text.split(/(\*\*.*?\*\*|\[.*?\]\(.*?\))/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} style={{ color: '#ffffff', fontWeight: 600 }}>{part.slice(2, -2)}</strong>;
    }
    const link = part.match(/^\[(.*?)\]\((.*?)\)$/);
    if (link) {
      return (
        <a key={i} href={link[2]} target="_blank" rel="noopener noreferrer"
          style={{ color: '#60a5fa', textDecoration: 'underline', textUnderlineOffset: '2px' }}>
          {link[1]}
        </a>
      );
    }
    return part;
  });
}

function Heading2({ children }: { children: React.ReactNode }) {
  return (
    <p style={{ fontWeight: 700, marginTop: '1.5rem', marginBottom: '0.375rem', color: '#ffffff', fontSize: '1.05rem' }}>
      {children}
    </p>
  );
}

function Heading3({ children }: { children: React.ReactNode }) {
  return (
    <p style={{ fontWeight: 600, marginTop: '1.25rem', marginBottom: '0.25rem', color: '#ffffff', fontSize: '1rem' }}>
      {children}
    </p>
  );
}

function Heading4({ children }: { children: React.ReactNode }) {
  return (
    <p style={{ fontWeight: 600, marginTop: '1rem', marginBottom: '0.15rem', color: '#e0e0e0', fontSize: '0.95rem' }}>
      {children}
    </p>
  );
}
