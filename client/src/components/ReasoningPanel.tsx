import { useState, type ReactNode } from 'react';
import { ChevronDown } from 'lucide-react';
import type { ReasoningStep } from '../types';

interface ReasoningPanelProps {
  steps: ReasoningStep[];
  thinking?: string;
}

export function ReasoningPanel({ steps, thinking }: ReasoningPanelProps) {
  const [open, setOpen] = useState(false);

  const hasTools = steps.length > 0;
  const label = [
    thinking ? 'reasoning' : '',
    hasTools  ? `${steps.length} tool call${steps.length !== 1 ? 's' : ''}` : '',
  ].filter(Boolean).join(' · ');

  return (
    <div
      style={{
        borderRadius: '0.625rem',
        background: '#292929',
        border: '1px solid #3a3a3a',
      }}
    >
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0.625rem 1rem',
          background: 'none',
          color: '#c8c8c8',
          cursor: 'pointer',
          border: 'none',
          borderRadius: open ? '0.625rem 0.625rem 0 0' : '0.625rem',
          fontFamily: 'inherit',
          fontSize: '0.825rem',
          gap: '0.5rem',
        }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.6, flexShrink: 0 }}>
            <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
          </svg>
          <span style={{ fontWeight: 500 }}>{label}</span>
        </span>
        <ChevronDown
          size={13}
          strokeWidth={2}
          style={{
            transition: 'transform 0.2s',
            transform: open ? 'rotate(180deg)' : 'rotate(0deg)',
            flexShrink: 0,
            opacity: 0.5,
          }}
        />
      </button>

      {open && (
        <div style={{ borderTop: '1px solid #3a3a3a', borderRadius: '0 0 0.625rem 0.625rem', overflow: 'visible' }} className="animate-slide-down">

          {thinking && (
            <div style={{ padding: '0.875rem 1rem', borderBottom: hasTools ? '1px solid #3a3a3a' : 'none' }}>
              <SectionLabel>Model Reasoning</SectionLabel>
              <p style={{
                fontSize: '0.825rem',
                color: '#c0c0c0',
                lineHeight: 1.75,
                fontStyle: 'italic',
                margin: 0,
                whiteSpace: 'pre-wrap',
              }}>
                {thinking}
              </p>
            </div>
          )}

          {hasTools && steps.map((step, i) => (
            <StepRow key={i} step={step} index={i} last={i === steps.length - 1} />
          ))}
        </div>
      )}
    </div>
  );
}

function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <p style={{ fontSize: '0.7rem', color: '#aaa', marginBottom: '0.4rem', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 500 }}>
      {children}
    </p>
  );
}
interface StepRowProps {
  step: ReasoningStep;
  index: number;
  last: boolean;
}

function StepRow({ step, index, last }: StepRowProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div style={{ background: '#292929', borderBottom: last ? 'none' : '1px solid #3a3a3a' }}>
      <button
        onClick={() => setExpanded(o => !o)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          gap: '0.75rem',
          padding: '0.55rem 1rem',
          cursor: 'pointer',
          background: 'none',
          border: 'none',
          fontFamily: 'inherit',
          fontSize: '0.825rem',
          color: '#bbb',
          textAlign: 'left',
        }}
      >
        <span style={{ flexShrink: 0, fontSize: '0.72rem', color: '#aaa', minWidth: '1rem', textAlign: 'right' }}>
          {index + 1}
        </span>
        <code style={{ fontFamily: 'ui-monospace, monospace', fontSize: '0.825rem', color: '#d4d4d4', flex: 1, letterSpacing: '-0.01em' }}>
          {step.tool}
        </code>
        <ChevronDown
          size={12}
          strokeWidth={2}
          style={{ flexShrink: 0, transition: 'transform 0.15s', transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)', opacity: 0.45 }}
        />
      </button>

      {expanded && (
        <div style={{ padding: '0 1rem 0.875rem', display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
          {[
            { label: 'Input', value: JSON.stringify(step.input, null, 2) },
            { label: 'Output', value: typeof step.output === 'string' ? step.output : JSON.stringify(step.output, null, 2) },
          ].map(({ label, value }) => (
            <div key={label}>
              <SectionLabel>{label}</SectionLabel>
              <pre
                style={{
                  background: '#1a1a1a',
                  border: '1px solid #3a3a3a',
                  borderRadius: '0.5rem',
                  padding: '0.625rem 0.875rem',
                  fontSize: '0.78rem',
                  color: '#d4d4d4',
                  overflowX: 'auto',
                  overflowY: 'auto',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  lineHeight: 1.6,
                  fontFamily: 'ui-monospace, monospace',
                  margin: 0,
                  maxHeight: '220px',
                }}
              >
                {value}
              </pre>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
