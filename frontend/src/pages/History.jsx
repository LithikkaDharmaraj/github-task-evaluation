import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { History as HistoryIcon, Trash2, Clock, Search, ChevronLeft, ChevronRight } from 'lucide-react';
import { listEvaluations, deleteEvaluation } from '../utils/api';
import { getStatusBadgeClass, getStatusLabel, formatDate, truncateUrl, getRecommendationConfig, getHiringGradeColor } from '../utils/helpers';

export default function History() {
  const [evaluations, setEvaluations] = useState([]);
  const [loading, setLoading]         = useState(true);
  const [total, setTotal]             = useState(0);
  const [offset, setOffset]           = useState(0);
  const [search, setSearch]           = useState('');
  const limit      = 20;
  const navigate   = useNavigate();
  const debounceRef = useRef(null);

  useEffect(() => { loadEvaluations(search, offset); }, [offset]);

  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setOffset(0);
      loadEvaluations(search, 0);
    }, 300);
    return () => clearTimeout(debounceRef.current);
  }, [search]);

  async function loadEvaluations(searchTerm, currentOffset) {
    setLoading(true);
    try {
      const data = await listEvaluations(limit, currentOffset, searchTerm);
      setEvaluations(data.evaluations || []);
      setTotal(data.total || 0);
    } catch (err) {
      console.error('Failed to load evaluations:', err);
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(id, e) {
    e.stopPropagation();
    if (!confirm('Delete this evaluation?')) return;
    try {
      await deleteEvaluation(id);
      setEvaluations(prev => prev.filter(ev => ev.id !== id));
      setTotal(prev => prev - 1);
    } catch (err) {
      alert('Failed to delete: ' + err.message);
    }
  }

  return (
    <div className="fade-in">

      {/* Header */}
      <div className="section-header" style={{ marginBottom: 'var(--space-xl)' }}>
        <div>
          <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 800, letterSpacing: '-0.5px', display: 'flex', alignItems: 'center', gap: 10 }}>
            <HistoryIcon size={22} style={{ color: 'var(--accent-primary-light)' }} />
            Evaluation History
          </h1>
          <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-tertiary)', marginTop: 4 }}>
            {total} evaluation{total !== 1 ? 's' : ''} total
          </p>
        </div>
      </div>

      {/* Search */}
      <div className="input-group" style={{ marginBottom: 'var(--space-lg)', maxWidth: 480 }}>
        <span className="input-icon"><Search size={15} /></span>
        <input
          type="text"
          className="input input-with-icon"
          placeholder="Filter by project or repository URL…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>

      {/* List */}
      {loading ? (
        <div className="stagger" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
          {[1,2,3,4,5].map(i => (
            <div key={i} style={{ padding: 'var(--space-md) var(--space-lg)', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)' }}>
              <div className="skeleton" style={{ height: 16, width: '48%', marginBottom: 10 }} />
              <div className="skeleton" style={{ height: 12, width: '24%' }} />
            </div>
          ))}
        </div>
      ) : evaluations.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon"><HistoryIcon size={28} /></div>
          <h3>No evaluations found</h3>
          <p>{search ? 'No results match your filter.' : 'Start by evaluating a repository from the dashboard.'}</p>
        </div>
      ) : (
        <>
          {/* Table card */}
          <div className="card" style={{ padding: 0, marginBottom: 'var(--space-xl)' }}>
            <div className="table-container" style={{ border: 'none', borderRadius: 0 }}>
              <table>
                <thead>
                  <tr>
                    <th>Project / Repository</th>
                    <th>Status</th>
                    <th>Score</th>
                    <th>Hiring Grade</th>
                    <th>Verdict</th>
                    <th>Files</th>
                    <th>Date</th>
                    <th style={{ width: 40 }}></th>
                  </tr>
                </thead>
                <tbody>
                  {evaluations.map(ev => {
                    const rec        = getRecommendationConfig(ev.recommendation);
                    const gradeColor = getHiringGradeColor(ev.hiring_grade);
                    return (
                      <tr key={ev.id} style={{ cursor: 'pointer' }} onClick={() => navigate(`/eval/${ev.id}`)}>
                        <td style={{ maxWidth: 280 }}>
                          <div style={{ fontWeight: 600, fontSize: 'var(--text-sm)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {ev.project_title || truncateUrl(ev.repo_url)}
                          </div>
                          <div className="td-mono" style={{ marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 260 }}>
                            {truncateUrl(ev.repo_url)}
                          </div>
                        </td>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <span className={`status-dot ${ev.status}`} />
                            <span className={`badge ${getStatusBadgeClass(ev.status)}`}>{getStatusLabel(ev.status)}</span>
                          </div>
                        </td>
                        <td>
                          <span style={{ fontWeight: 700, fontSize: 'var(--text-sm)' }}>
                            {ev.status === 'completed' ? `${ev.overall_score?.toFixed(1)}/100` : '—'}
                          </span>
                        </td>
                        <td>
                          {ev.status === 'completed' ? (
                            <span style={{ fontWeight: 800, color: gradeColor, fontSize: 'var(--text-base)' }}>
                              {ev.hiring_grade}
                            </span>
                          ) : '—'}
                        </td>
                        <td>
                          {ev.status === 'completed' ? (
                            <span style={{
                              padding: '3px 10px', borderRadius: 'var(--radius-full)',
                              background: rec.bg, color: rec.color,
                              fontSize: 11, fontWeight: 700,
                              border: `1px solid ${rec.color}30`,
                              whiteSpace: 'nowrap',
                            }}>
                              {rec.label}
                            </span>
                          ) : '—'}
                        </td>
                        <td style={{ color: 'var(--text-secondary)', fontSize: 'var(--text-sm)' }}>
                          {ev.total_files || '—'}
                        </td>
                        <td style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', whiteSpace: 'nowrap' }}>
                          {formatDate(ev.created_at)}
                        </td>
                        <td>
                          <button
                            className="btn btn-ghost btn-sm"
                            onClick={e => handleDelete(ev.id, e)}
                            style={{ color: 'var(--text-muted)', padding: '4px 6px' }}
                          >
                            <Trash2 size={13} />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Pagination */}
          {total > limit && (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 'var(--space-sm)' }}>
              <button
                className="btn btn-secondary btn-sm"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - limit))}
              >
                <ChevronLeft size={14} /> Previous
              </button>
              <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', padding: '0 var(--space-sm)' }}>
                {offset + 1}–{Math.min(offset + limit, total)} of {total}
              </span>
              <button
                className="btn btn-secondary btn-sm"
                disabled={offset + limit >= total}
                onClick={() => setOffset(offset + limit)}
              >
                Next <ChevronRight size={14} />
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
