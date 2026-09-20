/**
 * Octop REST client for the mobile PWA.
 *
 * Talks to the Octop backend over HTTPS. Auth tokens are stored in
 * localStorage. Network errors surface as OctopApiError so the UI can
 * distinguish transport failure from auth failure.
 */

const STORAGE_KEY_TOKEN = 'xiongbao.pwa.token';
const STORAGE_KEY_BASE_URL = 'xiongbao.pwa.baseUrl';

/**
 * Default Octop base URL applied on first launch. Override by typing a different
 * address in the login screen — the value is persisted to localStorage.
 */
export const DEFAULT_BASE_URL = 'http://127.0.0.1:8088';

export class OctopApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'OctopApiError';
    this.status = status;
  }
}

export function getStoredToken(): string | null {
  return localStorage.getItem(STORAGE_KEY_TOKEN);
}

export function getStoredBaseUrl(): string {
  return localStorage.getItem(STORAGE_KEY_BASE_URL) ?? DEFAULT_BASE_URL;
}

export function setStoredBaseUrl(url: string): void {
  localStorage.setItem(STORAGE_KEY_BASE_URL, url);
}

export function setStoredToken(token: string | null): void {
  if (token) localStorage.setItem(STORAGE_KEY_TOKEN, token);
  else localStorage.removeItem(STORAGE_KEY_TOKEN);
}

function normalizeBaseUrl(raw: string): string {
  if (!raw) {
    throw new OctopApiError('请先设置 Octop 服务地址', 0);
  }
  return raw.replace(/\/+$/, '');
}

interface RequestOptions {
  token?: string;
  method?: string;
  body?: unknown;
}

async function request(
  baseUrl: string,
  path: string,
  { token, method = 'GET', body }: RequestOptions = {},
): Promise<unknown> {
  const url = `${normalizeBaseUrl(baseUrl)}${path}`;
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  let res: Response;
  try {
    res = await fetch(url, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (err) {
    throw new OctopApiError(err instanceof Error ? err.message : '网络错误', 0);
  }
  if (res.status === 401) {
    setStoredToken(null);
    throw new OctopApiError('登录已过期，请重新登录', 401);
  }
  if (!res.ok) {
    let detail = '';
    try {
      const j = (await res.json()) as { message?: string; detail?: unknown };
      detail = j?.message ?? (typeof j?.detail === 'string' ? j.detail : JSON.stringify(j));
    } catch {
      detail = await res.text().catch(() => '');
    }
    throw new OctopApiError(detail || `HTTP ${res.status}`, res.status);
  }
  if (res.status === 204) return null;
  return res.json();
}

export interface LoginResult {
  access_token: string;
}

export async function login(
  baseUrl: string,
  { username, password }: { username: string; password: string },
): Promise<LoginResult> {
  const url = `${normalizeBaseUrl(baseUrl)}/api/auth/login`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    let detail = '';
    try {
      const j = (await res.json()) as { message?: string; detail?: unknown };
      detail = j?.message ?? (typeof j?.detail === 'string' ? j.detail : JSON.stringify(j));
    } catch {
      detail = `HTTP ${res.status}`;
    }
    throw new OctopApiError(detail || '登录失败', res.status);
  }
  const data = (await res.json()) as LoginResult;
  setStoredToken(data.access_token);
  return data;
}

export function listAgents(baseUrl: string, token: string): Promise<unknown> {
  return request(baseUrl, '/api/agents', { token });
}

export function getAgent(baseUrl: string, token: string, agentId: string): Promise<unknown> {
  return request(baseUrl, `/api/agents/${encodeURIComponent(agentId)}`, { token });
}
