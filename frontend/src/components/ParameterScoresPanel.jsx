import { useState } from 'react';
import { Target, ChevronDown, ChevronUp, FileCode2, Lightbulb } from 'lucide-react';

const PARAM_COLORS = {
  relevancy:      { color: '#6366f1', bg: 'rgba(99,102,241,0.1)' },
  accuracy:       { color: '#3b82f6', bg: 'rgba(59,130,246,0.1)' },
  completeness:   { color: '#0ea5e9', bg: 'rgba(14,165,233,0.1)' },
  code_quality:   { color: '#10b981', bg: 'rgba(16,185,129,0.1)' },
  architecture:   { color: '#14b8a6', bg: 'rgba(20,184,166,0.1)' },
  performance:    { color: '#f59e0b', bg: 'rgba(245,158,11,0.1)' },
  security:       { color: '#ef4444', bg: 'rgba(239,68,68,0.1)' },
  error_handling: { color: '#f97316', bg: 'rgba(249,115,22,0.1)' },
  database:       { color: '#8b5cf6', bg: 'rgba(139,92,246,0.1)' },
  documentation:  { color: '#ec4899', bg: 'rgba(236,72,153,0.1)' },
};

function ScoreRing({ score, maxScore, color }) {
  const pct  = Math.min(1, score / maxScore);
  const size = 64;
  const sw   = 6;
  const r    = (size - sw) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ * (1 - pct);

  return (
    <div style={{ position: 'relative', width: size, height: size, flexShrink: 0 }}>
      <svg width={size} height={size}>
        <circle cx={size/2} cy={size/2} r={r} strokeWidth={sw}
          fill="none" stroke="var(--border)" />
        <circle cx={size/2} cy={size/2} r={r} strokeWidth={sw}
          fill="none" stroke={color}
          strokeDasharray={circ} strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transform: 'rotate(-90deg)', transformOrigin: '50% 50%',
                   filter: `drop-shadow(0 0 4px ${color}60)` }} />
      </svg>
      <div style={{
        position: 'absolute', inset: 0,
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        fontSize: 13, fontWeight: 800, lineHeight: 1.1,
      }}>
        <span style={{ color }}>{score % 1 === 0 ? score : score.toFixed(1)}</span>
        <span style={{ fontSize: 9, color: 'var(--text-muted)' }}>/{maxScore}</span>
      </div>
    </div>
  );
}

function ProgressBar({ score, maxScore, color }) {
  const pct = Math.min(100, (score / maxScore) * 100);
  return (
    <div style={{ height: 6, borderRadius: 3, background: 'var(--border)', overflow: 'hidden', flex: 1 }}>
      <div style={{
        width: `${pct}%`, height: '100%', borderRadius: 3,
        background: color, transition: 'width 0.4s ease',
        boxShadow: `0 0 6px ${color}60`,
      }} />
    </div>
  );
}

function ParameterCard({ ps }) {
  const [expanded, setExpanded] = useState(false);
  const theme = PARAM_COLORS[ps.key] || { color: 'var(--accent-primary-light)', bg: 'rgba(99,102,241,0.1)' };
  const pct   = Math.round((ps.score / ps.max_score) * 100);
  const statusLabel = pct >= 70 ? 'Good' : pct >= 40 ? 'Fair' : 'Weak';
  const statusColor = pct >= 70 ? 'var(--success)' : pct >= 40 ? 'var(--warning)' : 'var(--error)';

  return (
    <div className="card" style={{ padding: 0, overflow: 'hidden', border: `1px solid ${theme.color}25` }}>
      {/* Header row */}
      <div
        style={{
          display: 'flex', alignItems: 'center', gap: 'var(--space-md)',
          padding: 'var(--space-md) var(--space-lg)',
          background: theme.bg, cursor: 'pointer',
        }}
        onClick={() => setExpanded(!expanded)}
      >
        <ScoreRing score={ps.score} maxScore={ps.max_score} color={theme.color} />

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', marginBottom: 6 }}>
            <span style={{ fontWeight: 700, fontSize: 'var(--text-sm)', color: 'var(--text-primary)' }}>
              {ps.name}
            </span>
            <span style={{
              fontSize: 10, fontWeight: 700, padding: '2px 6px',
              borderRadius: 999, background: statusColor + '20', color: statusColor,
            }}>
              {statusLabel}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
            <ProgressBar score={ps.score} maxScore={ps.max_score} color={theme.color} />
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', minWidth: 28, textAlign: 'right' }}>
              {pct}%
            </span>
          </div>
          {ps.reason && (
            <p style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', marginTop: 4, lineHeight: 1.5,
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: expanded ? 'normal' : 'nowrap' }}>
              {ps.reason}
            </p>
          )}
        </div>

        <div style={{ color: 'var(--text-muted)', flexShrink: 0 }}>
          {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </div>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div style={{ padding: 'var(--space-md) var(--space-lg)', display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
          {ps.evidence?.length > 0 && (
            <div>
              <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--text-tertiary)',
                textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6 }}>
                Evidence
              </div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {ps.evidence.map((e, i) => (
                  <span key={i} style={{
                    fontSize: 11, fontFamily: 'var(--font-mono)',
                    padding: '2px 8px', borderRadius: 4,
                    background: theme.bg, color: theme.color,
                    border: `1px solid ${theme.color}30`,
                  }}>
                    <FileCode2 size={10} style={{ marginRight: 4, verticalAlign: 'middle' }} />
                    {e}
                  </span>
                ))}
              </div>
            </div>
          )}

          {ps.suggestions?.length > 0 && (
            <div>
              <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--text-tertiary)',
                textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6 }}>
                Suggestions
              </div>
              <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 4 }}>
                {ps.suggestions.map((s, i) => (
                  <li key={i} style={{ display: 'flex', gap: 6, alignItems: 'flex-start',
                    fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
                    <Lightbulb size={12} style={{ color: 'var(--warning)', flexShrink: 0, marginTop: 2 }} />
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function ParameterScoresPanel({ parameterScores }) {
  if (!parameterScores?.length) {
    return (
      <div className="card fade-in">
        <div className="card-header">
          <h3 className="card-title"><Target size={20} /> Parameter Scores</h3>
        </div>
        <div className="empty-state" style={{ padding: 'var(--space-xl)' }}>
          <h3 style={{ fontSize: 'var(--text-base)' }}>No parameter scores</h3>
          <p style={{ fontSize: 'var(--text-sm)' }}>LLM stage did not run or produced no parameter scores.</p>
        </div>
      </div>
    );
  }

  const totalScore  = parameterScores.reduce((s, p) => s + p.score, 0);
  const totalMax    = parameterScores.reduce((s, p) => s + p.max_score, 0);

  return (
    <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>

      {/* Summary bar */}
      <div className="card" style={{ padding: 'var(--space-lg)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-md)' }}>
          <h3 className="card-title" style={{ margin: 0 }}><Target size={20} /> Parameter Breakdown</h3>
          <div style={{ textAlign: 'right' }}>
            <span style={{ fontSize: 'var(--text-2xl)', fontWeight: 800, color: 'var(--accent-primary-light)' }}>
              {totalScore.toFixed(1)}
            </span>
            <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>/{totalMax}</span>
          </div>
        </div>

        {/* Stacked bar */}
        <div style={{ display: 'flex', height: 12, borderRadius: 6, overflow: 'hidden', gap: 2 }}>
          {parameterScores.map(ps => {
            const theme = PARAM_COLORS[ps.key] || { color: 'var(--accent-primary-light)' };
            const widthPct = (ps.score / totalMax) * 100;
            return (
              <div key={ps.key} title={`${ps.name}: ${ps.score}/${ps.max_score}`}
                style={{ width: `${widthPct}%`, background: theme.color, minWidth: widthPct > 0 ? 3 : 0 }} />
            );
          })}
        </div>

        {/* Legend */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-sm)', marginTop: 'var(--space-md)' }}>
          {parameterScores.map(ps => {
            const theme = PARAM_COLORS[ps.key] || { color: 'var(--accent-primary-light)' };
            const pct = Math.round((ps.score / ps.max_score) * 100);
            return (
              <div key={ps.key} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11 }}>
                <div style={{ width: 8, height: 8, borderRadius: 2, background: theme.color, flexShrink: 0 }} />
                <span style={{ color: 'var(--text-secondary)' }}>{ps.name}</span>
                <span style={{ fontWeight: 700, color: theme.color }}>{pct}%</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Individual parameter cards */}
      {parameterScores.map(ps => <ParameterCard key={ps.key} ps={ps} />)}
    </div>
  );
}
