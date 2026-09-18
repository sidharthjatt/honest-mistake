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
 * Three things end a run before the model says it is done: the turn
 * ceiling, the tool-call ceiling and the spend ceiling. All three are
 * tested at the top of the loop, before a request is built, because that
 * is the last moment at which nothing further can be spent. A visitor's
 * Stop is tested in the same place and for the same reason.
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
export const COST_LIMIT = 'cost_limit';
export const STOPPED = 'stopped';
/* A visitor's second Stop, which abandons the request in flight. agent.py
   has no counterpart: the Python loop has no way to abort a request. */
export const ABORTED = 'aborted';
export const FAILED = 'failed';

/* What each ending means, in a sentence. The loop records the enum; a
   visitor should never be shown the enum on its own. */
export const TERMINATION_SENTENCE = {
  [COMPLETED]: 'The agent finished and gave its answer.',
  [TRUNCATED]: 'The agent was cut off mid-sentence: one turn hit the per-request output ceiling.',
  [REFUSAL]: 'The model declined to continue.',
  [PAUSED]: 'The model paused the turn and the run was not resumed.',
  [STOP_SEQUENCE]: 'The model hit a stop sequence.',
  [UNKNOWN_STOP]: 'The model stopped for a reason this page does not recognise, so the run was ended rather than treated as finished.',
  [TURN_LIMIT]: 'The run hit its turn ceiling and was stopped before it could send another request.',
  [CALL_LIMIT]: 'The run hit its tool-call ceiling and was stopped.',
  [COST_LIMIT]: 'The run reached the spend ceiling and was stopped before it could send another request.',
  [STOPPED]: 'You stopped the run.',
  [ABORTED]: 'The run was cancelled mid-request.',
  [FAILED]: 'The run stopped on an error.',
};

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

/* The markers the system prompt tells the agent to wrap its answer in.
   Their presence is the only evidence that a run produced a verdict rather
   than being cut off mid-investigation, and the scorer treats it the same
   way: a run that never signalled it had finished is not scored, because a
   partial answer is not an answer. */
const FINDINGS_OPEN = '=== AUDIT FINDINGS ===';
const FINDINGS_CLOSE = '=== END AUDIT FINDINGS ===';

export function hasFindingsBlock(text) {
  if (!text) return false;
  const open = text.indexOf(FINDINGS_OPEN);
  if (open === -1) return false;
  return text.indexOf(FINDINGS_CLOSE, open + FINDINGS_OPEN.length) !== -1;
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
  /* The spend ceiling, in dollars, and the function that prices the usage
     counters. Both or neither: a ceiling with no way to price is not a
     ceiling. Enforced at the top of the loop, which is the only place that
     can stop money being spent — once a request is away it is billed
     whatever we do with the answer. */
  maxCost = null,
  priceUsage = null,
  /* Polled once per turn, in the same place. Returning true ends the run
     after the turn that is already paid for, so a visitor who changes
     their mind loses nothing that was not already bought. */
  shouldStop = null,
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
  /* Every text block the model wrote, in order. Kept only so the findings
     block can be looked for across the whole run rather than in the last
     turn alone: a run that wrote its answer and then said one more thing
     still produced a verdict. */
  let allText = '';
  let lastStopReason = '';
  let termination = TURN_LIMIT;
  let failure = null;

  if (maxCost !== null && typeof priceUsage !== 'function') {
    throw new Error('A spend ceiling was set without a way to price usage.');
  }
  const spend = () => (priceUsage ? priceUsage(usage) : 0);

  events.emit('run:started', {
    model: { id: model.id, label: model.label },
    config: { maxTurns, maxToolCalls, maxCost, cache, ...tools.config },
  });

  while (true) {
    /* The three gates, all before the request is built, because that is the
       last moment at which nothing more can be spent. They run in the order
       a visitor would want them to: their own decision first, then the
       ceilings they were shown. */
    if (shouldStop && shouldStop()) { termination = STOPPED; break; }
    if (turns >= maxTurns) { termination = TURN_LIMIT; break; }
    if (maxCost !== null && spend() >= maxCost) { termination = COST_LIMIT; break; }

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
        termination = ABORTED;
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
    if (reply.text) { finalText = reply.text; allText += reply.text + '\n'; }

    if (reply.thinking) events.emit('reasoning', { turn, text: reply.thinking });
    if (reply.text) events.emit('text', { turn, text: reply.text });

    const blocks = assistantContent(reply);
    if (blocks.length) messages.push({ role: 'assistant', content: blocks });

    // The model's half of the turn is over. The turn itself is not: its
    // tool calls run below and belong to it, so turn:finished waits.
    /* The running total is computed here, from the loop's own counters, and
       handed to the renderer. A meter that keeps a second tally of its own
       could drift from the number the ceiling is actually tested against,
       and the visitor would be watching the wrong one. */
    events.emit('model:replied', {
      turn,
      stopReason: reply.stop_reason,
      usage: { ...reply.usage },
      usageTotal: { ...usage },
      spend: spend(),
      maxCost,
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
    spend: spend(),
    /* Whether the agent produced a verdict at all. This is not the same
       question as whether the run ended cleanly: a run can reach its last
       turn and still have written nothing an answer could be read from.
       The page must not let a visitor mistake one for the other. */
    hasFindings: hasFindingsBlock(allText),
    reason: TERMINATION_SENTENCE[termination] || `The run ended (${termination}).`,
    failure,
    config: { maxTurns, maxToolCalls, maxCost, cache, model: model.id, ...tools.config },
    toolCallLog: tools.getCallLog(),
  };
  events.emit('run:finished', record);
  return record;
}
