// Smoke test using the production OctopChatClient. Bypasses Electron, just exercises
// the wire protocol + handles errors. Run with:
//   cd vendor/RongXinAI && npx tsx scripts/octop-chat-smoke.ts <agent_id> [prompt]
import WebSocket from 'ws';
import { OctopChatClient } from '../src/main/libs/octopBridge/OctopChatClient';

async function main() {
  const agentId = process.argv[2];
  if (!agentId) {
    console.error('usage: tsx scripts/octop-chat-smoke.ts <agent_id> [prompt]');
    process.exit(2);
  }
  const prompt = process.argv[3] ?? '用一句话介绍你自己';

  const baseUrl = 'http://127.0.0.1:8088';
  const username = 'admin';
  const password = 'TestPass123!';

  const loginRes = await fetch(`${baseUrl}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!loginRes.ok) {
    console.error('login failed:', loginRes.status, await loginRes.text());
    process.exit(1);
  }
  const loginBody = (await loginRes.json()) as { access_token: string };
  console.log('[ok] login, JWT len=', loginBody.access_token.length);

  const client = new OctopChatClient({
    baseUrl,
    bearer: loginBody.access_token,
    WebSocketCtor: WebSocket as unknown as typeof WebSocket,
  });

  try {
    const result = await client.sendTurn({ agentId, text: prompt });
    console.log('[reply]', JSON.stringify(result.text));
    process.exit(0);
  } catch (err) {
    console.error('[err]', err instanceof Error ? err.message : String(err));
    process.exit(2);
  }
}

main();
