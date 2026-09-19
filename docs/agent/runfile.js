export const BUILD = 'ed6b67583fac';
/* Keeping a finished run, and writing it out.
 *
 * Two different failures, two mechanisms. sessionStorage survives a reload
 * and a navigation away and back within the tab, which is the failure that
 * has actually bitten: the beforeunload guard disarms the moment a run
 * ends, so a reload afterwards is silent and total. It does not survive
 * closing the tab, a second tab, or another device. The download covers
 * those, and neither substitutes for the other.
 *
 * The key is in neither. No event the loop emits carries it, the record
 * built here never reads it, and Screen 1 says so in as many words.
 *
 * On the file: it deliberately does NOT look like one of the twelve. Same
 * field names inside, so the replay page could read it and so a run can be
 * cited — but a different filename and a different top-level key, because
 * a file shaped exactly like a recorded run will eventually be dropped into
 * docs/data/runs/, and at that point it is a thirteenth run with no hash,
 * no commit and no export script behind it. A marker inside the file does
 * not survive a glance. A filename does.
 */

const STORE_KEY = 'honest-mistake:last-run';
const SCHEMA = 'honest-mistake/browser-run';
const SCHEMA_VERSION = 1;

/* ------------------------------------------------------------- the record */

/* Built from the loop's events, which carry more than its return value
   does. Every turn's usage is here, where the twelve have per-turn usage
   for exactly one run and the bundle lists its absence under cannot_carry. */
export function buildRecord({ events, result, model, card, variant, canaryPresent,
                              system, toolConfig, limits, startedAt }) {
  const messages = [];
  const perTurn = [];
  let current = null;

  const open = () => {
    if (!current) {
      current = { index: messages.length, role: 'assistant', blocks: [] };
      messages.push(current);
    }
    return current;
  };

  messages.push({ index: 0, role: 'user', blocks: [{ type: 'text', text: events.opening }] });

  for (const e of events.list) {
    switch (e.type) {
      case 'turn:started':
        current = null;
        break;
      case 'reasoning':
        open().blocks.push({ type: 'thinking', summary: e.text, summary_empty: !e.text });
        break;
      case 'text':
        open().blocks.push({ type: 'text', text: e.text });
        break;
      case 'tool:called':
        open().blocks.push({ type: 'tool_call', id: e.id, tool: e.name, arguments: e.input });
        break;
      case 'tool:returned':
        messages.push({
          index: messages.length, role: 'user',
          blocks: [{ type: 'tool_result', id: e.id, tool: e.name, result: e.result,
                     bytes: e.bytes, duration_ms: e.durationMs }],
        });
        current = null;
        break;
      case 'model:replied':
        perTurn.push({
          request: e.turn,
          completed_at: new Date(e.at).toISOString().slice(0, 19),
          input: e.usage.input, output: e.usage.output,
          cache_creation: e.usage.cache_creation, cache_read: e.usage.cache_read,
          cost_usd_estimated: Number((e.spend - (perTurn.at(-1)?.cumulative ?? 0)).toFixed(6)),
          cumulative: e.spend,
        });
        break;
      default:
        break;
    }
  }
  for (const t of perTurn) delete t.cumulative;

  return {
    // Not "label". A recorded run's label is its directory name.
    schema: SCHEMA,
    schema_version: SCHEMA_VERSION,
    run_id: `browser-${startedAt.toISOString().replace(/[:.]/g, '-')}`,
    produced_by: 'docs/scan.html, in a visitor’s browser',

    /* Said outright, not left to be noticed. Each of these is a way this
       file is not one of the twelve. */
    not_a_recorded_run: [
      'Cost is computed from token counts against the price table in ' +
      'docs/agent/models.js. It is not read from a billing ledger and may ' +
      'differ from what Anthropic actually charged.',
      'Retrieval is substring-fallback over the exported dictionary. The ' +
      'twelve recorded runs used a pgvector index over embeddings, so this ' +
      'is not the same agent that produced them.',
      'This file was produced client-side, in the browser, from data only ' +
      'that browser saw. Nothing attests that the run happened: there is no ' +
      'commit, no export script and no hash behind it. The twelve recorded ' +
      'runs are exported from committed run directories and every source ' +
      'they were built from is hashed in docs/data/bundle.json.',
    ],

    /* Present and null rather than absent, so a reader sees what is missing
       instead of wondering whether it was forgotten. */
    facts: {
      run_id: `browser-${startedAt.toISOString().replace(/[:.]/g, '-')}`,
      directory: null,               // never on a filesystem
      fields_not_in_manifest: null,  // there is no manifest to reconcile against
      model: model.id,
      started: startedAt.toISOString(),
      finished: new Date().toISOString(),
      canary: { present: canaryPresent, established_by: 'assigned by this page',
                column: canaryPresent ? variant && 'recoveries' : null },
      variant,
      candidate: card,
      tool_layer_version: toolConfig.tool_layer_version,
      dictionary_populated_field: toolConfig.dictionary_populated_field,
      coverage_scopes: toolConfig.coverage_scopes,
      retrieval: toolConfig.retrieval,
      prompt_caching: result.config.cache ? 'moving-breakpoint' : null,
      limits,
      max_tokens_per_turn: model.maxTokens,
      termination: result.termination,
      last_stop_reason: result.lastStopReason,
      turns: result.turns,
      tool_calls: result.toolCalls,
      usage_totals: result.usage,
      cost_usd_estimated: result.spend,
      system_prompt_chars: system.length,
    },
    final_answer_text: result.finalText,
    tool_calls_without_results: messages
      .flatMap(m => m.blocks).filter(b => b.type === 'tool_call').length
      - messages.flatMap(m => m.blocks).filter(b => b.type === 'tool_result').length,
    ends_on_role: messages.at(-1)?.role ?? null,
    per_turn_usage: perTurn,
    per_turn_usage_note:
      'From the loop’s own events, one entry per request. Cost is estimated ' +
      'from token counts, not billed.',
    tool_call_log: result.toolCallLog,
    messages,
  };
}

/* ------------------------------------------------------------ persistence */

/* Every read and write is wrapped: sessionStorage throws in a private
   window with site data blocked, and a page that cannot keep a run must
   still render one. */
export function remember(record) {
  try {
    sessionStorage.setItem(STORE_KEY, JSON.stringify(record));
    return true;
  } catch {
    return false;
  }
}

export function recall() {
  try {
    const raw = sessionStorage.getItem(STORE_KEY);
    if (!raw) return null;
    const record = JSON.parse(raw);
    // A record from an older shape is dropped rather than rendered wrongly.
    if (record?.schema !== SCHEMA || record.schema_version !== SCHEMA_VERSION) return null;
    return record;
  } catch {
    return null;
  }
}

export function forget() {
  try { sessionStorage.removeItem(STORE_KEY); } catch { /* nothing to do */ }
}

/* ------------------------------------------------------------- download */

export function download(record) {
  const blob = new Blob([JSON.stringify(record, null, 1) + '\n'],
                        { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${record.run_id}.json`;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

/* ------------------------------------------------------------ the view */

/* What the screen renders from. The file's shape is chosen for a reader of
   the file; this is the shape the page wants, and keeping the translation
   in one named place stops the two drifting into each other. `variant` is
   here because the reveal depends on it and it must come from the record —
   never from whatever assignment the page dealt at its last boot. */
export function view(record) {
  const f = record.facts;
  return {
    card: f.candidate,
    variant: f.variant,
    canaryPresent: f.canary.present,
    finalText: record.final_answer_text,
    turns: f.turns,
    toolCalls: f.tool_calls,
    spend: f.cost_usd_estimated,
    // Null on a record saved before the ceiling was written into it.
    maxCost: f.limits?.max_cost_usd ?? null,
    termination: f.termination,
    terminationSentence: record.termination_sentence || null,
  };
}
