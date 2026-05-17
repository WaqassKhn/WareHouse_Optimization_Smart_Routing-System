const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...(options.token ? { Authorization: `Bearer ${options.token}` } : {}),
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Request failed');
  }
  return response.json();
}

export async function loginDemo() {
  const body = new URLSearchParams();
  body.set('username', 'admin@supplychain.ai');
  body.set('password', 'admin123');
  const response = await fetch(`${API_BASE}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  });
  if (!response.ok) throw new Error('Demo login failed');
  return response.json();
}

export function fetchDashboard() {
  return request('/api/analytics/dashboard');
}

export function fetchLayoutWithObstacles(blocked) {
  return request('/api/warehouse/layout', {
    method: 'POST',
    body: JSON.stringify(blocked),
  });
}

export function optimizePicking(payload, token) {
  return request('/api/picking/optimize', {
    method: 'POST',
    token,
    body: JSON.stringify(payload),
  });
}

export function optimizeDelivery(payload, token) {
  return request('/api/delivery/optimize', {
    method: 'POST',
    token,
    body: JSON.stringify(payload),
  });
}

export function optimizeInventory(payload) {
  return request('/api/inventory/optimize', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function uploadInventory(file, token) {
  const form = new FormData();
  form.append('file', file);
  return request('/api/inventory/upload', {
    method: 'POST',
    token,
    body: form,
  });
}

export function fetchOperationalReport(token) {
  return request('/api/reports/operational', { token });
}

