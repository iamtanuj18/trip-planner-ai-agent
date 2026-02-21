import { useRef, useState, useEffect, useCallback } from 'react';
import type { Message } from './types';
import { ChatInput } from './components/ChatInput';
import { MessageBubble } from './components/MessageBubble';
import { ChevronDown } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL ?? '';

const SESSION_KEY = 'trip_planner_session_id';
const SESSION_MAX_HISTORY = 40;

class RateLimitError extends Error {
  readonly resetsAt: string;
  constructor(message: string, resetsAt: string) {
    super(message);
    this.resetsAt = resetsAt;
  }
}

// On a full page refresh, treat it as a new conversation.
if ((performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming)?.type === 'reload') {
  sessionStorage.removeItem(SESSION_KEY);
}

// sessionStorage is tab-isolated and destroyed when the tab closes,
// so every tab and every fresh page load gets its own conversation.
function getOrCreateSessionId(): string {
  let sid = sessionStorage.getItem(SESSION_KEY);
  if (!sid) {
    sid = crypto.randomUUID();
    sessionStorage.setItem(SESSION_KEY, sid);
  }
  return sid;
}

const SESSION_ID = getOrCreateSessionId();

const STARTER_SUGGESTIONS = [
  '7 days in Japan under A$5,000  culture and food',
  'Best budget beach trip from Australia in winter',
  'Bali vs Thailand  which is better for a week away?',
  '10 days in Europe with A$8,000, where should I go?',
];

interface SuggestionCardProps {
  text: string;
  onClick: () => void;
}

function SuggestionCard({ text, onClick }: SuggestionCardProps) {
  return (
    <button
      onClick={onClick}
      style={{
        textAlign: 'left',
        padding: '1rem',
        borderRadius: '1rem',
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        color: '#b8b8b8',
        fontSize: '0.875rem',
        lineHeight: '1.5',
        cursor: 'pointer',
        transition: 'background 0.15s, color 0.15s',
      }}
      onMouseEnter={e => {
        e.currentTarget.style.background = 'var(--surface-raised)';
        e.currentTarget.style.color = 'var(--foreground)';
      }}
      onMouseLeave={e => {
        e.currentTarget.style.background = 'var(--surface)';
        e.currentTarget.style.color = '#b8b8b8';
      }}
    >
      {text}
    </button>
  );
}

interface FollowUpChipProps {
  text: string;
  disabled: boolean;
  onClick: () => void;
}

function FollowUpChip({ text, disabled, onClick }: FollowUpChipProps) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        padding: '0.4rem 0.875rem',
        borderRadius: '2rem',
        background: 'transparent',
        border: '1px solid #3d3d3d',
        color: '#c0c0c0',
        fontSize: '0.825rem',
        cursor: disabled ? 'default' : 'pointer',
        transition: 'border-color 0.15s, color 0.15s, background 0.15s',
        opacity: disabled ? 0.4 : 1,
      }}
      onMouseEnter={e => {
        if (!disabled) {
          e.currentTarget.style.borderColor = '#666';
          e.currentTarget.style.color = '#ececec';
          e.currentTarget.style.background = '#2f2f2f';
        }
      }}
      onMouseLeave={e => {
        e.currentTarget.style.borderColor = '#3d3d3d';
        e.currentTarget.style.color = '#c0c0c0';
        e.currentTarget.style.background = 'transparent';
      }}
    >
      {text}
    </button>
  );
}

export function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading]   = useState(false);
  const [showScrollBtn, setShowScrollBtn] = useState(false);
  const bottomRef          = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const userScrolledUpRef  = useRef(false);
  const loadingRef         = useRef(false);
  loadingRef.current = loading;

  // During streaming: instantly pin to bottom on every token unless the user scrolled away.
  useEffect(() => {
    if (!loading) return;
    const el = scrollContainerRef.current;
    if (!el || userScrolledUpRef.current) return;
    el.scrollTop = el.scrollHeight;
  }, [messages, loading]);

  // When a response finishes, reset the scroll-up flag and smooth-snap to bottom.
  useEffect(() => {
    if (!loading) {
      userScrolledUpRef.current = false;
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [loading]);

  // Detect intentional scroll-up during streaming; show/hide the scroll-to-bottom button.
  useEffect(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    function onScroll() {
      const dist = el!.scrollHeight - el!.scrollTop - el!.clientHeight;
      if (dist > 80 && loadingRef.current) userScrolledUpRef.current = true;
      if (dist <= 80)                       userScrolledUpRef.current = false;
      setShowScrollBtn(dist > 200);
    }
    el.addEventListener('scroll', onScroll, { passive: true });
    return () => el.removeEventListener('scroll', onScroll);
  }, []);

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  async function sendMessage(text: string) {
    const completedCount = messages.filter(m => !m.loading).length;
    if (!text.trim() || loading || completedCount >= SESSION_MAX_HISTORY) return;

    setMessages(prev => [
      ...prev,
      { role: 'user', content: text },
      { role: 'assistant', content: '', loading: true, reasoning_steps: [] },
    ]);
    setLoading(true);
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 30);

    try {
      const res = await fetch(`${API_BASE}/stream`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ message: text, session_id: SESSION_ID }),
      });

      if (!res.ok || !res.body) {
        const err = await res.json().catch(() => ({}));
        if (res.status === 429 && err.detail && typeof err.detail === 'object') {
          throw new RateLimitError(err.detail.message, err.detail.resets_at);
        }
        throw new Error((err as Record<string, string>).detail ?? 'Something went wrong');
      }

      const reader  = res.body.getReader();
      const decoder = new TextDecoder();
      let   buffer  = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const raw = line.slice(6).trim();
          if (!raw) continue;
          let evt: Record<string, unknown>;
          try { evt = JSON.parse(raw); } catch { continue; }

          if (evt.type === 'token') {
            setMessages(prev => {
              const last = prev[prev.length - 1];
              return [...prev.slice(0, -1), {
                ...last,
                loading: false,
                content: (last.content as string) + (evt.text as string),
              }];
            });
          } else if (evt.type === 'thinking') {
            setMessages(prev => {
              const last = prev[prev.length - 1];
              return [...prev.slice(0, -1), { ...last, thinking: evt.text as string }];
            });
          } else if (evt.type === 'tool_start') {
            setMessages(prev => {
              const last = prev[prev.length - 1];
              return [...prev.slice(0, -1), { ...last, activeTool: evt.tool as string }];
            });
          } else if (evt.type === 'tool_end') {
            setMessages(prev => {
              const last = prev[prev.length - 1];
              const step = { tool: evt.tool as string, input: evt.input as Record<string, unknown>, output: evt.output };
              return [...prev.slice(0, -1), {
                ...last,
                activeTool: undefined,
                reasoning_steps: [...(last.reasoning_steps ?? []), step],
              }];
            });
          } else if (evt.type === 'done') {
            setMessages(prev => {
              const last = prev[prev.length - 1];
              return [...prev.slice(0, -1), {
                ...last,
                content:               evt.clean_response as string,
                follow_up_suggestions: (evt.follow_up_suggestions as string[]) ?? [],
              }];
            });
          } else if (evt.type === 'error') {
            throw new Error(evt.message as string);
          }
        }
      }
    } catch (err) {
      if (err instanceof RateLimitError) {
        setMessages(prev => [...prev.slice(0, -1), {
          role: 'assistant', content: err.message, isError: true, rateLimitReset: err.resetsAt,
        }]);
      } else {
        const message = err instanceof Error ? err.message : 'Something went wrong';
        setMessages(prev => [...prev.slice(0, -1), { role: 'assistant', content: message, isError: true }]);
      }
    } finally {
      setLoading(false);
    }
  }

  const completedCount = messages.filter(m => !m.loading).length;
  const nearLimit      = completedCount >= SESSION_MAX_HISTORY - 4 && completedCount < SESSION_MAX_HISTORY;
  const sessionFull    = completedCount >= SESSION_MAX_HISTORY;

  const isEmpty = messages.length === 0;

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--background)', position: 'relative' }}>

      <div className="flex-1 overflow-y-auto" ref={scrollContainerRef}>
        <div style={{ maxWidth: '48rem', margin: '0 auto', padding: '2rem 1.5rem 1rem' }}>

          {isEmpty && (
            <div className="flex flex-col items-center gap-8 animate-fade-up" style={{ paddingTop: '18vh' }}>
              <div style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                <h2 style={{ fontSize: '2rem', fontWeight: 600, color: 'var(--foreground)' }}>
                  Plan your next trip
                </h2>
                <p style={{ fontSize: '0.95rem', color: '#999', lineHeight: '1.6', maxWidth: '34rem', margin: '0 auto' }}>
                  Powered by a multi-step AI agent that searches a curated knowledge base of 22 destinations,
                  compares costs, and builds a personalised day-by-day itinerary  all in one conversation.
                </p>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', width: '100%' }}>
                {STARTER_SUGGESTIONS.map(s => (
                  <SuggestionCard key={s} text={s} onClick={() => sendMessage(s)} />
                ))}
              </div>
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
            {messages.map((msg, i) => {
              const isLastAssistant = msg.role === 'assistant' && !msg.loading && i === messages.length - 1;
              const isStreaming = loading && msg.role === 'assistant' && !msg.loading && i === messages.length - 1;
              return (
                <div key={i}>
                  <MessageBubble message={msg} isStreaming={isStreaming} />
                  {isLastAssistant && msg.follow_up_suggestions && msg.follow_up_suggestions.length > 0 && (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '1rem' }}>
                      {msg.follow_up_suggestions.map((s, si) => (
                        <FollowUpChip key={si} text={s} disabled={loading} onClick={() => sendMessage(s)} />
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <div ref={bottomRef} />
        </div>
      </div>

      {/* Scroll-to-bottom button — floats above input bar */}
      {showScrollBtn && (
        <button
          onClick={scrollToBottom}
          aria-label="Scroll to bottom"
          style={{
            position: 'absolute',
            bottom: '5.5rem',
            left: '50%',
            transform: 'translateX(-50%)',
            display: 'flex',
            alignItems: 'center',
            gap: '0.375rem',
            padding: '0.4rem 0.875rem',
            borderRadius: '2rem',
            background: 'var(--surface-raised)',
            border: '1px solid var(--border)',
            color: '#c0c0c0',
            fontSize: '0.8rem',
            cursor: 'pointer',
            zIndex: 10,
            boxShadow: '0 2px 8px rgba(0,0,0,0.4)',
            whiteSpace: 'nowrap',
          }}
        >
          <ChevronDown size={14} strokeWidth={2.5} />
          Scroll to bottom
        </button>
      )}

      {/* Input bar */}
      <div style={{ padding: '0.75rem 1.5rem 1.25rem' }}>
        <div style={{ maxWidth: '48rem', margin: '0 auto' }}>
          {sessionFull ? (
            <div style={{
              textAlign: 'center',
              padding: '0.875rem 1rem',
              borderRadius: '1rem',
              background: 'var(--surface)',
              border: '1px solid var(--border)',
              color: '#888',
              fontSize: '0.875rem',
              lineHeight: 1.6,
            }}>
              Conversation limit reached — open a new tab to start fresh.
            </div>
          ) : (
            <>
              {nearLimit && (
                <p style={{ textAlign: 'center', marginBottom: '0.5rem', fontSize: '0.75rem', color: '#aaa' }}>
                  {SESSION_MAX_HISTORY - completedCount} message{SESSION_MAX_HISTORY - completedCount !== 1 ? 's' : ''} remaining in this conversation.
                </p>
              )}
              <ChatInput onSend={sendMessage} disabled={loading} />
            </>
          )}
          <p style={{ textAlign: 'center', marginTop: '0.5rem', fontSize: '0.75rem', color: '#999' }}>
            AI Trip Planner can make mistakes. Costs are estimates in AUD.
          </p>
        </div>
      </div>

    </div>
  );
}
