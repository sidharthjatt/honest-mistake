/* The ReAct loop, ported from agent/agent.py.
 *
 * Every turn emits events as it happens rather than returning a transcript
 * at the end, so a visual layer can render the run while it is running.
 * Events are emitted before the thing they describe blocks: tool:called
 * fires before the tool runs, request:sent before the network wait.
 *
 * The order within one turn, which a renderer can rely on:
 *
 *   turn:started -> request:sent -> [reasoning] -> [text] -> model:replied
 *     -> (tool:called -> tool:returned)*  -> turn:finished
 *
 * model:replied closes the model's half of the turn; turn:finished closes
 * the whole turn, after that turn's tool calls have run. Every event
 * carries `turn` and `at`. The run is bracketed by run:started and
 * run:finished, with run:aborted or a fatal error in place of the tools
 * when one occurs. No event ever carries the API key.
 *
 * The visitor's key is a parameter. It is never written to localStorage,
 * sessionStorage or IndexedDB, never put in a URL, and never included in
 * an event. It lives in the caller's variable and dies with the tab.
 */

import { buildRequest, send, ProviderError } from './provider.js';
import { serialiseToolResult } from './tools.js';

export const COMPLETED = 'completed';
export const TRUNCATED = 'truncated';
export const REFUSAL = 'refusal';
export const PAUSED = 'paused';
export const STOP_SEQUENCE = 'stop_sequence';
export const UNKNOWN_STOP = 'unknown_stop_reason';
export const TURN_LIMIT = 'turn_limit';
export const CALL_LIMIT = 'call_limit';
export const FAILED = 'failed';

/* Only end_turn means the model decided it was done. Every other value,
   recognised or not, ends the run without a usable answer, and the raw
   stop_reason is recorded either way. tool_use is handled by the tool
   branch and never reaches this mapping. */
const STOP_REASON_TERMINATION = {
  max_tokens: TRUNCATED,
  refusal: REFUSAL,
  pause_turn: PAUSED,
  stop_sequence: STOP_SEQUENCE,
};

export const DEFAULT_MAX_TURNS = 20;
export const DEFAULT_MAX_TOOL_CALLS = 70;

export class Events {
  constructor() { this.handlers = new Map(); }
  on(type, fn) {
    if (!this.handlers.has(type)) this.handlers.set(type, []);
    this.handlers.get(type).push(fn);
    return this;
  }
  emit(type, payload) {
    const event = { type, at: Date.now(), ...payload };
    for (const fn of this.handlers.get(type) || []) {
      try { fn(event); } catch (err) { console.error('event handler failed', type, err); }
    }
    // '*' sees every event, in order, after the specific handlers.
    for (const fn of this.handlers.get('*') || []) {
      try { fn(event); } catch (err) { console.error('event handler failed', type, err); }
    }
    return event;
  }
}

/* Fill the exported prompt template. Every placeholder must be replaced:
   a prompt that still reads "{max_turns}" would tell the model a limit
   that is not a number, and a prompt stating a different ceiling from the
   one enforced is the exact failure prompts.py exists to prevent. */
export function renderSystemPrompt(template, { maxTurns, maxToolCalls, nFeatures, figures }) {
  const filled = template.template
    .replaceAll('{max_turns}', String(maxTurns))
    .replaceAll('{max_tool_calls}', String(maxToolCalls))
    .replaceAll('{n_features}', String(nFeatures))
    .replaceAll('{test_roc_auc}', figures.test_roc_auc_text)
    .replaceAll('{val_roc_auc}', figures.val_roc_auc_text);
  const left = filled.match(/\{(max_turns|max_tool_calls|n_features|test_roc_auc|val_roc_auc)\}/);
  if (left) throw new Error(`The system prompt still contains ${left[0]} after rendering.`);
  return filled;
}

/* The assistant turn as it must be echoed back. Thinking blocks are
   returned unchanged, signature and all: the API rejects a replayed
   thinking block that has been edited. */
function assistantContent(reply) {
  return reply.content.filter(
    b => b.type === 'thinking' || b.type === 'redacted_thinking' ||
         b.type === 'text' || b.type === 'tool_use');
}

export async function runReactLoop({
  apiKey,
  model,
  tools,            // a ToolLayer
  toolSchemas,
  system,
  openingMessage = 'Begin your review.',
  maxTurns = DEFAULT_MAX_TURNS,
  maxToolCalls = DEFAULT_MAX_TOOL_CALLS,
  cache = true,
  signal,
  events = new Events(),
  /* The provider, injected. Defaults to Anthropic; a second adapter
     exposing buildRequest/send drops in here without the loop changing.
     A scripted transport also lets the loop be exercised without
     spending anything. */
  transport = { buildRequest, send },
} = {}) {

  const messages = [{ role: 'user', content: openingMessage }];
  const usage = { input: 0, output: 0, cache_creation: 0, cache_read: 0 };
  let turns = 0;
  let callsMade = 0;
  let finalText = '';
  let lastStopReason = '';
  let termination = TURN_LIMIT;
  let failure = null;

  events.emit('run:started', {
    model: { id: model.id, label: model.label },
    config: { maxTurns, maxToolCalls, cache, ...tools.config },
  });

  while (true) {
    if (turns >= maxTurns) { termination = TURN_LIMIT; break; }

    const turn = turns + 1;
    events.emit('turn:started', { turn, messageCount: messages.length });

    let reply;
    try {
      const body = transport.buildRequest({ model, system, messages, tools: toolSchemas, cache });
      events.emit('request:sent', {
        turn,
        model: model.id,
        messageCount: body.messages.length,
        cacheBreakpoint: cache,
      });
      reply = await transport.send({ apiKey, body, signal });
    } catch (err) {
      if (err && err.name === 'AbortError') {
        termination = 'aborted';
        events.emit('run:aborted', { turn });
        break;
      }
      // A failed request is shown, not swallowed: an invalid or retired
      // model has to read as a message rather than a page that stops.
      failure = {
        kind: err instanceof ProviderError ? err.kind : 'unknown',
        message: err.message,
        detail: err instanceof ProviderError ? err.detail : null,
      };
      termination = FAILED;
      events.emit('error', { turn, fatal: true, ...failure });
      break;
    }

    turns += 1;
    for (const k of Object.keys(usage)) usage[k] += reply.usage[k] || 0;
    lastStopReason = reply.stop_reason;
    if (reply.text) finalText = reply.text;

    if (reply.thinking) events.emit('reasoning', { turn, text: reply.thinking });
    if (reply.text) events.emit('text', { turn, text: reply.text });

    const blocks = assistantContent(reply);
    if (blocks.length) messages.push({ role: 'assistant', content: blocks });

    // The model's half of the turn is over. The turn itself is not: its
    // tool calls run below and belong to it, so turn:finished waits.
    events.emit('model:replied', {
      turn,
      stopReason: reply.stop_reason,
      usage: { ...reply.usage },
      toolCallCount: reply.tool_calls.length,
    });

    let toolsRan = 0;
    const closeTurn = () => events.emit('turn:finished', {
      turn,
      stopReason: reply.stop_reason,
      usage: { ...reply.usage },
      toolCallsThisTurn: toolsRan,
      termination: termination === TURN_LIMIT ? null : termination,
    });

    // Classified before the tool-call test. Several stop reasons carry no
    // tool calls and would otherwise look exactly like a finished turn.
    if (reply.stop_reason in STOP_REASON_TERMINATION) {
      termination = STOP_REASON_TERMINATION[reply.stop_reason];
      closeTurn();
      break;
    }

    if (reply.tool_calls.length) {
      // Enforced before the batch runs, so the recorded call count never
      // exceeds the ceiling that was set.
      if (callsMade + reply.tool_calls.length > maxToolCalls) {
        termination = CALL_LIMIT;
        closeTurn();
        break;
      }
    } else if (reply.stop_reason === 'end_turn') {
      termination = COMPLETED;
      closeTurn();
      break;
    } else {
      // An unrecognised stop reason never becomes a completion.
      termination = UNKNOWN_STOP;
      closeTurn();
      break;
    }

    const results = [];
    for (const call of reply.tool_calls) {
      events.emit('tool:called', {
        turn, id: call.id, name: call.name, input: call.input,
        index: callsMade + 1,
      });
      const started = performance.now();
      // dispatch never throws; a rejected call comes back as a message and
      // is fed to the model like any other result so it can correct itself.
      const output = tools.dispatch(call.name, call.input);
      const durationMs = Math.round(performance.now() - started);
      callsMade += 1;
      // Python's spacing, so the model reads the bytes the recorded runs sent.
      const serialised = serialiseToolResult(output);
      events.emit('tool:returned', {
        turn, id: call.id, name: call.name, input: call.input,
        result: output, bytes: serialised.length, durationMs,
        index: callsMade,
      });
      results.push({ type: 'tool_result', tool_use_id: call.id, content: serialised });
      toolsRan += 1;
    }
    messages.push({ role: 'user', content: results });
    closeTurn();
  }

  const record = {
    finalText,
    termination,
    lastStopReason,
    turns,
    toolCalls: callsMade,
    usage,
    failure,
    config: { maxTurns, maxToolCalls, cache, model: model.id, ...tools.config },
    toolCallLog: tools.getCallLog(),
  };
  events.emit('run:finished', record);
  return record;
}
