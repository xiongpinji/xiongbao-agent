import { useCallback, useEffect, useRef, useState } from 'react';

import { OctopChatSocket, type IncomingFrame } from '../api/chatSocket';
import { OctopApiError } from '../api/client';
import { ChatComposer } from './ChatComposer';
import { ChatMessageList } from './ChatMessageList';

interface ChatScreenProps {
  baseUrl: string;
  token: string;
  onLogout: () => void;
  onAuthError: (err: OctopApiError) => void;
}

export interface ChatTurn {
  id: string;
  role: 'user' | 'assistant' | 'system';
  text: string;
  streaming?: boolean;
}

const SESSION_KEY = 'xiongbao.pwa.thread';

export function ChatScreen({ baseUrl, token, onLogout, onAuthError }: ChatScreenProps) {
  const [agentId] = useState<string>(() => {
    return new URLSearchParams(window.location.search).get('agent') ?? '';
  });
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [connection, setConnection] = useState<'idle' | 'connecting' | 'open' | 'closed'>(
    'idle',
  );
  const [error, setError] = useState<string | null>(null);
  const socketRef = useRef<OctopChatSocket | null>(null);

  useEffect(() => {
    if (!agentId) {
      setError('未指定 agent。请使用 ?agent=<agent_id> 打开本页');
      return;
    }
    const sock = new OctopChatSocket({
      baseUrl,
      token,
      agentId,
      onOpen: () => setConnection('open'),
      onClose: (code) => {
        setConnection('closed');
        if (code === 4001 || code === 4003) onAuthError(new OctopApiError('auth', code));
      },
      onError: (err: Error) => setError(err.message),
      onFrame: (frame: IncomingFrame) => handleFrame(frame),
    });
    socketRef.current = sock;
    setConnection('connecting');
    sock.open();
    return () => {
      sock.close();
      socketRef.current = null;
    };
  }, [agentId, baseUrl, token, onAuthError]);

  const handleFrame = useCallback((frame: IncomingFrame) => {
    switch (frame.type) {
      case 'chunk':
        setTurns((prev) => appendAssistantText(prev, String(frame.text ?? '')));
        break;
      case 'message':
        setTurns((prev) => [
          ...prev,
          { id: cryptoId(), role: 'assistant', text: String(frame.text ?? '') },
        ]);
        break;
      case 'tool_start':
        setTurns((prev) => [
          ...prev,
          {
            id: cryptoId(),
            role: 'system',
            text: `🔧 调用工具：${frame.tool_hint_text ?? frame.tool}`,
          },
        ]);
        break;
      case 'error':
        setError(String(frame.message ?? '未知错误'));
        break;
      case 'done':
        setTurns((prev) => markStreamingDone(prev));
        break;
      default:
        break;
    }
  }, []);

  const send = (text: string) => {
    if (!socketRef.current) return;
    if (!text.trim()) return;
    setTurns((prev) => [...prev, { id: cryptoId(), role: 'user', text }]);
    try {
      const threadId = localStorage.getItem(SESSION_KEY) ?? undefined;
      socketRef.current.send(text, threadId);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <main className="screen screen-chat">
      <header className="topbar">
        <div className="topbar-title">
          <strong>熊宝 Agent</strong>
          <span className={`status status-${connection}`}>{statusLabel(connection)}</span>
        </div>
        <button onClick={onLogout} className="ghost">
          退出
        </button>
      </header>
      {error ? (
        <p role="alert" className="error-banner">
          {error}
        </p>
      ) : null}
      <ChatMessageList turns={turns} />
      <ChatComposer onSend={send} disabled={connection !== 'open'} />
    </main>
  );
}

function appendAssistantText(prev: ChatTurn[], text: string): ChatTurn[] {
  const last = prev[prev.length - 1];
  if (last && last.role === 'assistant' && last.streaming) {
    const updated = [...prev];
    updated[updated.length - 1] = { ...last, text: last.text + text };
    return updated;
  }
  return [...prev, { id: cryptoId(), role: 'assistant', text, streaming: true }];
}

function markStreamingDone(prev: ChatTurn[]): ChatTurn[] {
  if (prev.length === 0) return prev;
  const last = prev[prev.length - 1];
  if (!last || !last.streaming) return prev;
  const updated = [...prev];
  updated[updated.length - 1] = { ...last, streaming: false };
  return updated;
}

function statusLabel(state: string): string {
  if (state === 'idle') return '未连接';
  if (state === 'connecting') return '连接中';
  if (state === 'open') return '已连接';
  return '已断开';
}

function cryptoId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}
