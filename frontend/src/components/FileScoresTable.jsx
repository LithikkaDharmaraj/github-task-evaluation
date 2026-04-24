import { getGradeClass } from '../utils/helpers';
import { FileCode2, ArrowUpDown } from 'lucide-react';
import { useState, useMemo } from 'react';

export default function FileScoresTable({ fileScores }) {
  const [sortKey, setSortKey] = useState('mi_score');
  const [sortAsc, setSortAsc] = useState(false);

  const sorted = useMemo(() => {
    return [...fileScores].sort((a, b) => {
      const va = a[sortKey] ?? 0;
      const vb = b[sortKey] ?? 0;
      return sortAsc ? va - vb : vb - va;
    });
  }, [fileScores, sortKey, sortAsc]);

  const toggleSort = (key) => {
    if (sortKey === key) setSortAsc(!sortAsc);
    else { setSortKey(key); setSortAsc(false); }
  };

  if (!fileScores?.length) return null;

  return (
    <div className="card fade-in" id="file-scores-table">
      <div className="card-header">
        <h3 className="card-title">
          <FileCode2 size={20} />
          File Quality Scores
        </h3>
        <span className="badge badge-neutral">{fileScores.length} files</span>
      </div>

      <div style={{
        display: 'flex', flexWrap: 'wrap', gap: '6px 20px',
        padding: '10px 20px', borderBottom: '1px solid var(--border)',
        background: 'rgba(255,255,255,0.02)',
      }}>
        {[
          ['MI Score', 'Maintainability Index (0–100)'],
          ['MI Grade', 'A = excellent → F = unmaintainable'],
          ['Avg CC', 'Avg Cyclomatic Complexity per function'],
          ['Max CC', 'Max Cyclomatic Complexity (worst function)'],
          ['LOC', 'Lines of Code (incl. blanks & comments)'],
          ['Issues', 'Semgrep security & code smell findings'],
        ].map(([abbr, full]) => (
          <span key={abbr} style={{ fontSize: 11, color: 'var(--text-tertiary)', whiteSpace: 'nowrap' }}>
            <span style={{ fontWeight: 700, color: 'var(--text-secondary)' }}>{abbr}</span>
            {' — '}{full}
          </span>
        ))}
      </div>

      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>File</th>
              <th>Language</th>
              <th onClick={() => toggleSort('mi_score')} style={{ cursor: 'pointer' }}>
                <span title="Maintainability Index — 0 to 100, higher is better">MI Score</span> <ArrowUpDown size={12} style={{ opacity: 0.5 }} />
              </th>
              <th title="Maintainability Index Grade — A (80–100) to F (0–19)">MI Grade</th>
              <th onClick={() => toggleSort('cc_avg')} style={{ cursor: 'pointer' }}>
                <span title="Average Cyclomatic Complexity — number of independent code paths per function">Avg CC</span> <ArrowUpDown size={12} style={{ opacity: 0.5 }} />
              </th>
              <th title="Maximum Cyclomatic Complexity — worst single function in the file">Max CC</th>
              <th onClick={() => toggleSort('loc')} style={{ cursor: 'pointer' }}>
                <span title="Lines of Code — total lines including blanks and comments">LOC</span> <ArrowUpDown size={12} style={{ opacity: 0.5 }} />
              </th>
              <th title="Static Analysis Issues — security vulnerabilities and code smells flagged by Semgrep">Issues</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((fs, i) => (
              <tr key={i}>
                <td className="td-mono" style={{ maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {fs.file_path}
                </td>
                <td>
                  <span className="badge badge-neutral">{fs.language}</span>
                </td>
                <td>
                  <span style={{
                    fontWeight: 700,
                    color: fs.mi_score >= 60 ? 'var(--success)' : fs.mi_score >= 40 ? 'var(--warning)' : 'var(--error)',
                  }}>
                    {fs.mi_score?.toFixed(1)}
                  </span>
                </td>
                <td>
                  <span className={`grade-badge ${getGradeClass(fs.mi_grade)}`} style={{ width: 32, height: 32, fontSize: 'var(--text-sm)' }}>
                    {fs.mi_grade}
                  </span>
                </td>
                <td style={{
                  color: fs.cc_avg <= 5 ? 'var(--success)' : fs.cc_avg <= 10 ? 'var(--warning)' : 'var(--error)',
                  fontWeight: 600,
                }}>
                  {fs.cc_avg?.toFixed(1)}
                </td>
                <td style={{
                  color: fs.cc_max <= 10 ? 'var(--success)' : fs.cc_max <= 20 ? 'var(--warning)' : 'var(--error)',
                  fontWeight: 600,
                }}>
                  {fs.cc_max}
                </td>
                <td className="td-mono">{fs.loc}</td>
                <td>
                  {fs.security_findings > 0 ? (
                    <span className="badge badge-error">{fs.security_findings}</span>
                  ) : (
                    <span className="badge badge-success">0</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
