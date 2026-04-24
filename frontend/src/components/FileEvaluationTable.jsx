import { useState, useMemo } from 'react';
import { FileCode2, ArrowUpDown, CheckCircle2, AlertCircle } from 'lucide-react';

function ScoreBar({ score }) {
  const color = score >= 70 ? 'var(--success)' : score >= 45 ? 'var(--warning)' : 'var(--error)';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
      <div style={{
        flex: 1, height: 6, borderRadius: 3,
        background: 'var(--border)', overflow: 'hidden',
      }}>
        <div style={{ width: `${Math.min(100, score)}%`, height: '100%', background: color, borderRadius: 3, transition: 'width 0.3s' }} />
      </div>
      <span style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color, minWidth: 28, textAlign: 'right' }}>
        {score?.toFixed(0)}
      </span>
    </div>
  );
}

export default function FileEvaluationTable({ fileEvaluations }) {
  const [expanded, setExpanded] = useState(null);
  const [sortKey, setSortKey] = useState('file_score');
  const [sortAsc, setSortAsc] = useState(false);

  const sorted = useMemo(() => {
    return [...(fileEvaluations || [])].sort((a, b) => {
      const va = typeof a[sortKey] === 'string' ? a[sortKey].localeCompare(b[sortKey]) : (a[sortKey] ?? 0) - (b[sortKey] ?? 0);
      return sortAsc ? (typeof va === 'number' ? va : 0) : (typeof va === 'number' ? -va : 0);
    });
  }, [fileEvaluations, sortKey, sortAsc]);

  const toggleSort = (key) => {
    if (sortKey === key) setSortAsc(!sortAsc);
    else { setSortKey(key); setSortAsc(false); }
  };

  if (!fileEvaluations?.length) {
    return (
      <div className="card fade-in">
        <div className="card-header">
          <h3 className="card-title"><FileCode2 size={20} /> File Evaluations</h3>
        </div>
        <div className="empty-state" style={{ padding: 'var(--space-xl)' }}>
          <h3 style={{ fontSize: 'var(--text-base)' }}>No file evaluations</h3>
          <p style={{ fontSize: 'var(--text-sm)' }}>File-level hiring assessment was not generated.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="card fade-in">
      <div className="card-header">
        <h3 className="card-title"><FileCode2 size={20} /> File Evaluations</h3>
        <span className="badge badge-neutral">{fileEvaluations.length} key files</span>
      </div>

      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>File</th>
              <th>Purpose</th>
              <th>Relevance</th>
              <th onClick={() => toggleSort('file_score')} style={{ cursor: 'pointer', minWidth: 100 }}>
                Score <ArrowUpDown size={12} style={{ opacity: 0.5 }} />
              </th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((fe, i) => (
              <>
                <tr key={fe.file_path} style={{ cursor: 'pointer' }} onClick={() => setExpanded(expanded === i ? null : i)}>
                  <td className="td-mono" style={{ maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {fe.file_path}
                  </td>
                  <td style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', maxWidth: 160 }}>
                    <span className="badge badge-neutral">{fe.purpose}</span>
                  </td>
                  <td style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {fe.relevance_to_task}
                  </td>
                  <td style={{ minWidth: 120 }}>
                    <ScoreBar score={fe.file_score} />
                  </td>
                  <td>
                    <button className="btn btn-ghost btn-sm" style={{ fontSize: 'var(--text-xs)' }}>
                      {expanded === i ? 'Hide' : 'View'}
                    </button>
                  </td>
                </tr>

                {expanded === i && (
                  <tr key={`${fe.file_path}-detail`}>
                    <td colSpan={5} style={{ background: 'var(--surface-alt, rgba(255,255,255,0.03))', padding: 'var(--space-md)' }}>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-md)' }}>
                        {fe.strengths?.length > 0 && (
                          <div>
                            <div style={{ fontWeight: 700, fontSize: 'var(--text-xs)', color: 'var(--success)', marginBottom: 'var(--space-xs)', textTransform: 'uppercase', letterSpacing: 1 }}>
                              Strengths
                            </div>
                            <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 4 }}>
                              {fe.strengths.map((s, si) => (
                                <li key={si} style={{ display: 'flex', gap: 6, alignItems: 'flex-start', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
                                  <CheckCircle2 size={12} style={{ color: 'var(--success)', flexShrink: 0, marginTop: 2 }} />
                                  {s}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {fe.issues?.length > 0 && (
                          <div>
                            <div style={{ fontWeight: 700, fontSize: 'var(--text-xs)', color: 'var(--error)', marginBottom: 'var(--space-xs)', textTransform: 'uppercase', letterSpacing: 1 }}>
                              Issues
                            </div>
                            <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 4 }}>
                              {fe.issues.map((issue, ii) => (
                                <li key={ii} style={{ display: 'flex', gap: 6, alignItems: 'flex-start', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
                                  <AlertCircle size={12} style={{ color: 'var(--error)', flexShrink: 0, marginTop: 2 }} />
                                  {issue}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
