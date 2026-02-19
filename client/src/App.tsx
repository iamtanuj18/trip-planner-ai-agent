import { useRef, useState, useEffect } from 'react';
import type { Message } from './types';
import { ChatInput } from './components/ChatInput';
import { MessageBubble } from './components/MessageBubble';

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

function getOrCreateSessionId(): string {
  let sid = localStorage.getItem(SESSION_KEY);
  if (!sid) {
    sid = crypto.randomUUID();
    localStorage.setItem(SESSION_KEY, sid);
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

//  API call 

interface PlanResult {
  content:              string;
  reasoning_steps:      unknown[];
  thinking?:            string;
  follow_up_suggestions: string[];
}

async function fetchPlan(message: string, history: { role: string; content: string }[]): Promise<PlanResult> {
  const res = await fetch(`${API_BASE}/plan`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ message, session_id: SESSION_ID, history }),
  });

  if (!res.ok) {
    const err = await res.json();
    if (res.status === 429 && err.detail && typeof err.detail === 'object') {
      throw new RateLimitError(err.detail.message, err.detail.resets_at);
    }
    throw new Error(err.detail ?? 'Something went wrong');
  }

  const data = await res.json();

  const thinkingMatch = (data.response as string).match(/<thinking>([\s\S]*?)<\/thinking>/i);
  const thinking      = thinkingMatch ? thinkingMatch[1].trim() : undefined;
  const content       = (data.response as string).replace(/<thinking>[\s\S]*?<\/thinking>/gi, '').trim();

  return {
    content,
    thinking,
    reasoning_steps:       data.reasoning_steps,
    follow_up_suggestions: data.follow_up_suggestions ?? [],
  };
}

export function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading]   = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function sendMessage(text: string) {
    if (!text.trim() || loading) return;

    const history = messages.slice(-SESSION_MAX_HISTORY).map(m => ({ role: m.role, content: m.content }));

    setMessages(prev => [...prev, { role: 'user', content: text }, { role: 'assistant', content: '', loading: true }]);
    setLoading(true);

    try {
      const result = await fetchPlan(text, history);
      setMessages(prev => [
        ...prev.slice(0, -1),
        {
          role:                  'assistant',
          content:               result.content,
          reasoning_steps:       result.reasoning_steps as Message['reasoning_steps'],
          thinking:              result.thinking,
          follow_up_suggestions: result.follow_up_suggestions,
        },
      ]);
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

  const isEmpty = messages.length === 0;

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--background)' }}>

      <div className="flex-1 overflow-y-auto">
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
              return (
                <div key={i}>
                  <MessageBubble message={msg} />
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

      {/* Input bar */}
      <div style={{ padding: '0.75rem 1.5rem 1.25rem' }}>
        <div style={{ maxWidth: '48rem', margin: '0 auto' }}>
          <ChatInput onSend={sendMessage} disabled={loading} />
          <p style={{ textAlign: 'center', marginTop: '0.5rem', fontSize: '0.75rem', color: '#999' }}>
            AI Trip Planner can make mistakes. Costs are estimates in AUD.
          </p>
        </div>
      </div>

    </div>
  );
}
