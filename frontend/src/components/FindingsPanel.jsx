import { Shield, AlertTriangle, Info, XCircle } from 'lucide-react';
import { getSeverityBadgeClass } from '../utils/helpers';
import { useState } from 'react';

export default function FindingsPanel({ findings }) {
  const [filter, setFilter] = useState('all');

  if (!findings?.length) {
    return (
      <div className="card fade-in" id="findings-panel">
        <div className="card-header">
          <h3 className="card-title">
            <Shield size={20} />
            Security & Code Findings
          </h3>
        </div>
        <div className="empty-state" style={{ padding: 'var(--space-xl)' }}>
          <div className="empty-state-icon" style={{ width: 56, height: 56 }}>
            <Shield size={24} />
          </div>
          <h3 style={{ fontSize: 'var(--text-base)' }}>No findings</h3>
          <p style={{ fontSize: 'var(--text-sm)' }}>No security issues or code smells detected.</p>
        </div>
      </div>
    );
  }

  const errors = findings.filter(f => f.severity === 'ERROR').length;
  const warnings = findings.filter(f => f.severity === 'WARNING').length;
  const infos = findings.filter(f => f.severity === 'INFO').length;

  const filtered = filter === 'all' ? findings : findings.filter(f => f.severity === filter);

  return (
    <div className="card fade-in" id="findings-panel">
      <div className="card-header">
        <h3 className="card-title">
          <Shield size={20} />
          Security & Code Findings
        </h3>
        <span className="badge badge-neutral">{findings.length} total</span>
      </div>

      <div style={{ display: 'flex', gap: 'var(--space-sm)', marginBottom: 'var(--space-md)', flexWrap: 'wrap' }}>
        <button
          className={`btn btn-sm ${filter === 'all' ? 'btn-primary' : 'btn-ghost'}`}
          onClick={() => setFilter('all')}
        >
          All ({findings.length})
        </button>
        <button
          className={`btn btn-sm ${filter === 'ERROR' ? 'btn-primary' : 'btn-ghost'}`}
          onClick={() => setFilter('ERROR')}
          style={{ color: filter !== 'ERROR' ? 'var(--error)' : undefined }}
        >
          <XCircle size={14} /> Errors ({errors})
        </button>
        <button
          className={`btn btn-sm ${filter === 'WARNING' ? 'btn-primary' : 'btn-ghost'}`}
          onClick={() => setFilter('WARNING')}
          style={{ color: filter !== 'WARNING' ? 'var(--warning)' : undefined }}
        >
          <AlertTriangle size={14} /> Warnings ({warnings})
        </button>
        <button
          className={`btn btn-sm ${filter === 'INFO' ? 'btn-primary' : 'btn-ghost'}`}
          onClick={() => setFilter('INFO')}
          style={{ color: filter !== 'INFO' ? 'var(--info)' : undefined }}
        >
          <Info size={14} /> Info ({infos})
        </button>
      </div>

      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>Severity</th>
              <th>File</th>
              <th>Rule</th>
              <th>Message</th>
              <th>Line</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((f, i) => (
              <tr key={i}>
                <td>
                  <span className={`badge ${getSeverityBadgeClass(f.severity)}`}>
                    {f.severity}
                  </span>
                </td>
                <td className="td-mono" style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {f.file_path}
                </td>
                <td className="td-mono" style={{ fontSize: 'var(--text-xs)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {f.rule_id}
                </td>
                <td style={{ fontSize: 'var(--text-xs)', maxWidth: 400, color: 'var(--text-secondary)' }}>
                  {f.message}
                </td>
                <td className="td-mono">{f.line_start}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
