export function getGradeColor(grade) {
  const map = {
    A: 'var(--grade-a)', B: 'var(--grade-b)', C: 'var(--grade-c)',
    D: 'var(--grade-d)', E: 'var(--grade-e)', F: 'var(--grade-f)',
  };
  return map[grade?.toUpperCase()] || 'var(--text-secondary)';
}

export function getGradeClass(grade) {
  return `grade-${(grade || 'f').toLowerCase()}`;
}

export function getHiringGradeColor(grade) {
  const map = {
    Strong: 'var(--success)',
    Good: 'var(--info, #3b82f6)',
    Average: 'var(--warning)',
    Weak: 'var(--error)',
  };
  return map[grade] || 'var(--text-secondary)';
}

export function getRecommendationConfig(recommendation) {
  const map = {
    shortlisted: { label: 'Shortlisted', color: 'var(--success)', bg: 'rgba(34,197,94,0.1)', icon: '✓' },
    needs_review: { label: 'Needs Review', color: 'var(--warning)', bg: 'rgba(234,179,8,0.1)', icon: '⚠' },
    rejected: { label: 'Rejected', color: 'var(--error)', bg: 'rgba(239,68,68,0.1)', icon: '✗' },
  };
  return map[recommendation] || map['needs_review'];
}

export function getStatusBadgeClass(status) {
  const map = {
    completed: 'badge-success', running: 'badge-info',
    pending: 'badge-neutral', failed: 'badge-error',
  };
  return map[status] || 'badge-neutral';
}

export function getStatusLabel(status) {
  return status?.charAt(0).toUpperCase() + status?.slice(1) || 'Unknown';
}

export function getSeverityBadgeClass(severity) {
  const map = { ERROR: 'badge-error', WARNING: 'badge-warning', INFO: 'badge-info' };
  return map[severity?.toUpperCase()] || 'badge-neutral';
}

export function formatDate(dateStr) {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleDateString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

export function timeAgo(dateStr) {
  if (!dateStr) return '';
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function truncateUrl(url) {
  try {
    return new URL(url).pathname.slice(1) || url;
  } catch {
    return url;
  }
}

export function parseJsonList(str) {
  try {
    return JSON.parse(str || '[]');
  } catch {
    return [];
  }
}

export function parseLanguages(langStr) {
  return parseJsonList(langStr);
}

export function parseContributors(contribStr) {
  return parseJsonList(contribStr);
}
