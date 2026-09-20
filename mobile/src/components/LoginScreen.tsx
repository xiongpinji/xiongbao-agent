import { useState } from 'react';

import { login, OctopApiError } from '../api/client';

interface LoginScreenProps {
  baseUrl: string;
  initialError: string | null;
  onBaseUrlChange: (value: string) => void;
  onLoggedIn: (token: string) => void;
}

export function LoginScreen({
  baseUrl,
  initialError,
  onBaseUrlChange,
  onLoggedIn,
}: LoginScreenProps) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(initialError);

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const result = await login(baseUrl, { username, password });
      onLoggedIn(result.access_token);
    } catch (err) {
      setError(err instanceof OctopApiError ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="screen screen-login">
      <header className="brand">
        <h1>熊宝 Agent</h1>
        <p className="subtitle">移动端 · 自托管 AI 工作台</p>
      </header>
      <form onSubmit={submit} className="card">
        <label className="field">
          <span>服务地址</span>
          <input
            type="url"
            value={baseUrl}
            placeholder="http://127.0.0.1:8088"
            onChange={(e) => onBaseUrlChange(e.target.value)}
            required
            autoComplete="url"
          />
        </label>
        <label className="field">
          <span>账号</span>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
          />
        </label>
        <label className="field">
          <span>密码</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>
        {error ? <p className="error">{error}</p> : null}
        <button type="submit" className="primary" disabled={submitting || !baseUrl}>
          {submitting ? '登录中…' : '登录'}
        </button>
      </form>
    </main>
  );
}
