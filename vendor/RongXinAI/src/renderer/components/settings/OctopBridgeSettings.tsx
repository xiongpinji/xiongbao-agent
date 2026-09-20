import { Button } from '@shared/components/ui/button';
import { Input } from '@shared/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@shared/components/ui/select';
import { Switch } from '@shared/components/ui/switch';
import { RefreshCw, KeyRound, Plug, Power } from 'lucide-react';
import React, { useCallback, useEffect, useState } from 'react';

import { normalizeError } from '../../services/errorNormalization';

interface OctopBridgeConfigDto {
  baseUrl: string;
  jwt: string;
  agentId: string;
  enabled: boolean;
}

interface OctopAgentSummary {
  id: string;
  name: string;
}

type Status =
  | { kind: 'idle' }
  | { kind: 'loading'; message: string }
  | { kind: 'success'; message: string }
  | { kind: 'error'; message: string };

function StatusBanner({ status }: { status: Status }): React.ReactElement | null {
  if (status.kind === 'idle') return null;
  const tone =
    status.kind === 'success'
      ? 'text-emerald-600 dark:text-emerald-400'
      : status.kind === 'error'
        ? 'text-rose-600 dark:text-rose-400'
        : 'text-muted-foreground';
  return <p className={`text-xs ${tone}`}>{status.message}</p>;
}

export function OctopBridgeSettings(): React.ReactElement {
  const [config, setConfig] = useState<OctopBridgeConfigDto | null>(null);
  const [baseUrl, setBaseUrl] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [agentId, setAgentId] = useState('');
  const [enabled, setEnabled] = useState(true);
  const [agents, setAgents] = useState<OctopAgentSummary[]>([]);
  const [status, setStatus] = useState<Status>({ kind: 'idle' });
  const [hydrated, setHydrated] = useState(false);

  // Hydrate from main process on mount.
  useEffect(() => {
    let cancelled = false;
    const hydrate = async () => {
      try {
        const cfg = (await window.electron.octopBridge.getConfig()) as OctopBridgeConfigDto;
        if (cancelled) return;
        setConfig(cfg);
        setBaseUrl(cfg.baseUrl);
        setAgentId(cfg.agentId);
        setEnabled(cfg.enabled);
      } catch (err) {
        if (!cancelled) setStatus({ kind: 'error', message: normalizeError(err) });
      } finally {
        if (!cancelled) setHydrated(true);
      }
    };
    void hydrate();
    return () => {
      cancelled = true;
    };
  }, []);

  const persist = useCallback(
    async (patch: Partial<OctopBridgeConfigDto>) => {
      try {
        const next = (await window.electron.octopBridge.setConfig(patch)) as OctopBridgeConfigDto;
        setConfig(next);
        return next;
      } catch (err) {
        setStatus({ kind: 'error', message: normalizeError(err) });
        return null;
      }
    },
    [],
  );

  const handleSaveBaseUrl = useCallback(async () => {
    const trimmed = baseUrl.trim();
    if (!trimmed) {
      setStatus({ kind: 'error', message: '请填写 Octop 服务地址' });
      return;
    }
    setStatus({ kind: 'loading', message: '正在保存…' });
    const next = await persist({ baseUrl: trimmed });
    if (next) setStatus({ kind: 'success', message: '已保存服务地址' });
  }, [baseUrl, persist]);

  const handleLogin = useCallback(async () => {
    const u = username.trim();
    const p = password;
    if (!u || !p) {
      setStatus({ kind: 'error', message: '请输入账号和密码' });
      return;
    }
    setStatus({ kind: 'loading', message: '正在登录 Octop…' });
    try {
      const res = (await window.electron.octopBridge.login({
        baseUrl: baseUrl.trim(),
        username: u,
        password: p,
      })) as { success: true; config: OctopBridgeConfigDto } | { success: false; error: string };
      if (!res.success) {
        setStatus({ kind: 'error', message: res.error });
        return;
      }
      setConfig(res.config);
      setPassword('');
      setStatus({ kind: 'success', message: '登录成功，JWT 已保存' });
    } catch (err) {
      setStatus({ kind: 'error', message: normalizeError(err) });
    }
  }, [baseUrl, password, persist, username]);

  const refreshAgents = useCallback(async () => {
    if (!config?.jwt) {
      setStatus({ kind: 'error', message: '请先登录 Octop 后端' });
      return;
    }
    setStatus({ kind: 'loading', message: '正在拉取 agent 列表…' });
    try {
      const res = (await window.electron.octopBridge.listAgents({})) as
        | { success: true; agents: OctopAgentSummary[] }
        | { success: false; error: string };
      if (!res.success) {
        setStatus({ kind: 'error', message: res.error });
        return;
      }
      setAgents(res.agents);
      setStatus({ kind: 'success', message: `已找到 ${res.agents.length} 个 agent` });
    } catch (err) {
      setStatus({ kind: 'error', message: normalizeError(err) });
    }
  }, [config?.jwt]);

  const handleSelectAgent = useCallback(
    async (value: string) => {
      setAgentId(value);
      setStatus({ kind: 'loading', message: '正在保存 agent id…' });
      const next = await persist({ agentId: value });
      if (next) setStatus({ kind: 'success', message: '已选择 agent' });
    },
    [persist],
  );

  const handleToggleEnabled = useCallback(
    async (next: boolean) => {
      setEnabled(next);
      setStatus({ kind: 'loading', message: next ? '正在启用 Octop 接管…' : '正在切回本地 LLM…' });
      const cfg = await persist({ enabled: next });
      if (cfg) {
        setStatus({
          kind: 'success',
          message: next
            ? '已启用 — IM 消息将通过 Octop 路由'
            : '已关闭 — IM 消息直接走本地 LLM',
        });
      }
    },
    [persist],
  );

  const hasJwt = Boolean(config?.jwt);
  const hasAgentId = Boolean(agentId);

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-base font-semibold text-foreground">Octop 连接</h2>
        <p className="text-xs text-muted-foreground mt-1">
          把桌面端 IM 收到的消息转交给本地 Octop 后端处理。开启后，IM 消息会走 Octop
          的对话 WebSocket，而非直接调用模型 provider。
        </p>
      </header>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-foreground flex items-center gap-2">
              <Power className="h-4 w-4" />
              启用 Octop 接管 IM
            </p>
            <p className="text-xs text-muted-foreground">
              关闭后 IM 消息继续走桌面端本地 LLM（兼容旧行为）。
            </p>
          </div>
          <Switch
            checked={enabled}
            onCheckedChange={handleToggleEnabled}
            disabled={!hydrated}
            aria-label="启用 Octop 接管 IM"
          />
        </div>
      </section>

      <section className="space-y-3">
        <p className="text-sm font-medium text-foreground flex items-center gap-2">
          <Plug className="h-4 w-4" />
          服务地址
        </p>
        <div className="flex items-center gap-2">
          <Input
            value={baseUrl}
            onChange={e => setBaseUrl(e.target.value)}
            placeholder="http://127.0.0.1:8088"
            autoComplete="off"
            spellCheck={false}
          />
          <Button variant="secondary" onClick={handleSaveBaseUrl} disabled={!hydrated}>
            保存
          </Button>
        </div>
      </section>

      <section className="space-y-3">
        <p className="text-sm font-medium text-foreground flex items-center gap-2">
          <KeyRound className="h-4 w-4" />
          登录 Octop
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          <Input
            value={username}
            onChange={e => setUsername(e.target.value)}
            placeholder="账号"
            autoComplete="username"
          />
          <Input
            value={password}
            onChange={e => setPassword(e.target.value)}
            placeholder="密码"
            type="password"
            autoComplete="current-password"
          />
        </div>
        <div className="flex items-center gap-2">
          <Button onClick={handleLogin} disabled={!hydrated}>
            登录并保存 JWT
          </Button>
          {hasJwt ? (
            <span className="text-xs text-emerald-600 dark:text-emerald-400">JWT 已就绪</span>
          ) : (
            <span className="text-xs text-muted-foreground">尚未登录</span>
          )}
        </div>
      </section>

      <section className="space-y-3">
        <p className="text-sm font-medium text-foreground">Agent</p>
        <div className="flex items-center gap-2">
          <Select
            value={agentId}
            onValueChange={(value: string | null) => {
              if (typeof value === 'string') void handleSelectAgent(value);
            }}
            disabled={!hasJwt}
          >
            <SelectTrigger className="w-72">
              <SelectValue placeholder="选择 Octop agent" />
            </SelectTrigger>
            <SelectContent>
              {agents.length === 0 ? (
                <SelectItem value="__placeholder__" disabled>
                  请先点击右侧「拉取 agents」
                </SelectItem>
              ) : (
                agents.map(agent => (
                  <SelectItem key={agent.id} value={agent.id}>
                    {agent.name || agent.id}
                  </SelectItem>
                ))
              )}
            </SelectContent>
          </Select>
          <Button variant="secondary" onClick={refreshAgents} disabled={!hasJwt || !hydrated}>
            <RefreshCw className="h-4 w-4 mr-1" />
            拉取 agents
          </Button>
          {hasAgentId ? (
            <span className="text-xs text-emerald-600 dark:text-emerald-400">已选择</span>
          ) : (
            <span className="text-xs text-muted-foreground">未选择</span>
          )}
        </div>
      </section>

      <StatusBanner status={status} />
    </div>
  );
}
