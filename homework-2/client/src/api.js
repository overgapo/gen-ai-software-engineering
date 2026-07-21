async function request(url, options) {
  let res;
  try {
    res = await fetch(url, options);
  } catch {
    // network-level failure — fetch gives an unhelpful "Failed to fetch"
    throw new Error('Cannot reach the server. Is the API running on this address?');
  }
  if (res.status === 204) return null;
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const error = new Error(body.error || `Request failed with status ${res.status}`);
    error.body = body;
    throw error;
  }
  return body;
}

const json = (method, payload) => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload),
});

export const api = {
  list(filters = {}) {
    const params = new URLSearchParams(
      Object.entries(filters).filter(([, v]) => v !== '' && v !== undefined)
    );
    const qs = params.toString();
    return request(`/tickets${qs ? `?${qs}` : ''}`);
  },
  get: (id) => request(`/tickets/${id}`),
  create: (payload, autoClassify) =>
    request(`/tickets${autoClassify ? '?auto_classify=true' : ''}`, json('POST', payload)),
  update: (id, payload) => request(`/tickets/${id}`, json('PUT', payload)),
  remove: (id) => request(`/tickets/${id}`, { method: 'DELETE' }),
  classify: (id) => request(`/tickets/${id}/auto-classify`, { method: 'POST' }),
  import(file, autoClassify) {
    const form = new FormData();
    form.append('file', file);
    return request(`/tickets/import${autoClassify ? '?auto_classify=true' : ''}`, {
      method: 'POST',
      body: form,
    });
  },
};
