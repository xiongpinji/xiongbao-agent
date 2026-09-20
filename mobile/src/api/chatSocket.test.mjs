/**
 * Self-contained Node test for OctopChatSocket.
 *
 * Uses node:test (built-in, Node 18+). Avoids pulling in a vitest dep just
 * for one file. Run with `npm test` (which calls node --test with the
 * --experimental-transform-types flag so the .ts source is consumed
 * directly).
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { OctopChatSocket } from './chatSocket.ts';

class FakeWebSocket {
  static instances = [];
  url;
  readyState = 0;
  sent = [];
  listeners = {};
  constructor(url) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }
  addEventListener(name, cb) {
    (this.listeners[name] ??= []).push(cb);
  }
  send(data) {
    this.sent.push(data);
  }
  close() {
    this.readyState = 3;
    this.emit('close', { code: 1000, reason: '' });
  }
  emit(name, payload) {
    for (const cb of this.listeners[name] ?? []) cb(payload);
  }
  open() {
    this.readyState = 1;
    this.emit('open', {});
  }
  message(payload) {
    this.emit('message', { data: payload });
  }
}

test('builds the correct URL with token', () => {
  FakeWebSocket.instances = [];
  const sock = new OctopChatSocket({
    baseUrl: 'https://octop.example.com',
    token: 'abc',
    agentId: 'a1',
    WebSocketCtor: FakeWebSocket,
  });
  sock.open();
  assert.equal(
    FakeWebSocket.instances[0].url,
    'wss://octop.example.com/api/agents/a1/chat/ws?token=abc',
  );
  sock.close();
});

test('sends user_turn frames with the right shape', () => {
  FakeWebSocket.instances = [];
  const sock = new OctopChatSocket({
    baseUrl: 'https://octop.example.com',
    token: 't',
    agentId: 'a1',
    WebSocketCtor: FakeWebSocket,
  });
  sock.open();
  const ws = FakeWebSocket.instances[0];
  ws.open();
  sock.send('hi', 'thread-x');
  assert.equal(ws.sent.length, 1);
  assert.deepEqual(JSON.parse(ws.sent[0]), {
    type: 'user_turn',
    text: 'hi',
    thread_id: 'thread-x',
  });
  sock.close();
});

test('dispatches incoming frames', () => {
  FakeWebSocket.instances = [];
  const calls = [];
  const sock = new OctopChatSocket({
    baseUrl: 'https://octop.example.com',
    token: 't',
    agentId: 'a1',
    WebSocketCtor: FakeWebSocket,
    onFrame: (frame) => calls.push(frame),
  });
  sock.open();
  const ws = FakeWebSocket.instances[0];
  ws.open();
  ws.message(JSON.stringify({ type: 'chunk', text: 'hello' }));
  ws.message(JSON.stringify({ type: 'done' }));
  assert.equal(calls.length, 2);
  assert.deepEqual(calls[0], { type: 'chunk', text: 'hello' });
  assert.deepEqual(calls[1], { type: 'done' });
  sock.close();
});

test('does nothing when send is called before open', () => {
  FakeWebSocket.instances = [];
  const sock = new OctopChatSocket({
    baseUrl: 'https://octop.example.com',
    token: 't',
    agentId: 'a1',
    WebSocketCtor: FakeWebSocket,
  });
  sock.open();
  assert.throws(() => sock.send('hi'));
  sock.close();
});

test('reports an error when JSON parse fails', () => {
  FakeWebSocket.instances = [];
  let errorCount = 0;
  const sock = new OctopChatSocket({
    baseUrl: 'https://octop.example.com',
    token: 't',
    agentId: 'a1',
    WebSocketCtor: FakeWebSocket,
    onError: () => {
      errorCount += 1;
    },
  });
  sock.open();
  const ws = FakeWebSocket.instances[0];
  ws.open();
  ws.message('not-json{');
  assert.ok(errorCount >= 1);
  sock.close();
});

test('uses ws:// for plain http base URL', () => {
  FakeWebSocket.instances = [];
  const sock = new OctopChatSocket({
    baseUrl: 'http://localhost:8787',
    token: 't',
    agentId: 'a1',
    WebSocketCtor: FakeWebSocket,
  });
  sock.open();
  assert.ok(FakeWebSocket.instances[0].url.startsWith('ws://localhost:8787/'));
  sock.close();
});
