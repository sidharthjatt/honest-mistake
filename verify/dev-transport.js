/* A scripted stand-in for the provider, used to build and test the scan
 * page without spending anything.
 *
 * It implements the same two methods the real adapter does, so the loop
 * cannot tell the difference. The replies are written to exercise every
 * tool visualisation, including the ones that come back found=false on a
 * variant that lacks the column. That path has nothing to plot and shows
 * the tool's own message instead, and it needs testing too.
 *
 * Loaded only when the page is opened with ?dev, by dynamic import, and it
 * lives outside docs/ so it is never published. On the deployed site the
 * path does not resolve at all: docs/ is the server root there, and ../
 * escapes it. Dev mode therefore works only when the repository root is
 * being served locally, which is the right place for it to work.
 */

import { buildRequest } from '../docs/agent/provider.js';

const wait = ms => new Promise(r => setTimeout(r, ms));

const TURNS = [
  {
    stop: 'tool_use',
    thinking: 'Start with what the model leans on. If one column dominates the ' +
      'attribution, that is where a leak would show first.',
    calls: [['get_shap_ranking', { top_n: 12 }]],
  },
  {
    stop: 'tool_use',
    thinking: 'One column carries far more than the rest. Before believing that, ' +
      'find out what it means and how its influence is spread across loans.',
    calls: [['lookup_feature', { feature: 'recoveries' }],
            ['get_feature_shap_detail', { feature: 'recoveries' }]],
  },
  {
    stop: 'tool_use',
    thinking: 'If that column is doing the work, removing it should cost the model ' +
      'most of its score. That is a test, not a guess.',
    calls: [['get_ablation_result', { feature: 'recoveries' }]],
  },
  {
    stop: 'tool_use',
    thinking: 'Now the other direction: are there columns whose completeness tracks ' +
      'when the loan was written rather than how risky it was?',
    calls: [['search_data_dictionary', { query: 'recovery' }],
            ['get_feature_coverage', { feature: 'all_util_was_missing' }]],
  },
  {
    stop: 'tool_use',
    thinking: 'Check whether that column orders the outcome on its own, and what ' +
      'else moves with the strongest ordinary feature.',
    calls: [['get_feature_target_association', { feature: 'open_acc_6m_was_missing' }],
            ['get_correlated_features', { feature: 'term', top_k: 8 }]],
  },
  {
    stop: 'end_turn',
    /* A real findings block, in the shape prompts.py asks for, because the
       page now branches on whether one is present. Without it this script
       could only ever exercise the no-verdict path. */
    text: 'Scripted reply. Nothing above was sent anywhere — this is the dev ' +
      'transport. The block below is here so the finished-run path can be ' +
      'tested; the columns in it are examples, not a real finding.\n\n' +
      '=== AUDIT FINDINGS ===\n' +
      'FLAG: all_util_was_missing\n' +
      'REASON: its completeness tracks when the loan was written rather than how risky it was.\n' +
      'EVIDENCE: get_feature_coverage showed the column absent for whole vintages.\n' +
      'CONFIDENCE: medium\n' +
      '###\n' +
      'FLAG: open_acc_6m_was_missing\n' +
      'REASON: it orders the outcome on its own, apart from the fitted model.\n' +
      'EVIDENCE: get_feature_target_association returned a per-year AUC well above 0.5.\n' +
      'CONFIDENCE: low\n' +
      '=== END AUDIT FINDINGS ===',
    calls: [],
  },
];

/* Two flags chosen for which cards they reach, not for what they say:
   loan_status, which the key credits although no model reads it, and
   int_rate, a real input the key does not score. The REASON and EVIDENCE
   text is placeholder. It deliberately does not reproduce the reasoning
   of the browser run that first flagged these two, which was never
   recorded and cannot be sourced. */
const NAMED_FINAL = {
  stop: 'end_turn',
  text: 'Scripted reply for the named scenario.\n\n' +
    '=== AUDIT FINDINGS ===\n' +
    'FLAG: int_rate\n' +
    'REASON: example text for the fixture.\n' +
    'EVIDENCE: example text for the fixture.\n' +
    'CONFIDENCE: medium\n' +
    '###\n' +
    'FLAG: loan_status\n' +
    'REASON: example text for the fixture; not a reconstruction of any real run.\n' +
    'EVIDENCE: example text for the fixture.\n' +
    'CONFIDENCE: low\n' +
    '=== END AUDIT FINDINGS ===',
  calls: [],
};

/* One key column from every branch of the credited copy, picked because the
   copy once said the wrong thing about them. The unreachable card used to
   describe every column as the loan's own outcome, and ?dev=named let that
   through by flagging loan_status, the one column it was true of. So:
     recoveries            tier A, post-outcome but not the outcome
     total_rec_prncp       tier B
     hardship_flag         tier C
     last_fico_range_high  no tier, and no description in the published key
     loan_status           the one column the outcome sentence is for
   recoveries is also the one scored column any model reads, and only the
   canary variant reads it, so on a canary deal it reaches the plain
   credited card instead. The text is synthetic, like the fixture above. */
const CREDITED_COLUMNS = ['recoveries', 'total_rec_prncp', 'hardship_flag',
  'last_fico_range_high', 'loan_status'];
const CREDITED_FINAL = {
  stop: 'end_turn',
  text: 'Scripted reply for the credited scenario.\n\n' +
    '=== AUDIT FINDINGS ===\n' +
    CREDITED_COLUMNS.map(c =>
      `FLAG: ${c}\n` +
      'REASON: synthetic fixture text, written to reach a credited card; not a real finding.\n' +
      'EVIDENCE: synthetic fixture text; no tool output is being described.\n' +
      'CONFIDENCE: medium\n').join('###\n') +
    '=== END AUDIT FINDINGS ===',
  calls: [],
};

/* member_id is one of the two columns the key sets aside. It reaches the
   out_of_scope card on either variant. */
const OUT_OF_SCOPE_FINAL = {
  stop: 'end_turn',
  text: 'Scripted reply for the out-of-scope scenario.\n\n' +
    '=== AUDIT FINDINGS ===\n' +
    'FLAG: member_id\n' +
    'REASON: synthetic fixture text, written to reach the out-of-scope card; not a real finding.\n' +
    'EVIDENCE: synthetic fixture text; no tool output is being described.\n' +
    'CONFIDENCE: low\n' +
    '=== END AUDIT FINDINGS ===',
  calls: [],
};

/* The findings block comes one turn too early. Turn 5 writes it and also
   calls a tool, so the run goes on, and turn 6 says one more sentence and
   ends. Only the final answer is scored, as it was for the recorded runs,
   so this run has no verdict even though a block appears in the stream.
   That's the case where a check over all of the run's text and the parser
   over the last turn would disagree. */
const LATE_BLOCK = [
  {
    stop: 'tool_use',
    text: 'Synthetic fixture text, not a real finding.\n\n' +
      '=== AUDIT FINDINGS ===\n' +
      'FLAG: loan_status\n' +
      'REASON: synthetic fixture text; this block is written a turn too early on purpose.\n' +
      'EVIDENCE: synthetic fixture text; no tool output is being described.\n' +
      'CONFIDENCE: low\n' +
      '=== END AUDIT FINDINGS ===',
    calls: [['lookup_feature', { feature: 'loan_status' }]],
  },
  {
    stop: 'end_turn',
    text: 'Synthetic fixture text: one more sentence after the block, and no block in this turn.',
    calls: [],
  },
];

/* Ends cleanly on end_turn but never writes the block, which is the one
   case that is neither a truncation nor a result. */
const NO_BLOCK_FINAL = {
  stop: 'end_turn',
  text: 'Scripted reply that deliberately stops without emitting the findings ' +
    'block, to exercise the completed-but-verdictless path.',
  calls: [],
};

/* The final answer opens the findings block and never closes it. The
   parser's second early exit: a start marker with no end marker after it. */
const UNCLOSED_FINAL = {
  stop: 'end_turn',
  text: 'Synthetic fixture text, not a real finding.\n\n' +
    '=== AUDIT FINDINGS ===\n' +
    'FLAG: loan_status\n' +
    'REASON: synthetic fixture text; this block is left open on purpose.\n' +
    'EVIDENCE: synthetic fixture text; no tool output is being described.\n' +
    'CONFIDENCE: low\n',
  calls: [],
};

/* Ends on end_turn with no text at all. The first five turns of the script
   carry thinking but no text, so this run never wrote a final answer. */
const EMPTY_FINAL = {
  stop: 'end_turn',
  calls: [],
};

/* The ordinary script completes in six turns, which is the point of it but
 * makes the stop conditions unreachable: a cap that is never hit is a cap
 * that has never been tested. Each scenario below is a transport that runs
 * into exactly one of them.
 *
 *   ?dev=1        the six-turn script, ends on end_turn
 *   ?dev=endless  never ends, one call a turn      -> turn ceiling
 *   ?dev=calls    four calls a turn, never ends    -> tool-call ceiling
 *   ?dev=costly   enormous usage a turn            -> spend ceiling
 *   ?dev=slow     eight seconds a turn             -> for testing Stop
 *   ?dev=noblock  the six-turn script, but the last turn omits the
 *                 findings block                   -> completed, no verdict
 *   ?dev=named    the six-turn script, ending on loan_status and int_rate
 *                 -> a credited flag the model never read, and a plain
 *                    input the key does not score. Both cards print the
 *                    model's input count, so this is the scenario that
 *                    shows whether that count follows the run's own variant.
 *   ?dev=credited the six-turn script, ending on five key columns: one each
 *                 of tier A, B, C, no tier, and loan_status
 *                 -> credited_unreachable for all five on the honest model;
 *                    on a canary deal, recoveries is the plain credited card
 *   ?dev=oos      the six-turn script, ending on member_id
 *                 -> the out_of_scope card, on either variant
 *   ?dev=late     the findings block in turn 5, alongside a tool call, then
 *                 a sixth turn with text and no block
 *                 -> no verdict, because only the final answer is scored
 *   ?dev=unclosed the six-turn script, ending on a findings block with no
 *                 end marker                       -> completed, no verdict
 *   ?dev=empty    the six-turn script, ending with no text, and no turn
 *                 before it wrote any              -> completed, no verdict
 *   ?dev=costexact  one turn costs exactly $1.00 on Sonnet 5 -> spend
 *                   ceiling, spend equal to it
 *   ?dev=costnear   one turn costs $1.002 on Sonnet 5 -> spend ceiling,
 *                   past it by less than a cent
 *   ?dev=blockstop    as slow, but every turn also writes a complete
 *                     findings block               -> press Stop: stopped
 *   ?dev=blockturns   as endless, with the block   -> turn ceiling
 *   ?dev=blockcost    as costly, with the block    -> spend ceiling
 *                 -> all three: no verdict, though the last text holds a
 *                    complete block, because the run did not finish
 */
/* A complete, well-formed findings block, written on every turn of the
   block* scenarios alongside a tool call, so the run never ends itself.
   Whatever ends it, the block must not be scored: only a completed run is,
   and the page has to say so without claiming there were no findings. */
const EVERY_TURN_BLOCK = 'Synthetic fixture text, not a real finding.\n\n' +
  '=== AUDIT FINDINGS ===\n' +
  'FLAG: recoveries\n' +
  'REASON: synthetic fixture text; this block is complete but the run is not.\n' +
  'EVIDENCE: synthetic fixture text; no tool output is being described.\n' +
  'CONFIDENCE: high\n' +
  '=== END AUDIT FINDINGS ===';

const SCENARIOS = {
  endless: { callsPerTurn: 1, endless: true },
  calls: { callsPerTurn: 4, endless: true },
  costly: { callsPerTurn: 1, endless: true,
            usage: { input: 0, output: 9000, cache_creation: 60000, cache_read: 120000 } },
  slow: { callsPerTurn: 1, endless: true, latencyMs: 8000 },
  /* One turn priced at exactly $1.00 at Sonnet 5's $10/MTok output rate,
     and one at $1.002, which rounds to $1.00. Against the default $1.00
     ceiling they show the "at" and the near-miss "past" spend sentences. */
  costexact: { callsPerTurn: 1, endless: true,
               usage: { input: 0, output: 100000, cache_creation: 0, cache_read: 0 } },
  costnear: { callsPerTurn: 1, endless: true,
              usage: { input: 0, output: 100200, cache_creation: 0, cache_read: 0 } },
  blockstop: { callsPerTurn: 1, endless: true, latencyMs: 8000, text: EVERY_TURN_BLOCK },
  blockturns: { callsPerTurn: 1, endless: true, text: EVERY_TURN_BLOCK },
  blockcost: { callsPerTurn: 1, endless: true, text: EVERY_TURN_BLOCK,
               usage: { input: 0, output: 9000, cache_creation: 60000, cache_read: 120000 } },
};

export function scriptedTransport({ latencyMs = 700, scenario = '1' } = {}) {
  const s = SCENARIOS[scenario] || null;
  if (s) return cappedTransport({ ...s, latencyMs: s.latencyMs || latencyMs });

  const script = scenario === 'noblock' ? [...TURNS.slice(0, -1), NO_BLOCK_FINAL]
    : scenario === 'named' ? [...TURNS.slice(0, -1), NAMED_FINAL]
    : scenario === 'credited' ? [...TURNS.slice(0, -1), CREDITED_FINAL]
    : scenario === 'oos' ? [...TURNS.slice(0, -1), OUT_OF_SCOPE_FINAL]
    : scenario === 'late' ? [...TURNS.slice(0, 4), ...LATE_BLOCK]
    : scenario === 'unclosed' ? [...TURNS.slice(0, -1), UNCLOSED_FINAL]
    : scenario === 'empty' ? [...TURNS.slice(0, -1), EMPTY_FINAL]
    : TURNS;

  let i = 0;
  return {
    buildRequest,
    async send({ body }) {
      const turn = script[Math.min(i, script.length - 1)];
      i += 1;
      // A real turn takes seconds. Pausing here is what makes the streaming
      // visible while developing; without it every turn lands at once.
      await wait(latencyMs);

      const content = [];
      if (turn.thinking) content.push({ type: 'thinking', summary: turn.thinking });
      if (turn.text) content.push({ type: 'text', text: turn.text });
      turn.calls.forEach(([name, input], n) => {
        content.push({ type: 'tool_use', id: `dev_${i}_${n}`, name, input });
      });

      return {
        id: `msg_dev_${i}`,
        model: body.model,
        stop_reason: turn.stop,
        stop_details: null,
        content,
        text: turn.text || '',
        thinking: turn.thinking || '',
        tool_calls: content.filter(b => b.type === 'tool_use')
          .map(b => ({ id: b.id, name: b.name, input: b.input })),
        usage: {
          input: i === 1 ? 1840 : 12,
          output: 260 + turn.calls.length * 90,
          cache_creation: i === 1 ? 3600 : 900,
          cache_read: i === 1 ? 0 : 3600 + (i - 2) * 1400,
        },
      };
    },
  };
}

/* A transport that never volunteers an ending, so the only thing that can
   stop it is a ceiling in the loop or the visitor pressing Stop. If a run
   against this one finishes, something enforced it. */
function cappedTransport({ callsPerTurn, latencyMs, usage, text = '' }) {
  let i = 0;
  return {
    buildRequest,
    async send({ body, signal }) {
      i += 1;
      await waitOrAbort(latencyMs, signal);

      const content = [{
        type: 'thinking',
        summary: `Scripted turn ${i}. This transport never returns end_turn, so ` +
          `whatever ends this run is a ceiling and not the model.`,
      }];
      if (text) content.push({ type: 'text', text });
      for (let n = 0; n < callsPerTurn; n += 1) {
        content.push({
          type: 'tool_use', id: `dev_${i}_${n}`,
          name: 'get_shap_ranking', input: { top_n: 6 },
        });
      }

      return {
        id: `msg_dev_${i}`,
        model: body.model,
        stop_reason: 'tool_use',
        stop_details: null,
        content,
        text,
        thinking: content[0].summary,
        tool_calls: content.filter(b => b.type === 'tool_use')
          .map(b => ({ id: b.id, name: b.name, input: b.input })),
        usage: usage
          ? { ...usage }
          : { input: i === 1 ? 1840 : 12, output: 300,
              cache_creation: i === 1 ? 3600 : 900,
              cache_read: i === 1 ? 0 : 3600 + (i - 2) * 1400 },
      };
    },
  };
}

/* The real adapter passes the signal to fetch, which rejects with an
   AbortError. The scripted one has to raise the same thing itself, or Stop
   would look like it worked here and not in a real run. */
function waitOrAbort(ms, signal) {
  return new Promise((resolve, reject) => {
    if (signal && signal.aborted) return reject(abortError());
    const timer = setTimeout(() => {
      if (signal) signal.removeEventListener('abort', onAbort);
      resolve();
    }, ms);
    function onAbort() { clearTimeout(timer); reject(abortError()); }
    if (signal) signal.addEventListener('abort', onAbort, { once: true });
  });
}

function abortError() {
  const err = new Error('The request was aborted.');
  err.name = 'AbortError';
  return err;
}
