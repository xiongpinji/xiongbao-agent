import { useEffect, useState } from 'react';

import { ChatScreen } from './components/ChatScreen';
import { LoginScreen } from './components/LoginScreen';
import {
  getStoredBaseUrl,
  getStoredToken,
  OctopApiError,
  setStoredBaseUrl,
} from './api/client';

export function App() {
  const [token, setToken] = useState<string | null>(getStoredToken());
  const [baseUrl, setBaseUrl] = useState<string>(getStoredBaseUrl());
  const [bootError, setBootError] = useState<string | null>(null);

  useEffect(() => {
    // After first launch we prefill DEFAULT_BASE_URL (see api/client.ts).
    // Only show a boot error if the user explicitly cleared the field.
    if (!baseUrl) {
      setBootError('请填写 Octop 服务地址');
    } else {
      setBootError(null);
    }
  }, [baseUrl]);

  const onLogin = (newToken: string) => {
    setToken(newToken);
  };

  const onLogout = () => {
    setToken(null);
  };

  if (!token) {
    return (
      <LoginScreen
        baseUrl={baseUrl}
        onBaseUrlChange={(v) => {
          setStoredBaseUrl(v);
          setBaseUrl(v);
        }}
        initialError={bootError}
        onLoggedIn={onLogin}
      />
    );
  }

  return (
    <ChatScreen
      baseUrl={baseUrl}
      token={token}
      onLogout={onLogout}
      onAuthError={(err: OctopApiError) => {
        if (err.status === 401) onLogout();
      }}
    />
  );
}
