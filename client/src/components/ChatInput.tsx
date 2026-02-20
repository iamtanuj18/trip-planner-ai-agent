import { useRef, useState, type KeyboardEvent } from 'react';
import { Send } from 'lucide-react';

interface ChatInputProps {
  onSend: (text: string) => void;
  disabled: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [value, setValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function handleSend() {
    const text = value.trim();
    if (!text || disabled) return;
    onSend(text);
    setValue('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleInput() {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }

  const canSend = value.trim().length > 0 && !disabled;

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-end',
        gap: '0.5rem',
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: '1rem',
        padding: '0.625rem 0.625rem 0.625rem 1.125rem',
        transition: 'border-color 0.15s',
      }}
      onFocusCapture={e => (e.currentTarget.style.borderColor = '#676767')}
      onBlurCapture={e => (e.currentTarget.style.borderColor = 'var(--border)')}
    >
      <textarea
        ref={textareaRef}
        value={value}
        onChange={e => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        onInput={handleInput}
        placeholder="Ask anything"
        rows={1}
        style={{
          flex: 1,
          resize: 'none',
          background: 'transparent',
          outline: 'none',
          color: 'var(--foreground)',
          caretColor: 'var(--foreground)',
          fontSize: '1rem',
          lineHeight: '1.6',
          maxHeight: '200px',
          fontFamily: 'inherit',
        }}
      />
      <button
        onClick={handleSend}
        disabled={!canSend}
        aria-label="Send message"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: '2rem',
          height: '2rem',
          borderRadius: '0.5rem',
          flexShrink: 0,
          background: canSend ? 'var(--send-btn-active)' : 'var(--send-btn)',
          color: '#212121',
          cursor: canSend ? 'pointer' : 'default',
          transition: 'background 0.15s',
          border: 'none',
        }}
      >
        <Send size={14} strokeWidth={2.5} />
      </button>
    </div>
  );
}
