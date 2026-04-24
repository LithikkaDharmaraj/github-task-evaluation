import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  GitBranch, ArrowRight, Briefcase, Brain, Shield, BarChart3,
  Clock, Trash2, FileText, Zap, Target, ChevronRight,
  Search, Code2, CheckCircle2, Sparkles,
} from 'lucide-react';
import { submitEvaluation, listEvaluations, deleteEvaluation } from '../utils/api';
import {
  getStatusBadgeClass, getStatusLabel, timeAgo, truncateUrl,
  getRecommendationConfig, getHiringGradeColor,
} from '../utils/helpers';

const PIPELINE_STEPS = [
  { icon: <GitBranch size={15} />, color: '#3b82f6', title: 'Clone Repository', desc: 'Full git history, metadata & file structure extracted' },
  { icon: <Code2 size={15} />,     color: '#93c5fd', title: 'Parse & Analyse',  desc: 'AST parsing, cyclomatic complexity & maintainability index' },
  { icon: <Shield size={15} />,    color: '#22c55e', title: 'Security Scan',    desc: 'Semgrep + Bandit finds security issues & code smells' },
  { icon: <Brain size={15} />,     color: '#f43f5e', title: 'AI Evaluation',    desc: 'Local LLM scores 10 hiring parameters against your task brief' },
  { icon: <Target size={15} />,    color: '#f59e0b', title: 'Hiring Verdict',   desc: 'Strong / Good / Average / Weak with Shortlisted recommendation' },
];

export default function Dashboard() {
  const [repoUrl,             setRepoUrl]             = useState('');
  const [projectTitle,        setProjectTitle]         = useState('');
  const [projectDescription,  setProjectDescription]   = useState('');
  const [loading,             setLoading]              = useState(false);
  const [evaluations,         setEvaluations]          = useState([]);
  const [loadingList,         setLoadingList]          = useState(true);
  const navigate = useNavigate();
  const inputRef = useRef(null);

  useEffect(() => {
    loadEvaluations();
    setTimeout(() => inputRef.current?.focus(), 100);
  }, []);

  async function loadEvaluations() {
    try {
      const data = await listEvaluations(6);
      setEvaluations(data.evaluations || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingList(false);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!repoUrl.trim() || !projectTitle.trim() || !projectDescription.trim() || loading) return;
    setLoading(true);
    try {
      const result = await submitEvaluation(repoUrl.trim(), projectTitle.trim(), projectDescription.trim());
      navigate(`/eval/${result.id}`);
    } catch (err) {
      alert('Failed to start evaluation: ' + err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(id, e) {
    e.stopPropagation();
    e.preventDefault();
    if (!confirm('Delete this evaluation?')) return;
    try {
      await deleteEvaluation(id);
      setEvaluations(prev => prev.filter(ev => ev.id !== id));
    } catch (err) {
      alert('Failed to delete: ' + err.message);
    }
  }

  const canSubmit = repoUrl.trim() && projectTitle.trim() && projectDescription.trim() && !loading;

  return (
    <div className="fade-in">
      <div
        className="dashboard-grid"
        style={{ display: 'grid', gridTemplateColumns: '1fr 368px', gap: 28, alignItems: 'start' }}
      >

        {/* ── LEFT COLUMN ── */}
        <div>
          {/* Hero */}
          <div style={{ paddingTop: 40, paddingBottom: 32 }}>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: 7,
              padding: '4px 12px', borderRadius: 'var(--radius-full)',
              background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.22)',
              fontSize: 11, fontWeight: 700, color: 'var(--violet-light)',
              letterSpacing: 0.3, marginBottom: 20,
            }}>
              <Sparkles size={11} />  AI-powered hiring evaluation
            </div>

            <h1 style={{
              fontSize: 'var(--text-5xl)', fontWeight: 900,
              letterSpacing: '-2.5px', lineHeight: 1.06, marginBottom: 18,
            }}>
              Evaluate<br />
              <span className="gradient-text">candidate repos</span><br />
              in minutes.
            </h1>

            <p style={{ fontSize: 'var(--text-base)', color: 'var(--text-secondary)', maxWidth: 440, lineHeight: 1.75 }}>
              Paste any GitHub URL and your task brief — the pipeline clones,
              analyses, and returns a hiring verdict with a full 10-parameter
              score breakdown.
            </p>
          </div>

          {/* Form card */}
          <div style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-xl)',
            padding: '28px 28px 24px',
            position: 'relative',
            overflow: 'hidden',
            boxShadow: '0 4px 40px rgba(0,0,0,0.4)',
          }}>
            {/* Top gradient stripe */}
            <div style={{
              position: 'absolute', top: 0, left: 0, right: 0, height: 2,
              background: 'var(--gradient-brand)',
            }} />

            <div style={{ marginBottom: 22 }}>
              <div style={{ fontWeight: 800, fontSize: 'var(--text-md)', marginBottom: 3 }}>
                New Evaluation
              </div>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)' }}>
                Runs the full 5-stage pipeline and generates a hiring verdict
              </div>
            </div>

            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>

              <div className="form-field">
                <label className="form-label">
                  <GitBranch size={11} /> Repository URL
                </label>
                <input
                  ref={inputRef}
                  type="text"
                  className="input"
                  placeholder="https://github.com/candidate/project"
                  value={repoUrl}
                  onChange={e => setRepoUrl(e.target.value)}
                  disabled={loading}
                  style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-sm)' }}
                />
              </div>

              <div className="form-field">
                <label className="form-label">
                  <Briefcase size={11} /> Project Title
                </label>
                <input
                  type="text"
                  className="input"
                  placeholder="e.g. Full-stack Task Manager with Auth"
                  value={projectTitle}
                  onChange={e => setProjectTitle(e.target.value)}
                  disabled={loading}
                />
              </div>

              <div className="form-field">
                <label className="form-label">
                  <FileText size={11} /> Task Requirements
                </label>
                <textarea
                  className="input"
                  style={{ minHeight: 110, resize: 'vertical', lineHeight: 1.7, fontFamily: 'inherit', fontSize: 'var(--text-sm)' }}
                  placeholder="Describe the expected features, tech stack, and requirements. The AI will score the submission against these criteria…"
                  value={projectDescription}
                  onChange={e => setProjectDescription(e.target.value)}
                  disabled={loading}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: 4 }}>
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                  Takes 2–5 min depending on repo size
                </span>
                <button type="submit" className="btn btn-primary btn-lg" disabled={!canSubmit}>
                  {loading ? (
                    <>
                      <span className="spin" style={{ width: 14, height: 14, border: '2px solid rgba(255,255,255,0.25)', borderTopColor: 'white', borderRadius: '50%', display: 'inline-block' }} />
                      Starting…
                    </>
                  ) : (
                    <>Start Evaluation <ArrowRight size={15} /></>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>

        {/* ── RIGHT SIDEBAR ── */}
        <div className="sidebar-col" style={{ position: 'sticky', top: 76, display: 'flex', flexDirection: 'column', gap: 16, paddingTop: 40 }}>

          {/* Pipeline card */}
          <div style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-xl)',
            padding: '20px 20px 16px',
            overflow: 'hidden',
            position: 'relative',
          }}>
            <div style={{
              position: 'absolute', top: 0, left: 0, right: 0, height: 2,
              background: 'linear-gradient(90deg, #3b82f6, #06b6d4)',
            }} />

            <div style={{ fontWeight: 800, fontSize: 'var(--text-base)', marginBottom: 18, display: 'flex', alignItems: 'center', gap: 8 }}>
              <Zap size={15} style={{ color: 'var(--violet-light)' }} />
              How it works
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
              {PIPELINE_STEPS.map((step, i) => (
                <div key={i} style={{ display: 'flex', gap: 12, paddingBottom: i < PIPELINE_STEPS.length - 1 ? 16 : 0, position: 'relative' }}>
                  {/* Connector line */}
                  {i < PIPELINE_STEPS.length - 1 && (
                    <div style={{ position: 'absolute', left: 15, top: 32, width: 2, height: 'calc(100% - 16px)', background: 'var(--border)', borderRadius: 1 }} />
                  )}

                  {/* Step icon bubble */}
                  <div style={{
                    width: 32, height: 32, borderRadius: '50%', flexShrink: 0,
                    background: step.color + '14', border: `1px solid ${step.color}28`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: step.color, zIndex: 1,
                  }}>
                    {step.icon}
                  </div>

                  <div style={{ paddingTop: 4 }}>
                    <div style={{ fontWeight: 700, fontSize: 'var(--text-sm)', marginBottom: 2 }}>{step.title}</div>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', lineHeight: 1.5 }}>{step.desc}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Recent evaluations card */}
          <div style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-xl)',
            overflow: 'hidden',
          }}>
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '16px 20px 12px',
              borderBottom: evaluations.length > 0 ? '1px solid var(--border)' : 'none',
            }}>
              <div style={{ fontWeight: 800, fontSize: 'var(--text-base)', display: 'flex', alignItems: 'center', gap: 8 }}>
                <BarChart3 size={15} style={{ color: 'var(--violet-light)' }} />
                Recent
              </div>
              {evaluations.length > 0 && (
                <a href="/history" style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', display: 'flex', alignItems: 'center', gap: 3 }}>
                  View all <ChevronRight size={12} />
                </a>
              )}
            </div>

            {loadingList ? (
              <div style={{ padding: '12px 20px', display: 'flex', flexDirection: 'column', gap: 10 }}>
                {[1,2,3].map(i => (
                  <div key={i}>
                    <div className="skeleton" style={{ height: 13, width: '65%', marginBottom: 7 }} />
                    <div className="skeleton" style={{ height: 10, width: '40%' }} />
                  </div>
                ))}
              </div>
            ) : evaluations.length === 0 ? (
              <div style={{ padding: '24px 20px', textAlign: 'center' }}>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>No evaluations yet</div>
              </div>
            ) : (
              <div>
                {evaluations.map((ev, idx) => {
                  const rec        = getRecommendationConfig(ev.recommendation);
                  const gradeColor = getHiringGradeColor(ev.hiring_grade);
                  return (
                    <div
                      key={ev.id}
                      onClick={() => navigate(`/eval/${ev.id}`)}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 10,
                        padding: '11px 20px',
                        borderBottom: idx < evaluations.length - 1 ? '1px solid var(--border-subtle)' : 'none',
                        cursor: 'pointer',
                        transition: 'background var(--transition-fast)',
                      }}
                      onMouseEnter={e => e.currentTarget.style.background = 'rgba(59,130,246,0.04)'}
                      onMouseLeave={e => e.currentTarget.style.background = ''}
                    >
                      <span className={`status-dot ${ev.status}`} />

                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontWeight: 600, fontSize: 'var(--text-xs)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginBottom: 2 }}>
                          {ev.project_title || truncateUrl(ev.repo_url)}
                        </div>
                        <div style={{ fontSize: 10, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
                          <Clock size={9} /> {timeAgo(ev.created_at)}
                          &nbsp;·&nbsp;
                          <span className={`badge ${getStatusBadgeClass(ev.status)}`} style={{ fontSize: 9, padding: '1px 6px' }}>
                            {getStatusLabel(ev.status)}
                          </span>
                        </div>
                      </div>

                      {ev.status === 'completed' && (
                        <div style={{ textAlign: 'right', flexShrink: 0 }}>
                          <div style={{ fontSize: 'var(--text-sm)', fontWeight: 800, color: gradeColor, lineHeight: 1 }}>{ev.hiring_grade}</div>
                          <div style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 1 }}>{ev.overall_score?.toFixed(0)}/100</div>
                        </div>
                      )}

                      <button
                        className="btn btn-ghost btn-sm"
                        onClick={e => handleDelete(ev.id, e)}
                        style={{ color: 'var(--text-muted)', padding: '3px 5px', flexShrink: 0 }}
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

        </div>
      </div>
    </div>
  );
}
