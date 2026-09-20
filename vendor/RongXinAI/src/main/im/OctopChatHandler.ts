/**
 * OctopChatHandler
 *
 * Mirror of IMChatHandler.processMessage that delegates to OctopChatClient
 * (octop's dashboard chat WebSocket) instead of calling a remote LLM directly.
 *
 * The interface intentionally matches IMChatHandler so IM-side code can pick
 * a backend at boot time without conditional call sites:
 *
 *   const handler = useOctop
 *     ? new OctopChatHandler({ baseUrl, bearer, getAgentId, imSettings })
 *     : new IMChatHandler({ getLLMConfig, imSettings });
 *   await handler.processMessage(message);
 *
 * The handler stitches together:
 *   1. Identity & media-instruction prompts from IMSettings (reused).
 *   2. Optional skill list from getSkillsPrompt (reused).
 *   3. A single octop `user_turn` over the chat WS.
 *   4. The collected text reply.
 */

import { OctopChatClient } from '../libs/octopBridge/OctopChatClient';
import type { OctopChatClientOptions, SendTurnInput } from '../libs/octopBridge/OctopChatClient';
import { buildIMMediaInstruction } from './imMediaInstruction';
import type { IMMessage, IMSettings } from './types';

export interface OctopChatHandlerOptions {
  baseUrl: string;
  /** JWT bearer token used by OctopChatClient. */
  bearer: string;
  /**
   * Resolve the agent id each turn. IM channels typically pin one agent per
   * channel account, but the resolver lets the caller route by sender / room.
   */
  getAgentId: (message: IMMessage) => Promise<string | null> | string | null;
  /**
   * Optional skill prompt block to merge into the user message (mirrors the
   * IMChatHandler contract).
   */
  getSkillsPrompt?: () => Promise<string | null>;
  /** Mirror of IMChatHandler.imSettings — only the prompt + skills toggle are read. */
  imSettings: IMSettings;
  /** Pass-through to OctopChatClient (used by tests to inject a fake WS). */
  WebSocketCtor?: OctopChatClientOptions['WebSocketCtor'];
}

export class OctopChatHandler {
  private readonly client: OctopChatClient;
  private readonly opts: OctopChatHandlerOptions;

  constructor(opts: OctopChatHandlerOptions) {
    this.opts = opts;
    const clientOpts: OctopChatClientOptions = {
      baseUrl: opts.baseUrl,
      bearer: opts.bearer,
    };
    if (opts.WebSocketCtor) clientOpts.WebSocketCtor = opts.WebSocketCtor;
    this.client = new OctopChatClient(clientOpts);
  }

  async processMessage(message: IMMessage, signal?: AbortSignal): Promise<string> {
    const agentId = await this.opts.getAgentId(message);
    if (!agentId) {
      throw new Error('OctopChatHandler: getAgentId returned empty');
    }

    let prompt = message.content ?? '';
    const skillsPrompt =
      this.opts.imSettings.skillsEnabled && this.opts.getSkillsPrompt
        ? await this.opts.getSkillsPrompt()
        : null;
    if (skillsPrompt) {
      prompt = prompt ? `${prompt}\n\n${skillsPrompt}` : skillsPrompt;
    }
    const mediaInstruction = buildIMMediaInstruction(this.opts.imSettings);
    if (mediaInstruction) {
      prompt = prompt ? `${prompt}\n\n${mediaInstruction}` : mediaInstruction;
    }

    const input: SendTurnInput = {
      agentId,
      text: prompt,
    };
    const result = await this.client.sendTurn(input, signal);
    return result.text;
  }
}
