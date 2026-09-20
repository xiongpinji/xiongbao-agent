// Vanilla Node WS smoke (no TS, no bundler) — exercises the same wire protocol
// as OctopChatClient. Run:
//   cd vendor/RongXinAI && node scripts/octop-chat-smoke.cjs <agent_id> [prompt]
const WebSocket = require('ws');

async function main() {
  const agentId = process.argv[2];
  if (!agentId) {
    console.error('usage: node scripts/octop-chat-smoke.cjs <agent_id> [prompt]');
    process.exit(2);
  }
  const prompt = process.argv[3] ?? '用一句话介绍你自己';

  const baseUrl = 'http://127.0.0.1:8088';
  const loginRes = await fetch(`${baseUrl}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'admin', password: 'TestPass123!' }),
  });
  if (!loginRes.ok) {
    console.error('login failed:', loginRes.status, await loginRes.text());
    process.exit(1);
  }
  const body = await loginRes.json();
  console.log('[ok] login, JWT len=', body.access_token.length);

  const wsUrl = `ws://127.0.0.1:8088/api/agents/${agentId}/chat/ws?token=${encodeURIComponent(body.access_token)}`;
  const ws = new WebSocket(wsUrl);
  let text = '';
  let exitCode = 2;

  ws.on('open', () => {
    console.log('[ws] open, sending user_turn');
    ws.send(JSON.stringify({ type: 'user_turn', text: prompt }));
  });

  ws.on('message', (data) => {
    const raw = data.toString('utf8');
    let frame;
    try {
      frame = JSON.parse(raw);
    } catch {
      frame = { type: 'text', text: raw };
    }
    if (frame.type === 'chunk') {
      const delta = frame.delta ?? frame.content ?? frame.text ?? '';
      text += delta;
    } else if (frame.type === 'done') {
      console.log('[reply]', JSON.stringify(text));
      exitCode = 0;
      ws.close();
    } else if (frame.type === 'error') {
      console.error('[server-error]', frame.message ?? JSON.stringify(frame));
      exitCode = 2;
      ws.close();
    } else {
      console.log('[frame]', frame.type ?? '?', JSON.stringify(frame).slice(0, 200));
    }
  });

  ws.on('close', (code, reason) => {
    console.log('[ws] close', code, reason.toString());
    process.exit(exitCode);
  });

  ws.on('error', (err) => {
    console.error('[ws-error]', err.message);
    process.exit(2);
  });

  setTimeout(() => {
    console.error('[timeout] no done frame within 45s');
    process.exit(3);
  }, 45_000);
}

main().catch((err) => {
  console.error('[fatal]', err);
  process.exit(2);
});
