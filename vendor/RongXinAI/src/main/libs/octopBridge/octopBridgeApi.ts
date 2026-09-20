/**
 * Thin HTTP helpers used by the Octop bridge IPC handlers.
 *
 * - `loginToOctop(baseUrl, username, password)` — POSTs `/api/auth/login` and
 *   returns the access token. Throws `OctopBridgeError` on non-200 responses.
 * - `listOctopAgents(baseUrl, token)` — GETs `/api/agents` and returns a
 *   minimal `{ id, name }` projection so the settings page can show a picker.
 *
 * Both helpers use the global `fetch`, which is available in the Electron main
 * process via Node 18+. No third-party HTTP client is required.
 */

export class OctopBridgeError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'OctopBridgeError';
    this.status = status;
  }
}

function normalizeBaseUrl(raw: string): string {
  return raw.replace(/\/+$/, '');
}

function readErrorDetail(payload: unknown, fallback: string): string {
  if (payload && typeof payload === 'object') {
    const obj = payload as { message?: unknown; detail?: unknown };
    if (typeof obj.message === 'string' && obj.message.trim()) return obj.message;
    if (typeof obj.detail === 'string' && obj.detail.trim()) return obj.detail;
  }
  return fallback;
}

export interface OctopLoginResult {
  accessToken: string;
  username: string;
  role: string;
}

export async function loginToOctop(
  baseUrl: string,
  username: string,
  password: string,
): Promise<OctopLoginResult> {
  if (!username || !password) {
    throw new OctopBridgeError('用户名和密码不能为空', 0);
  }
  const url = `${normalizeBaseUrl(baseUrl)}/api/auth/login`;
  let res: Response;
  try {
    res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
  } catch (err) {
    throw new OctopBridgeError(
      `无法连接 Octop 后端: ${err instanceof Error ? err.message : String(err)}`,
      0,
    );
  }
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const payload = await res.json();
      detail = readErrorDetail(payload, detail);
    } catch {
      // body wasn't JSON; keep HTTP status fallback
    }
    throw new OctopBridgeError(detail, res.status);
  }
  const data = (await res.json()) as {
    access_token?: unknown;
    user?: { username?: unknown; role?: unknown };
  };
  if (typeof data.access_token !== 'string' || !data.access_token) {
    throw new OctopBridgeError('Octop 响应缺少 access_token', res.status);
  }
  return {
    accessToken: data.access_token,
    username: typeof data.user?.username === 'string' ? data.user.username : username,
    role: typeof data.user?.role === 'string' ? data.user.role : '',
  };
}

export interface OctopAgentSummary {
  id: string;
  name: string;
}

export async function listOctopAgents(
  baseUrl: string,
  token: string,
): Promise<OctopAgentSummary[]> {
  const url = `${normalizeBaseUrl(baseUrl)}/api/agents`;
  let res: Response;
  try {
    res = await fetch(url, {
      method: 'GET',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
  } catch (err) {
    throw new OctopBridgeError(
      `无法连接 Octop 后端: ${err instanceof Error ? err.message : String(err)}`,
      0,
    );
  }
  if (res.status === 401) {
    throw new OctopBridgeError('JWT 已失效，请重新登录', 401);
  }
  if (!res.ok) {
    throw new OctopBridgeError(`拉取 agents 失败: HTTP ${res.status}`, res.status);
  }
  const data = (await res.json()) as unknown;
  if (!Array.isArray(data)) {
    throw new OctopBridgeError('Octop 响应不是数组', res.status);
  }
  return data
    .map(item => {
      if (!item || typeof item !== 'object') return null;
      const obj = item as { agent_id?: unknown; id?: unknown; name?: unknown };
      const id =
        typeof obj.agent_id === 'string'
          ? obj.agent_id
          : typeof obj.id === 'string'
            ? obj.id
            : null;
      const name = typeof obj.name === 'string' ? obj.name : '';
      if (!id) return null;
      return { id, name };
    })
    .filter((item): item is OctopAgentSummary => item !== null);
}
