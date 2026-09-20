import { useEffect, useRef } from 'react';

import type { ChatTurn } from './ChatScreen';

interface ChatMessageListProps {
  turns: ChatTurn[];
}

export function ChatMessageList({ turns }: ChatMessageListProps) {
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [turns]);

  return (
    <div ref={ref} className="message-list" aria-live="polite">
      {turns.length === 0 ? (
        <p className="empty">开始一个对话吧 👋</p>
      ) : (
        turns.map((turn) => (
          <div key={turn.id} className={`bubble bubble-${turn.role}`}>
            <span className="bubble-role">{turn.role === 'user' ? '我' : turn.role === 'assistant' ? '熊宝' : '系统'}</span>
            <p>{turn.text || (turn.streaming ? '…' : '')}</p>
          </div>
        ))
      )}
    </div>
  );
}
