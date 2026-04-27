const API_BASE = '/api';

export async function submitEvaluation(repoUrl, projectTitle, projectDescription, stages = '1,2,3,7,8', model = null) {
  const res = await fetch(`${API_BASE}/evaluate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      repo_url: repoUrl,
      project_title: projectTitle,
      project_description: projectDescription,
      stages,
      model,
      use_4bit: true,
    }),
  });
  if (!res.ok) throw new Error(`Submit failed: ${res.status}`);
  return res.json();
}

export async function getEvaluation(id) {
  const res = await fetch(`${API_BASE}/evaluate/${id}`);
  if (!res.ok) throw new Error(`Fetch failed: ${res.status}`);
  return res.json();
}

export async function listEvaluations(limit = 20, offset = 0, search = '') {
  const params = new URLSearchParams({ limit, offset });
  if (search) params.set('search', search);
  const res = await fetch(`${API_BASE}/evaluations?${params}`);
  if (!res.ok) throw new Error(`List failed: ${res.status}`);
  return res.json();
}

export async function deleteEvaluation(id) {
  const res = await fetch(`${API_BASE}/evaluations/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(`Delete failed: ${res.status}`);
}

export function streamEvaluation(id, onProgress) {
  const source = new EventSource(`${API_BASE}/evaluate/${id}/stream`);

  source.addEventListener('progress', (event) => {
    const data = JSON.parse(event.data);
    onProgress(data);
    if (data.done) source.close();
  });

  source.addEventListener('error', () => {
    source.close();
    onProgress({ stage: 'error', progress: 0, message: 'Connection lost', done: true, error: true });
  });

  return source;
}

export function getHealthStatus() {
  return fetch(`${API_BASE}/health`).then(r => r.json());
}
