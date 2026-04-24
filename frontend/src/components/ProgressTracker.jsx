import { CheckCircle2, Loader2, Circle, AlertTriangle, Zap } from 'lucide-react';

const STAGES = [
  { key: 'initialising',   label: 'Initialising',     desc: 'Setting up the pipeline' },
  { key: 'cloning',        label: 'Cloning Repo',     desc: 'Fetching git history & metadata' },
  { key: 'parsing',        label: 'Parsing Code',     desc: 'AST analysis of source files' },
  { key: 'static_analysis',label: 'Static Analysis',  desc: 'Security & code smell scan' },
  { key: 'llm_analysis',   label: 'AI Evaluation',    desc: '10-parameter hiring assessment' },
  { key: 'scoring',        label: 'Scoring',          desc: 'Computing final scores' },
  { key: 'saving',         label: 'Saving Results',   desc: 'Persisting to database' },
];

export default function ProgressTracker({ currentStage, progress, message, error }) {
  const currentIdx = STAGES.findIndex(s => s.key === currentStage);

  return (
    <div className="card slide-up">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-md)' }}>
        <h3 className="card-title">
          {error ? (
            <><AlertTriangle size={18} style={{ color: 'var(--error)' }} /> Evaluation Failed</>
          ) : progress >= 100 ? (
            <><CheckCircle2 size={18} style={{ color: 'var(--success)' }} /> Complete</>
          ) : (
            <><Loader2 size={18} className="spin" style={{ color: 'var(--accent-primary-light)' }} /> Evaluating…</>
          )}
        </h3>
        <span style={{ fontWeight: 700, fontSize: 'var(--text-sm)', color: 'var(--accent-primary-light)' }}>
          {progress}%
        </span>
      </div>

      {/* Main progress bar */}
      <div className="progress-bar" style={{ height: 8, marginBottom: 'var(--space-lg)' }}>
        <div className="progress-fill" style={{ width: `${progress}%` }} />
      </div>

      {message && (
        <p style={{
          fontSize: 'var(--text-xs)', lineHeight: 1.5,
          color: error ? 'var(--error)' : 'var(--text-secondary)',
          marginBottom: 'var(--space-lg)',
          padding: '8px 12px',
          background: error ? 'var(--error-bg)' : 'var(--bg-elevated)',
          borderRadius: 'var(--radius-md)',
          fontFamily: 'var(--font-mono)',
        }}>
          {message}
        </p>
      )}

      {/* Timeline */}
      <div className="stage-timeline">
        {STAGES.map((stage, i) => {
          let status = 'pending';
          if (i < currentIdx) status = 'complete';
          else if (i === currentIdx) status = error ? 'error' : 'active';

          return (
            <div key={stage.key} className="stage-row">
              <div className={`stage-dot ${status}`}>
                {status === 'complete' && <CheckCircle2 size={14} />}
                {status === 'active'   && <Loader2 size={14} className="spin" />}
                {status === 'error'    && <AlertTriangle size={14} />}
                {status === 'pending'  && <Circle size={14} />}
              </div>
              <div className="stage-info">
                <div className="stage-name" style={{
                  color: status === 'pending' ? 'var(--text-muted)' : 'var(--text-primary)',
                }}>
                  {stage.label}
                </div>
                <div className="stage-desc">{stage.desc}</div>
              </div>
              {status === 'complete' && (
                <span style={{ fontSize: 10, color: 'var(--success)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                  Done
                </span>
              )}
              {status === 'active' && (
                <span style={{ fontSize: 10, color: 'var(--accent-primary-light)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                  Running
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
