/**
 * Octop bridge configuration store.
 *
 * Persists three values used by the desktop IM gateway when routing inbound
 * messages through a local Octop backend (`OctopChatHandler`):
 *
 *   - `octop_base_url`  — base URL of the Octop HTTP server
 *   - `octop_jwt`       — Bearer token issued by `POST /api/auth/login`
 *   - `octop_agent_id`  — agent id used as the chat target
 *
 * The `use_octop_for_im` toggle lets users fall back to the legacy direct-LLM
 * path (`IMChatHandler`) without losing credentials.
 */

import type { SqliteStore } from '../../sqliteStore';

export const OCTOP_BRIDGE_KEYS = {
  baseUrl: 'octop_base_url',
  jwt: 'octop_jwt',
  agentId: 'octop_agent_id',
  enabled: 'use_octop_for_im',
} as const;

export interface OctopBridgeConfig {
  baseUrl: string;
  jwt: string;
  agentId: string;
  enabled: boolean;
}

const DEFAULT_CONFIG: OctopBridgeConfig = {
  baseUrl: 'http://127.0.0.1:8088',
  jwt: '',
  agentId: '',
  enabled: true,
};

function trimString(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

export function readOctopBridgeConfig(store: SqliteStore): OctopBridgeConfig {
  const baseUrl = trimString(store.get(OCTOP_BRIDGE_KEYS.baseUrl)) || DEFAULT_CONFIG.baseUrl;
  const jwt = trimString(store.get(OCTOP_BRIDGE_KEYS.jwt));
  const agentId = trimString(store.get(OCTOP_BRIDGE_KEYS.agentId));
  const enabledRaw = store.get(OCTOP_BRIDGE_KEYS.enabled);
  const enabled =
    typeof enabledRaw === 'boolean'
      ? enabledRaw
      : typeof enabledRaw === 'string'
        ? enabledRaw !== 'false' && enabledRaw !== '0'
        : DEFAULT_CONFIG.enabled;
  return { baseUrl, jwt, agentId, enabled };
}

export function writeOctopBridgeConfig(
  store: SqliteStore,
  patch: Partial<OctopBridgeConfig>,
): OctopBridgeConfig {
  const next: OctopBridgeConfig = {
    ...readOctopBridgeConfig(store),
    ...patch,
    baseUrl: trimString(patch.baseUrl) || DEFAULT_CONFIG.baseUrl,
    jwt: trimString(patch.jwt),
    agentId: trimString(patch.agentId),
    enabled:
      typeof patch.enabled === 'boolean'
        ? patch.enabled
        : patch.enabled === undefined
          ? readOctopBridgeConfig(store).enabled
          : Boolean(patch.enabled),
  };
  store.set(OCTOP_BRIDGE_KEYS.baseUrl, next.baseUrl);
  store.set(OCTOP_BRIDGE_KEYS.jwt, next.jwt);
  store.set(OCTOP_BRIDGE_KEYS.agentId, next.agentId);
  store.set(OCTOP_BRIDGE_KEYS.enabled, next.enabled);
  return next;
}

/**
 * Returns Octop handler options when the bridge is fully configured and
 * enabled, or `null` to signal callers should fall back to the legacy LLM
 * path. The returned `getAgentId` resolves to the persisted agent id; if the
 * IM message carries its own pinned agent id it overrides via caller logic.
 */
export function buildOctopHandlerOptions(
  store: SqliteStore,
  imSettings: OctopBridgeHandlerImSettings,
): OctopHandlerOptions | null {
  const cfg = readOctopBridgeConfig(store);
  if (!cfg.enabled) return null;
  if (!cfg.baseUrl || !cfg.jwt || !cfg.agentId) return null;
  return {
    baseUrl: cfg.baseUrl,
    bearer: cfg.jwt,
    imSettings: imSettings as unknown as Record<string, unknown>,
    getAgentId: async () => cfg.agentId,
  };
}

export interface OctopBridgeHandlerImSettings {
  identityInstruction?: string;
  mediaInstruction?: string;
  skillsEnabled?: boolean;
  systemPrompt?: string;
}

// Re-exported so callers don't have to reach into `OctopChatHandler` for
// the shape; mirrors `OctopChatHandlerOptions` minus `WebSocketCtor` and
// `getSkillsPrompt` (added by the caller if needed).
export interface OctopHandlerOptions {
  baseUrl: string;
  bearer: string;
  imSettings: Record<string, unknown>;
  getAgentId: (message: { senderId?: string; conversationId?: string }) => Promise<string | null>;
}
