import { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  ArrowLeft, GitCommit, Users, Calendar, FileCode2,
  Shield, BarChart3, Briefcase, Target, GitBranch, Clock,
} from 'lucide-react';
import { getEvaluation, streamEvaluation } from '../utils/api';
import {
  getGradeClass, parseLanguages, parseContributors, formatDate,
  getStatusBadgeClass, getStatusLabel, getRecommendationConfig, getHiringGradeColor,
} from '../utils/helpers';
import ScoreGauge from '../components/ScoreGauge';
import ProgressTracker from '../components/ProgressTracker';
import FileScoresTable from '../components/FileScoresTable';
import FileEvaluationTable from '../components/FileEvaluationTable';
import FindingsPanel from '../components/FindingsPanel';
import HiringPanel from '../components/HiringPanel';
import ParameterScoresPanel from '../components/ParameterScoresPanel';

const TABS = [
  { key: 'hiring',     label: 'Hiring Report',  icon: <Briefcase size={13} /> },
  { key: 'parameters', label: 'Parameters',      icon: <Target size={13} />,    badge: '10' },
  { key: 'files',      label: 'File Analysis',   icon: <FileCode2 size={13} /> },
  { key: 'metrics',    label: 'Code Metrics',    icon: <BarChart3 size={13} /> },
  { key: 'security',   label: 'Security',        icon: <Shield size={13} />,    countKey: 'total_findings' },
];

export default function EvaluationDetail() {
  const { id } = useParams();
  const [data,        setData]        = useState(null);
  const [loading,     setLoading]     = useState(true);
  const [activeTab,   setActiveTab]   = useState('hiring');
  const [progress,    setProgress]    = useState({ stage: '', progress: 0, message: '' });
  const [isStreaming, setIsStreaming]  = useState(false);
  const esRef = useRef(null);

  useEffect(() => {
    loadEvaluation();
    return () => esRef.current?.close();
  }, [id]);

  async function loadEvaluation() {
    try {
      const result = await getEvaluation(id);
      setData(result);
      if (result.status === 'running' || result.status === 'pending') startStreaming();
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  function startStreaming() {
    setIsStreaming(true);
    esRef.current = streamEvaluation(id, update => {
      setProgress(update);
      if (update.done) {
        setIsStreaming(false);
        setTimeout(async () => { try { setData(await getEvaluation(id)); } catch {} }, 1000);
      }
    });
  }

  /* ---- Loading skeleton ---- */
  if (loading) {
    return (
      <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div className="skeleton" style={{ height: 220, borderRadius: 'var(--radius-xl)' }} />
        <div className="skeleton" style={{ height: 46, width: 480, borderRadius: 'var(--radius-full)' }} />
        <div className="skeleton" style={{ height: 320, borderRadius: 'var(--radius-xl)' }} />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="empty-state">
        <h3>Evaluation not found</h3>
        <Link to="/" className="btn btn-primary" style={{ marginTop: 16 }}>
          <ArrowLeft size={15} /> Back to Dashboard
        </Link>
      </div>
    );
  }

  const languages    = parseLanguages(data.languages);
  const contributors = parseContributors(data.contributors);
  const isComplete   = data.status === 'completed';
  const isRunning    = data.status === 'running' || data.status === 'pending';
  const isFailed     = data.status === 'failed';
  const rec          = getRecommendationConfig(data.recommendation);
  const gradeColor   = getHiringGradeColor(data.hiring_grade);

  const statsStrip = [
    { label: 'Files',        value: data.total_files,                  color: '#3b82f6' },
    { label: 'Security',     value: data.total_findings,               color: data.total_findings > 0 ? '#ef4444' : '#22c55e' },
    { label: 'Commits',      value: data.total_commits,                color: '#93c5fd' },
    { label: 'Contributors', value: contributors.length,               color: '#f43f5e' },
    { label: 'Repo age',     value: `${data.repo_age_days}d`,          color: '#f59e0b' },
    { label: 'Languages',    value: languages.length,                  color: '#06b6d4' },
  ];

  return (
    <div className="fade-in">

      {/* Back */}
      <div style={{ marginBottom: 20 }}>
        <Link to="/" className="btn btn-ghost btn-sm" style={{ paddingLeft: 0, color: 'var(--text-tertiary)' }}>
          <ArrowLeft size={14} /> Back
        </Link>
      </div>

      {/* ─── Hero banner ─── */}
      <div style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-xl)',
        marginBottom: 20,
        overflow: 'hidden',
        backgroundImage: `
          radial-gradient(ellipse 60% 80% at 90% 50%, ${isComplete ? gradeColor : 'var(--violet)'}0a 0%, transparent 60%),
          var(--gradient-card)
        `,
      }}>
        {/* Colour top bar */}
        <div style={{
          height: 3,
          background: isComplete
            ? `linear-gradient(90deg, ${gradeColor}, ${rec.color})`
            : 'var(--gradient-brand)',
        }} />

        {/* Main content row */}
        <div style={{ display: 'flex', gap: 28, padding: '24px 28px 20px', flexWrap: 'wrap', alignItems: 'flex-start' }}>

          {/* Title + meta */}
          <div style={{ flex: 1, minWidth: 220 }}>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center', marginBottom: 10 }}>
              <span className={`badge ${getStatusBadgeClass(data.status)}`}>{getStatusLabel(data.status)}</span>
              {data.head_commit && (
                <span className="badge badge-neutral" style={{ fontFamily: 'var(--font-mono)' }}>
                  <GitCommit size={9} /> {data.head_commit.slice(0, 7)}
                </span>
              )}
              {data.default_branch && (
                <span className="badge badge-neutral">
                  <GitBranch size={9} /> {data.default_branch}
                </span>
              )}
            </div>

            <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 900, letterSpacing: '-0.5px', marginBottom: 6, lineHeight: 1.2 }}>
              {data.project_title || 'Hiring Evaluation'}
            </h1>

            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--text-muted)', marginBottom: 14, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 480 }}>
              {data.repo_url}
            </div>

            {languages.length > 0 && (
              <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                {languages.map(l => <span key={l} className="badge badge-neutral">{l}</span>)}
              </div>
            )}
          </div>

          {/* Score gauge */}
          {isComplete && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, flexShrink: 0 }}>
              <ScoreGauge score={data.overall_score} grade={data.overall_grade} size={130} strokeWidth={9} />
              <span style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.8 }}>Total Score</span>
            </div>
          )}

          {/* Hiring grade + recommendation */}
          {isComplete && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, flexShrink: 0, alignSelf: 'center' }}>
              {/* Grade box */}
              <div style={{
                padding: '16px 22px', borderRadius: 'var(--radius-lg)',
                background: gradeColor + '10',
                border: `1px solid ${gradeColor}22`,
                textAlign: 'center', minWidth: 100,
              }}>
                <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 4 }}>Hiring Grade</div>
                <div style={{ fontSize: 'var(--text-4xl)', fontWeight: 900, color: gradeColor, lineHeight: 1 }}>{data.hiring_grade}</div>
              </div>

              {/* Verdict pill */}
              <div style={{
                padding: '7px 14px', borderRadius: 'var(--radius-full)',
                background: rec.bg, color: rec.color,
                fontWeight: 700, fontSize: 'var(--text-sm)',
                border: `1px solid ${rec.color}30`,
                textAlign: 'center',
              }}>
                {rec.icon}&nbsp;{rec.label}
              </div>
            </div>
          )}
        </div>

        {/* Stats strip */}
        {isComplete && (
          <div
            className="stats-strip"
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(6, 1fr)',
              borderTop: '1px solid var(--border-subtle)',
            }}
          >
            {statsStrip.map((s, i) => (
              <div key={i} style={{
                padding: '12px 16px', textAlign: 'center',
                borderRight: i < statsStrip.length - 1 ? '1px solid var(--border-subtle)' : 'none',
              }}>
                <div style={{ fontSize: 'var(--text-xl)', fontWeight: 900, color: s.color, lineHeight: 1 }}>{s.value}</div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 3, textTransform: 'uppercase', letterSpacing: 0.5 }}>{s.label}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ─── Progress tracker ─── */}
      {(isRunning || (isStreaming && !isComplete)) && (
        <div style={{ marginBottom: 20 }}>
          <ProgressTracker
            currentStage={progress.stage || data.current_stage}
            progress={progress.progress || data.progress}
            message={progress.message}
            error={progress.error}
          />
        </div>
      )}

      {/* ─── Error state ─── */}
      {isFailed && (
        <div className="card" style={{ borderColor: 'rgba(239,68,68,0.2)', background: 'rgba(239,68,68,0.03)', marginBottom: 20 }}>
          <div style={{ fontWeight: 700, color: 'var(--error)', marginBottom: 8, fontSize: 'var(--text-base)' }}>Evaluation Failed</div>
          <p style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            {data.error_message}
          </p>
        </div>
      )}

      {/* ─── Tabs + content ─── */}
      {isComplete && (
        <>
          <div className="tabs-pill">
            {TABS.map(tab => {
              const count = tab.badge ?? (tab.countKey ? data[tab.countKey] : null);
              return (
                <button
                  key={tab.key}
                  className={`tab-pill ${activeTab === tab.key ? 'active' : ''}`}
                  onClick={() => setActiveTab(tab.key)}
                >
                  {tab.icon}
                  {tab.label}
                  {count != null && (
                    <span style={{
                      fontSize: 10, fontWeight: 700, lineHeight: '16px',
                      padding: '0 5px', borderRadius: 'var(--radius-full)',
                      background: activeTab === tab.key ? 'rgba(59,130,246,0.2)' : 'rgba(255,255,255,0.05)',
                      color: activeTab === tab.key ? 'var(--violet-light)' : 'var(--text-muted)',
                    }}>
                      {count}
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          {activeTab === 'hiring'     && <HiringPanel data={data} />}
          {activeTab === 'parameters' && <ParameterScoresPanel parameterScores={data.parameter_scores || []} overallScore={data.overall_score} />}
          {activeTab === 'files'      && <FileEvaluationTable fileEvaluations={data.file_evaluations || []} />}
          {activeTab === 'metrics'    && <FileScoresTable fileScores={data.file_scores || []} />}
          {activeTab === 'security'   && <FindingsPanel findings={data.findings || []} />}
        </>
      )}
    </div>
  );
}
