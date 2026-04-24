import { CheckCircle2, XCircle, Brain, User, Lightbulb, Sparkles } from 'lucide-react';
import { getRecommendationConfig, getHiringGradeColor, parseJsonList } from '../utils/helpers';

export default function HiringPanel({ data }) {
  const rec        = getRecommendationConfig(data.recommendation);
  const gradeColor = getHiringGradeColor(data.hiring_grade);
  const matched    = parseJsonList(data.matched_requirements);
  const missing    = parseJsonList(data.missing_features);
  const suggestions = parseJsonList(data.improvement_suggestions);

  return (
    <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-lg)' }}>

      {/* Verdict card */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr auto',
        gap: 'var(--space-lg)',
        padding: 'var(--space-xl)',
        background: 'var(--bg-card)',
        border: `1px solid ${rec.color}30`,
        borderRadius: 'var(--radius-xl)',
        position: 'relative',
        overflow: 'hidden',
      }}>
        {/* Background glow */}
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
          background: `radial-gradient(ellipse at 20% 50%, ${rec.color}08 0%, transparent 60%)`,
          pointerEvents: 'none',
        }} />

        <div style={{ position: 'relative' }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6 }}>
            Hiring Recommendation
          </div>
          <div style={{ fontSize: 'var(--text-3xl)', fontWeight: 900, color: rec.color, marginBottom: 8, lineHeight: 1 }}>
            {rec.icon}&nbsp;{rec.label}
          </div>

          {(data.project_title || data.project_description) && (
            <div style={{ marginTop: 'var(--space-md)', paddingTop: 'var(--space-md)', borderTop: `1px solid ${rec.color}20` }}>
              {data.project_title && (
                <div style={{ fontWeight: 700, fontSize: 'var(--text-sm)', marginBottom: 4, color: 'var(--text-primary)' }}>
                  {data.project_title}
                </div>
              )}
              {data.project_description && (
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', maxHeight: 60, overflow: 'hidden', lineHeight: 1.6 }}>
                  {data.project_description}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Grade */}
        <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
          <div style={{
            padding: '20px 28px',
            borderRadius: 'var(--radius-lg)',
            background: gradeColor + '10',
            border: `1px solid ${gradeColor}25`,
            textAlign: 'center',
          }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6 }}>Grade</div>
            <div style={{ fontSize: 'var(--text-4xl)', fontWeight: 900, color: gradeColor, lineHeight: 1 }}>{data.hiring_grade}</div>
          </div>
        </div>
      </div>

      {/* AI Summary */}
      {data.summary_feedback && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title"><Brain size={18} style={{ color: 'var(--accent-primary-light)' }} /> AI Assessment</h3>
          </div>
          <p style={{ color: 'var(--text-secondary)', lineHeight: 1.8, fontSize: 'var(--text-sm)' }}>{data.summary_feedback}</p>
        </div>
      )}

      {/* Matched & Missing requirements */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-md)' }}>

        <div className="card" style={{ borderColor: 'rgba(34,197,94,0.15)' }}>
          <div className="card-header">
            <h3 className="card-title" style={{ color: 'var(--success)', fontSize: 'var(--text-sm)' }}>
              <CheckCircle2 size={16} /> Matched
            </h3>
            <span className="badge badge-success">{matched.length}</span>
          </div>
          {matched.length > 0 ? (
            <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
              {matched.map((req, i) => (
                <li key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                  <CheckCircle2 size={13} style={{ color: 'var(--success)', flexShrink: 0, marginTop: 1 }} />
                  {req}
                </li>
              ))}
            </ul>
          ) : (
            <p style={{ color: 'var(--text-muted)', fontSize: 'var(--text-xs)' }}>No matched requirements detected.</p>
          )}
        </div>

        <div className="card" style={{ borderColor: 'rgba(239,68,68,0.15)' }}>
          <div className="card-header">
            <h3 className="card-title" style={{ color: 'var(--error)', fontSize: 'var(--text-sm)' }}>
              <XCircle size={16} /> Missing
            </h3>
            <span className="badge badge-error">{missing.length}</span>
          </div>
          {missing.length > 0 ? (
            <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
              {missing.map((req, i) => (
                <li key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                  <XCircle size={13} style={{ color: 'var(--error)', flexShrink: 0, marginTop: 1 }} />
                  {req}
                </li>
              ))}
            </ul>
          ) : (
            <p style={{ color: 'var(--text-muted)', fontSize: 'var(--text-xs)' }}>No missing requirements identified.</p>
          )}
        </div>
      </div>

      {/* Interviewer Notes */}
      {data.interviewer_notes && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title" style={{ fontSize: 'var(--text-sm)' }}><User size={16} style={{ color: 'var(--accent-primary-light)' }} /> Interviewer Notes</h3>
          </div>
          <p style={{ whiteSpace: 'pre-wrap', color: 'var(--text-secondary)', fontSize: 'var(--text-sm)', lineHeight: 1.75 }}>
            {data.interviewer_notes}
          </p>
        </div>
      )}

      {/* Improvement Suggestions */}
      {suggestions.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title" style={{ fontSize: 'var(--text-sm)' }}><Lightbulb size={16} style={{ color: 'var(--warning)' }} /> Improvement Suggestions</h3>
          </div>
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
            {suggestions.map((s, i) => (
              <li key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
                <span style={{
                  width: 20, height: 20, borderRadius: '50%', flexShrink: 0,
                  background: 'rgba(245,158,11,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  marginTop: 1,
                }}>
                  <Lightbulb size={11} style={{ color: 'var(--warning)' }} />
                </span>
                {s}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
