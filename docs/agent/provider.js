export const BUILD = '91493d637f81';
/* Every outbound request is built and sent here, and nowhere else.
 *
 * Only Anthropic is implemented. The loop never names a provider: it calls
 * send() with messages, tools and a system prompt and gets back one
 * normalised reply. Adding Groq or an OpenAI-compatible endpoint later
 * means another object with the same three methods, not a change to the
 * loop — and its own CORS probe first, because the header below is
 * Anthropic's and nothing guarantees another host answers a browser at all.
 */

const ENDPOINT = 'https://api.anthropic.com/v1/messages';
const VERSION = '2023-06-01';

/* Direct browser access is off by default and this header turns it on.
   Without it the preflight returns no Access-Control-Allow-Origin and the
   POST is never dispatched. */
const BROWSER_HEADER = 'anthropic-dangerous-direct-browser-access';

/* The API rejects a request carrying more than four. */
const MAX_BREAKPOINTS = 4;

function countBreakpoints(value) {
  if (Array.isArray(value)) return value.reduce((n, v) => n + countBreakpoints(v), 0);
  if (value && typeof value === 'object') {
    return ('cache_control' in value ? 1 : 0) +
      Object.values(value).reduce((n, v) => n + countBreakpoints(v), 0);
  }
  return 0;
}

/* One marker on the last block of the newest user turn, so each request
   reads back everything the previous one wrote. This mirrors the
   moving-breakpoint mode the recorded run11 used.
   The caller's messages are never modified: every message is copied, and a
   plain-string content becomes a single text block on every request so its
   bytes do not change between turns. The stored history therefore never
   carries a marker and each request carries exactly one. */
export function buildRequest({ model, system, messages, tools, cache = true }) {
  if (!model) throw new Error('No model selected.');

  const body = { model: model.id, max_tokens: model.maxTokens };

  if (model.shape === 'adaptive') {
    body.thinking = { type: 'adaptive', display: 'summarized' };
    if (model.effort) body.output_config = { effort: model.effort };
  } else if (model.shape === 'budget') {
    body.thinking = { type: 'enabled', budget_tokens: model.thinkingBudgetTokens };
  } else {
    throw new Error(`Unknown request shape '${model.shape}' for ${model.id}.`);
  }

  if (!cache) {
    body.system = system;
    body.messages = messages;
  } else {
    if (!messages.length || messages[messages.length - 1].role !== 'user') {
      throw new Error('A cached request must end on a user turn.');
    }
    const copied = messages.map(m => ({
      ...m,
      content: typeof m.content === 'string'
        ? [{ type: 'text', text: m.content }]
        : m.content.map(b => ({ ...b })),
    }));
    const last = copied[copied.length - 1].content;
    if (!last.length) throw new Error('The last user turn has no block to mark.');
    last[last.length - 1].cache_control = { type: 'ephemeral' };
    // One block and no marker: the marker on the message already caches
    // tools and system, which render before it.
    body.system = [{ type: 'text', text: system }];
    body.messages = copied;
  }

  if (tools && tools.length) body.tools = tools;

  const found = countBreakpoints(body.tools || []) +
    countBreakpoints(body.system) + countBreakpoints(body.messages);
  if (found > MAX_BREAKPOINTS) {
    throw new Error(`The request carries ${found} cache breakpoints; the API allows ${MAX_BREAKPOINTS}.`);
  }
  return body;
}

/* A failure the caller can show a visitor. `kind` is what the UI branches
   on; `message` is already a sentence. */
export class ProviderError extends Error {
  constructor(kind, message, detail = {}) {
    super(message);
    this.name = 'ProviderError';
    this.kind = kind;
    this.detail = detail;
  }
}

function classify(status, payload, modelId) {
  const err = (payload && payload.error) || {};
  const type = err.type || '';
  const msg = err.message || '';

  // A retired or mistyped model must say so rather than leaving a dead
  // page. The API reports it as a 404, or as a 400 naming the model.
  if (status === 404 || (status === 400 && /model/i.test(msg))) {
    return new ProviderError('invalid_model',
      `The model '${modelId}' was not accepted: ${msg || 'no such model'}. ` +
      `It may have been retired. Choose another model and run again.`,
      { status, type, api_message: msg });
  }
  if (status === 401 || type === 'authentication_error') {
    return new ProviderError('auth',
      'That API key was not accepted. Check it and try again.',
      { status, type, api_message: msg });
  }
  if (status === 403) {
    return new ProviderError('forbidden',
      `The key was recognised but is not allowed to do this: ${msg}`,
      { status, type, api_message: msg });
  }
  if (status === 429) {
    return new ProviderError('rate_limit',
      'Rate limited by the API. Wait a moment and run again.',
      { status, type, api_message: msg });
  }
  if (status >= 500) {
    return new ProviderError('server',
      `The API returned a server error (${status}). This is not your key or your input.`,
      { status, type, api_message: msg });
  }
  return new ProviderError('request',
    msg ? `The API rejected the request: ${msg}` : `The API returned ${status}.`,
    { status, type, api_message: msg });
}

/* Send one request and return a normalised reply. Never retries: a ReAct
   turn is not idempotent, and a silent retry would bill the visitor twice
   for a turn they were never told about. */
export async function send({ apiKey, body, signal }) {
  let res;
  try {
    res = await fetch(ENDPOINT, {
      method: 'POST',
      signal,
      headers: {
        'content-type': 'application/json',
        'x-api-key': apiKey,
        'anthropic-version': VERSION,
        [BROWSER_HEADER]: 'true',
      },
      body: JSON.stringify(body),
    });
  } catch (cause) {
    if (cause && cause.name === 'AbortError') throw cause;
    throw new ProviderError('network',
      'The request never reached the API. Check the connection; a blocked ' +
      'request also looks like this.', { cause: String(cause) });
  }

  const text = await res.text();
  let payload = null;
  try { payload = JSON.parse(text); } catch { /* handled below */ }

  if (!res.ok) throw classify(res.status, payload, body.model);
  if (!payload) {
    throw new ProviderError('parse', 'The API returned a response that was not JSON.',
      { body: text.slice(0, 400) });
  }
  return normalise(payload);
}

/* The wire response, reduced to what the loop uses. `content` is kept
   whole so it can be appended to the history unchanged — thinking blocks
   must be echoed back as they came. */
function normalise(payload) {
  const content = Array.isArray(payload.content) ? payload.content : [];
  const u = payload.usage || {};
  return {
    id: payload.id,
    model: payload.model,
    stop_reason: payload.stop_reason || '',
    stop_details: payload.stop_details || null,
    content,
    text: content.filter(b => b.type === 'text').map(b => b.text).join(''),
    thinking: content
      .filter(b => b.type === 'thinking')
      .map(b => (b.summary || b.thinking || ''))
      .filter(Boolean)
      .join('\n'),
    tool_calls: content
      .filter(b => b.type === 'tool_use')
      .map(b => ({ id: b.id, name: b.name, input: b.input || {} })),
    usage: {
      input: u.input_tokens || 0,
      output: u.output_tokens || 0,
      cache_creation: u.cache_creation_input_tokens || 0,
      cache_read: u.cache_read_input_tokens || 0,
    },
  };
}

export const anthropic = { buildRequest, send };
