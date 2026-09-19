/* The scan page: choose a model, run the agent, watch it work.
 *
 * All three screens. Screen 3 is rendered by agent/screen3.js from the
 * run's own record. This file loads the answer key for it only after the
 * run has ended, and never passes it the current deal.
 *
 * The key lives in this module's `apiKey` variable and nowhere else. It is
 * read from the field when a run starts, passed to the loop, and dropped
 * when the tab closes. No storage, no URL, no event.
 */

import { MODELS, getModel, costOf, retirementWarning, DEFAULT_MODEL_ID, PRICES_CHECKED } from './agent/models.js';
import { ToolLayer } from './agent/tools.js';
import {
  runReactLoop, Events, renderSystemPrompt, TERMINATION_SENTENCE,
  COMPLETED, TRUNCATED, REFUSAL, PAUSED, STOP_SEQUENCE, UNKNOWN_STOP,
  TURN_LIMIT, CALL_LIMIT, COST_LIMIT, STOPPED, ABORTED, FAILED,
} from './agent/loop.js';
import { buildRequest } from './agent/provider.js';
import { thesisChart, renderResult } from './agent/viz.js';
import { scoreRun, render as renderScreen3 } from './agent/screen3.js';
import { buildRecord, remember, recall, forget, download, view } from './agent/runfile.js';
import { readVerdict, finishedWithout, NO_TEXT } from './agent/verdict.js';
import { TRAIN_YEARS, TEST_YEAR } from './agent/pipeline.js';
import { count, word } from './agent/words.js';
import { spendStopSentence, spentApart } from './agent/ceilings.js';

const DATA = 'data/tools';
const PARAMS = new URLSearchParams(location.search);
const DEV = PARAMS.has('dev');
/* Which scripted transport dev mode uses. Only the caps are hard to reach
   with the ordinary script, which completes in six turns, so there is a
   scenario per cap. Meaningless without ?dev. */
const DEV_SCENARIO = PARAMS.get('dev') || '1';

/* The ceiling a visitor starts with, and the range they may move it to.
   A recorded run of this agent costs about $0.35 at Sonnet 5 rates, so a
   dollar is roughly three times a normal run: high enough that an ordinary
   audit never trips it, low enough to cut the theoretical worst case by
   about five times. */
const DEFAULT_CEILING = 1.00;
const MIN_CEILING = 0.05;
const MAX_CEILING = 20.00;

/* Anthropic keys begin with this and are far longer than anything typed by
   accident. The check exists to save a round trip on an obvious mistake —
   a truncated paste, the wrong field — and nothing more. It is deliberately
   loose: the API is the authority on whether a key is good, and a format
   that drifts must not lock a valid key out of the page. */
const KEY_PREFIX = 'sk-ant-';
const KEY_MIN_LENGTH = 40;

const $ = id => document.getElementById(id);

function el(tag, attrs = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'class') n.className = v;
    else if (k === 'text') n.textContent = v;
    else n.setAttribute(k, v);
  }
  for (const kid of kids.flat()) {
    if (kid === null || kid === undefined || kid === false) continue;
    n.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return n;
}

/* Fractions of a cent matter at the start of a run and stop mattering once
   there are whole dollars on the meter; a ceiling shown as "$1.000" reads
   like a token count rather than money. */
const money = v => {
  if (v < 0.01) return `$${v.toFixed(4)}`;
  if (v < 1) return `$${v.toFixed(3)}`;
  return `$${v.toFixed(2)}`;
};
const num = v => Number(v).toLocaleString('en-US');
/* "2026-09-19" as "19 September 2026". Read and written in UTC, so the day
   shown is the day in the string whatever the visitor's time zone. */
const longDate = iso => new Date(`${iso}T00:00:00Z`).toLocaleDateString('en-GB',
  { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });

async function getJSON(path) {
  const res = await fetch(path, { cache: 'no-cache' });
  if (!res.ok) throw new Error(`${path} could not be loaded (${res.status}).`);
  return res.json();
}

/* ------------------------------------------------------------------ boot */

let prompts, schemas, manifest, runIndex;
/* Loaded lazily, after a run ends. The answer key has no business in
   memory while the agent is working; the tools cannot reach it either way,
   but not having it there at all is cheaper than arguing that it is safe. */
let scoringData = null;
/* Every event of the current run, kept so the downloadable record can be
   built from them. The loop's return value carries less. */
let captured = null;
let lastRecord = null;
/* Whether Screen 2 holds lastRecord's turn-by-turn view. A run started on
   this page streams into it; a run restored after a reload does not, and
   Screen 2 says so. Screen 3 reads this same flag, so it never points the
   visitor at a view that isn't there. */
let turnViewShown = false;
/* Which card is which model is decided here, once, at random, and is never
   written to the page. The visitor is not told, and neither is anything
   they could read without opening the console on purpose. */
let assignment;
let chosenCard = null;
let running = false;
/* Set by the Stop control, read by the loop once per turn. Two stages: the
   first click lets the turn that is already paid for finish, the second
   aborts the request in flight. */
let stopRequested = false;
let controller = null;
/* Set when a click was refused, cleared when the run can actually start.
   Without it the live check — which fires on focus, and focus is exactly
   what refusing does — would overwrite the refusal a few milliseconds
   after showing it. */
let refused = false;

async function boot() {
  [prompts, schemas, manifest, runIndex] = await Promise.all([
    getJSON(`${DATA}/system_prompt.json`),
    getJSON(`${DATA}/tool_schemas.json`),
    getJSON(`${DATA}/manifest.json`),
    getJSON('data/runs/index.json'),
  ]);

  assignment = Math.random() < 0.5 ? ['layer1', 'canary'] : ['canary', 'layer1'];

  /* The field's bounds and starting value come from the same constants
     readCeiling() checks against, so the two can't disagree. */
  const field = $('ceiling');
  field.min = String(MIN_CEILING);
  field.max = String(MAX_CEILING);
  // A value the browser restored on reload is the visitor's, and is kept.
  if (!field.value) field.value = DEFAULT_CEILING.toFixed(2);

  renderThesis();
  renderChoices();
  renderModelSelect();
  wireControls();
}

/* --------------------------------------------------------------- screen 1 */

function renderThesis() {
  const f = prompts.figures_by_variant;
  $('thesis-chart').replaceChildren(
    thesisChart(f.canary.test_roc_auc, f.layer1.test_roc_auc,
                f.canary.test_roc_auc_text, f.layer1.test_roc_auc_text));
  $('thesis-cap').textContent =
    `One credit-default model, scored the same way on the same held-out ${TEST_YEAR} ` +
    `loans, with and without a single column that could only be known after ` +
    `the loan had already gone bad. ${f.canary.test_roc_auc_text} is what ` +
    `leakage buys you; ${f.layer1.test_roc_auc_text} is what it is actually worth. ` +
    `That is the difference a candidate below may be hiding.`;
}

function renderChoices() {
  const counts = Object.values(manifest.variants).map(v => v.features).sort((a, b) => a - b);
  const featureText = [...new Set(counts)].join(' or ');
  const box = $('choices');
  box.replaceChildren(...['A', 'B'].map(letter => {
    const card = el('button', {
      class: 'choice', type: 'button', 'aria-pressed': 'false', 'data-card': letter,
      'aria-label': `Candidate ${letter}, a credit-default model under audit` },
      el('div', { class: 'choice-top' },
        el('h3', { text: `Candidate ${letter}` }),
        el('span', { class: 'choice-state', text: 'not selected' })),
      el('p', { class: 'kind', text: 'Credit-default model — the thing under audit' }),
      el('p', { text: `Gradient-boosted, fitted on ${TRAIN_YEARS} loans and scored once ` +
        `on ${TEST_YEAR} loans held back from fitting.` }),
      el('dl', {},
        el('dt', { text: 'features' }), el('dd', { text: featureText }),
        el('dt', { text: 'trained' }), el('dd', { text: TRAIN_YEARS }),
        el('dt', { text: 'held out' }), el('dd', { text: String(TEST_YEAR) }),
        el('dt', { text: 'leak' }), el('dd', { text: 'not stated' })));
    card.addEventListener('click', () => selectCard(letter));
    return card;
  }));
}

function selectCard(letter) {
  chosenCard = letter;
  for (const card of document.querySelectorAll('.choice')) {
    const on = card.dataset.card === letter;
    card.setAttribute('aria-pressed', String(on));
    card.querySelector('.choice-state').textContent = on ? 'selected' : 'not selected';
  }
  refreshGo();
}

/* A run's likely cost, taken from a recorded run rather than guessed.
   run11-honest-cached is the one that used prompt caching, which this page
   also uses, so its split across fresh, written and read tokens is the
   right shape to price. */
function representativeUsage() {
  const runs = runIndex.runs;
  const run11 = runs.find(r => r.prompt_caching && r.termination === COMPLETED);
  if (run11) return { usage: run11.usage_totals, label: run11.label };
  const done = runs.filter(r => r.termination === COMPLETED);
  return done.length ? { usage: done[0].usage_totals, label: done[0].label } : null;
}

function renderModelSelect() {
  const sel = $('model');
  const rep = representativeUsage();
  sel.replaceChildren(...MODELS.map(m => {
    const cost = rep ? ` — about ${money(costOf(m, rep.usage))} a run` : '';
    return el('option', { value: m.id, selected: m.id === DEFAULT_MODEL_ID || null },
      `${m.label}${cost}`);
  }));
  sel.value = DEFAULT_MODEL_ID;
  updateModelNote();
  sel.addEventListener('change', updateModelNote);
}

function updateModelNote() {
  const m = getModel($('model').value);
  const rep = representativeUsage();
  const note = $('price-note');
  if (rep) {
    note.textContent =
      `${m.label}: $${m.price.input}/MTok in, $${m.price.output}/MTok out, ` +
      `$${m.price.cacheRead}/MTok on cache hits, as Anthropic's pricing page listed ` +
      `them on ${longDate(PRICES_CHECKED)}. The figure above prices ` +
      `${rep.label}, a recorded run of this agent, at those rates — ` +
      `${num(rep.usage.input + rep.usage.cache_creation + rep.usage.cache_read)} input ` +
      `and ${num(rep.usage.output)} output tokens. Your run will differ. ` +
      `You are billed by Anthropic directly.`;
  } else {
    note.textContent = `${m.label}: $${m.price.input}/MTok in, $${m.price.output}/MTok out, ` +
      `as Anthropic's pricing page listed them on ${longDate(PRICES_CHECKED)}.`;
  }
  const warn = retirementWarning(m);
  const banner = $('retire');
  banner.hidden = !warn;
  if (warn) banner.replaceChildren(el('b', { text: 'Heads up. ' }), warn);
}

function wireControls() {
  /* A value can reach a field without an `input` event: a password manager
     writing it in, the browser restoring it on reload, or anything setting
     .value directly. Binding only `input` left the page believing an
     obviously-filled field was empty, with a dead button and no explanation.
     So every event that can follow a value arriving is bound, the check is
     run once after boot for values that were already there, and again when
     the window regains focus, which is when an autofill usually lands. */
  for (const type of ['input', 'change', 'paste', 'blur', 'focus']) {
    $('key').addEventListener(type, () => refreshGo());
  }
  $('model').addEventListener('change', refreshGo);
  $('model').addEventListener('change', updateCeilingNote);
  for (const type of ['input', 'change', 'blur']) {
    $('ceiling').addEventListener(type, () => { updateCeilingNote(); refreshGo(); });
  }
  window.addEventListener('focus', refreshGo);
  $('go').addEventListener('click', start);
  $('stop').addEventListener('click', requestStop);
  $('see-score').addEventListener('click', () => {
    if (lastRecord) showScreen3(lastRecord);
  });
  for (const id of ['download-run', 'download-run-2']) {
    const b = $(id);
    if (b) b.addEventListener('click', () => { if (lastRecord) download(lastRecord); });
  }
  $('back-to-run').addEventListener('click', () => {
    $('screen3').hidden = true;
    $('screen2').hidden = false;
  });
  $('back').addEventListener('click', () => {
    if (running) return;
    $('screen2').hidden = true;
    $('screen1').hidden = false;
  });

  /* A reload mid-run cannot leave the loop running — the context dies with
     the page — but the turn in flight has already been paid for and its
     answer would be lost. Worth one confirmation. */
  window.addEventListener('beforeunload', e => {
    if (!running) return;
    e.preventDefault();
    e.returnValue = '';
  });

  updateCeilingNote();

  /* A run kept from before this reload. It is restored whole, and its own
     variant travels with it, so the reveal is about the run that happened
     rather than the deal made a moment ago at boot. */
  const kept = recall();
  if (kept) {
    lastRecord = kept;
    turnViewShown = false;
    $('screen2').hidden = false;
    $('run-title').textContent = runTitle(kept.facts.candidate, view(kept));
    $('run-sub').textContent =
      `Restored from this tab \u2014 the turn-by-turn view is not re-shown.`;
    $('stream').replaceChildren(el('p', { class: 'note', text:
      'This run was kept when the page reloaded. The turn-by-turn view is not ' +
      'restored, but the record is: what came of the run is on the next screen, ' +
      'and the record can be downloaded.' }));
    $('meters').replaceChildren();
    offerKeep(kept, true);
  }

  if (DEV) {
    $('key').value = 'dev-mode-no-key-needed';
    $('key').placeholder = 'dev mode — scripted transport, nothing is sent';
    selectCard('A');
  }
  // Values present before any event fired — restored, autofilled, or set by
  // an extension — are only noticed if the check runs at least once here.
  refreshGo();
}

/* What is still missing, in the order the visitor meets it. Empty means the
   run may start. This is the single source of truth for both the standing
   line and the check on click. */
function missingSteps() {
  const missing = [];
  if (!chosenCard) missing.push({ step: 'candidate', say: 'choose a candidate to audit, A or B' });

  const ceiling = readCeiling();
  if (ceiling === null) {
    missing.push({ step: 'auditor',
      say: `set a spend ceiling between $${MIN_CEILING.toFixed(2)} and $${MAX_CEILING.toFixed(2)}` });
  }

  const key = $('key').value.trim();
  if (!key) {
    missing.push({ step: 'key', say: 'enter your API key' });
  } else if (!DEV && !looksLikeKey(key)) {
    /* Named separately from "no key" so the visitor is told what is wrong
       with the one they have, rather than being told to enter the key that
       is plainly already in the field. */
    missing.push({ step: 'key',
      say: `check your API key — it should start with "${KEY_PREFIX}" and be much longer` });
  }
  return missing;
}

function looksLikeKey(key) {
  return key.startsWith(KEY_PREFIX) && key.length >= KEY_MIN_LENGTH && !/\s/.test(key);
}

/* The ceiling as a number, or null if the field does not hold a usable one.
   Null is a missing step, never a silent fallback to the default: a run must
   not proceed under a ceiling the visitor did not see. */
function readCeiling() {
  const raw = $('ceiling').value.trim();
  if (!raw) return null;
  const v = Number(raw);
  if (!Number.isFinite(v) || v < MIN_CEILING || v > MAX_CEILING) return null;
  return v;
}

function updateCeilingNote() {
  const v = readCeiling();
  const m = getModel($('model').value);
  const rep = representativeUsage();
  const note = $('ceiling-note');
  if (v === null) {
    note.textContent =
      `Enter a ceiling between $${MIN_CEILING.toFixed(2)} and $${MAX_CEILING.toFixed(2)}.`;
    return;
  }
  const typical = rep ? costOf(m, rep.usage) : null;
  const compare = typical
    ? ` A recorded run of this agent costs about ${money(typical)} at these rates, ` +
      `so this is roughly ${(v / typical).toFixed(1)}× a normal run.`
    : '';
  /* The gate is spend >= ceiling, tested between turns. A turn in flight
     is never cut short, so the run can only stop after the total has
     reached the ceiling, never before. */
  note.textContent =
    `Checked after every turn, before the next request is sent. A turn already ` +
    `under way is always finished, so the run stops at the first check where the ` +
    `total has reached ${money(v)}, and the final figure can pass it by up to the ` +
    `cost of that last turn. The total is an estimate, priced from the token counts ` +
    `the API reports at the rates above. Anthropic's bill is the real figure.${compare}`;
}

/* Mark the incomplete steps in the panel, or clear every mark. */
function markSteps(steps) {
  for (const node of document.querySelectorAll('[data-step]')) {
    node.dataset.stepState = steps.includes(node.dataset.step) ? 'missing' : 'ok';
  }
}

/* The button is never disabled. A disabled control that does not say why is
   its own bug, and keeping it enabled means the check runs at the moment it
   matters — on click — rather than depending on having bound every event
   that could possibly put a value in a field. This line is live feedback;
   it is not what stops a bad run. start() is. */
function refreshGo() {
  const missing = missingSteps();
  const why = $('go-why');
  if (!why) return;
  if (running) {
    why.textContent = 'Running\u2026';
    why.dataset.state = 'busy';
  } else if (missing.length && refused) {
    // Keep the refusal up, but let it shrink as steps get completed.
    why.textContent = `Nothing was sent. First, ${missing.map(m => m.say).join(', and ')}.`;
    why.dataset.state = 'refused';
    markSteps(missing.map(m => m.step));
  } else if (missing.length) {
    why.textContent = `Still needed: ${missing.map(m => m.say).join(', and ')}.`;
    why.dataset.state = 'blocked';
  } else {
    why.textContent = `Ready. This will send requests to Anthropic with your key, ` +
      `one per turn, for at most ${count(MAX_TURNS, 'turn')}.`;
    why.dataset.state = 'ready';
    refused = false;
    markSteps([]);
  }
}

/* ------------------------------------------------------------------ stop */

/* First click: stop after the turn now in flight, which is already bought
   and whose answer is worth rendering. Second click: abort that request
   too. Both are offered because "stop" means different things depending on
   whether the visitor is out of patience or out of money. */
function requestStop() {
  if (!running) return;
  if (!stopRequested) {
    stopRequested = true;
    $('stop').textContent = 'Stop now, without waiting';
    $('stop').dataset.armed = 'hard';
    $('stop-why').textContent =
      'Stopping. No further request will be sent. A request already in flight ' +
      'is paid for, so it is allowed to finish and be shown.';
    $('stop-why').dataset.state = 'refused';
    return;
  }
  if (controller) controller.abort();
  $('stop').disabled = true;
  $('stop-why').textContent = 'Cancelled mid-request. That turn may still be billed.';
}

function showStop(on) {
  $('stop-row').hidden = !on;
  if (!on) return;
  $('stop').disabled = false;
  $('stop').textContent = 'Stop the run';
  delete $('stop').dataset.armed;
  $('stop-why').textContent = 'Ends the run at the end of the current turn.';
  $('stop-why').dataset.state = 'busy';
}

/* --------------------------------------------------------------- screen 2 */

const meters = {
  turns: 0, calls: 0, spend: 0,
  usage: { input: 0, output: 0, cache_creation: 0, cache_read: 0 },
};
let model;
let ceiling = DEFAULT_CEILING;
let turnCards = new Map();

function resetMeters() {
  meters.turns = 0;
  meters.calls = 0;
  meters.spend = 0;
  meters.usage = { input: 0, output: 0, cache_creation: 0, cache_read: 0 };
  turnCards = new Map();
}

function paintMeters() {
  const inputSide = meters.usage.input + meters.usage.cache_creation + meters.usage.cache_read;
  const cells = [
    ['turns', meters.turns, model ? `of ${MAX_TURNS}` : ''],
    ['tool calls', meters.calls, `of ${MAX_CALLS}`],
    ['input tokens', num(inputSide), `${num(meters.usage.cache_read)} from cache`],
    ['output tokens', num(meters.usage.output), ''],
    ['estimated cost', spentApart(meters.spend, ceiling, money), `ceiling ${money(ceiling)}`],
  ];
  $('meters').replaceChildren(...cells.map(([k, v, s]) =>
    el('div', { class: 'meter' },
      el('div', { class: 'k', text: k }),
      el('div', { class: 'v', text: String(v) }),
      el('div', { class: 's', text: s }))));
}

/* A turn that ends without a turn:finished — an abort mid-request, or a
   fatal error — leaves its card reading "working" and a line saying the
   model is still being waited for, on a run that is over. Rather than
   patching the two paths that can do that, every card still claiming to be
   working is corrected here, once, when the run ends. A new way to exit the
   loop cannot reintroduce it. */
function closeOpenTurns(e) {
  for (const t of turnCards.values()) {
    if (t.waiting) { t.waiting.remove(); t.waiting = null; }
    const status = t.head.querySelector('.status');
    if (status && status.textContent === 'working') {
      status.textContent = e.termination === ABORTED ? 'cancelled' : 'not finished';
    }
  }
}

function turnCard(turn) {
  if (turnCards.has(turn)) return turnCards.get(turn);
  const body = el('div', { class: 'evt-body' });
  const head = el('div', { class: 'evt-head' },
    el('span', { text: `Turn ${turn}` }),
    el('span', { class: 'status', text: 'working' }));
  const card = el('div', { class: 'evt' }, head, body);
  $('stream').append(card);
  const entry = { card, head, body, calls: new Map() };
  turnCards.set(turn, entry);
  card.scrollIntoView({ block: 'end', behavior: 'smooth' });
  return entry;
}

/* 30, not 20. The recorded honest runs — the ones with nothing to find, so
   the agent keeps looking — completed in 11, 14, 16 and 16 turns, and
   run9-honest-nopop hit a 20-turn ceiling and was scored as no answer at
   all. 20 leaves almost no margin for the case this benchmark is mostly
   about. 30 is not a new configuration: run10-honest-nopop-30turns ran
   under exactly this ceiling and finished in 12.

   The number reaches the agent through {max_turns} in the system prompt,
   so the brief it reads always states the ceiling actually enforced. */
const MAX_TURNS = 30;
const MAX_CALLS = 70;

function attach(events) {
  /* Every event, in order, so the record can be built from them later. The
     loop's return value carries the totals but not the transcript. */
  events.on('*', e => { if (captured) captured.list.push(e); });

  events.on('run:started', e => {
    resetMeters();
    $('stream').replaceChildren();
    $('run-title').textContent = `Auditing Candidate ${chosenCard}`;
    $('run-sub').textContent =
      `Auditor: ${e.model.label} · ceilings ${count(e.config.maxTurns, 'turn')}, ` +
      `${count(e.config.maxToolCalls, 'tool call')} and ${money(e.config.maxCost)} · prompt caching ` +
      `${e.config.cache ? 'on' : 'off'} · retrieval ${e.config.retrieval}` +
      (DEV ? ' · DEV MODE, scripted replies, nothing sent' : '');
    paintMeters();
  });

  events.on('turn:started', e => {
    const t = turnCard(e.turn);
    t.waiting = el('p', { class: 'call-wait', text: 'waiting for the model…' });
    t.body.append(t.waiting);
  });

  events.on('reasoning', e => {
    const t = turnCard(e.turn);
    t.body.append(el('div', { class: 'think', text: e.text }));
  });

  events.on('text', e => {
    const t = turnCard(e.turn);
    t.body.append(el('div', { class: 'say', text: e.text }));
  });

  events.on('model:replied', e => {
    const t = turnCard(e.turn);
    if (t.waiting) { t.waiting.remove(); t.waiting = null; }
    meters.turns = e.turn;
    // Taken from the loop's own counters rather than tallied again here, so
    // the figure on screen is the one the ceiling is tested against.
    meters.usage = { ...e.usageTotal };
    meters.spend = e.spend;
    paintMeters();
  });

  events.on('tool:called', e => {
    const t = turnCard(e.turn);
    const slot = el('div', { class: 'viz' },
      el('p', { class: 'call-wait', text: 'running…' }));
    const call = el('div', { class: 'call' },
      el('div', { class: 'call-head' },
        el('span', { class: 'call-name', text: e.name }),
        el('span', { class: 'call-args', text: JSON.stringify(e.input) })),
      slot);
    t.calls.set(e.id, slot);
    t.body.append(call);
    call.scrollIntoView({ block: 'end', behavior: 'smooth' });
  });

  events.on('tool:returned', e => {
    const t = turnCard(e.turn);
    const slot = t.calls.get(e.id);
    meters.calls = e.index;
    paintMeters();
    if (!slot) return;
    slot.replaceChildren(renderResult(e.name, e.result));
  });

  events.on('turn:finished', e => {
    const t = turnCard(e.turn);
    if (t.waiting) { t.waiting.remove(); t.waiting = null; }
    t.head.querySelector('.status').textContent =
      `${e.stopReason}${e.toolCallsThisTurn ? ` · ${count(e.toolCallsThisTurn, 'call')}` : ''}`;
  });

  events.on('run:aborted', e => {
    $('stream').append(el('div', { class: 'banner bad' },
      el('b', { text: 'Cancelled. ' }),
      `The request for turn ${e.turn} was abandoned in flight. It may still be ` +
      `billed by Anthropic.`));
  });

  events.on('error', e => {
    $('stream').append(el('div', { class: 'banner bad' },
      el('b', { text: 'The run stopped. ' }), e.message));
  });

  /* Anything that throws while the ending is drawn is shown, not left to
     the console. Events.emit catches a handler's error and logs it, which
     on its own would leave the stream with no banner and the title still
     saying the audit is running. */
  events.on('run:finished', e => {
    try {
      showEnding(e);
    } catch (err) {
      $('stream').append(el('div', { class: 'banner bad' },
        el('b', { text: 'This run’s ending could not be shown. ' }),
        `The page refused rather than guess: ${err.message} `,
        el('b', { text: 'Nothing here is a verdict on this candidate.' })));
      $('run-title').textContent = `Candidate ${chosenCard} — ending not shown`;
    }
  });
}

/* The banner and title for a run that has ended. */
function showEnding(e) {
  meters.spend = e.spend;
  meters.usage = { ...e.usage };
  paintMeters();
  closeOpenTurns(e);
  const bits = [count(e.turns, 'turn'), count(e.toolCalls, 'tool call'),
    `${spentApart(e.spend, e.config.maxCost, money)} spent against a ` +
    `${money(e.config.maxCost)} ceiling`];

  /* The same call Screen 3 makes, on the same final answer, so the banner
     can't announce a result that the score then refuses. */
  const verdict = readVerdict(e.finalText, e.termination, prompts.answer_format);
  if (verdict.scoreable) {
    $('stream').append(el('div', { class: 'banner' },
      el('b', { text: 'Run finished. ' }),
      // The sentence, not the enum. "turn_limit" is a value in a record,
      // not something to put in front of a visitor on its own.
      `${e.reason} ${bits.join(' · ')}. `,
      'Press “See how it scored” below to find out which candidate this was.'));
    $('run-title').textContent = runTitle(chosenCard, e);
    return;
  }

  /* No findings block. The run bought an investigation and not an answer,
     and the two look almost identical on screen — a wall of turns, then a
     banner. The difference has to be stated, not implied, or a visitor
     reads a truncation as a result. The scorer that graded the twelve
     recorded runs draws exactly this line. */
  $('stream').append(el('div', { class: 'banner bad verdictless' },
    el('b', { text: 'No verdict. ' }),
    noVerdictCause(e, verdict.missing),
    e.termination === COMPLETED
      /* True whether or not a block appeared in an earlier turn. With no
         final answer there is no "before it" to speak of. */
      ? verdict.missing === NO_TEXT ? ''
        : ' Only the final answer is scored, as it was for the recorded runs, so ' +
          'anything written before it, above, does not count.'
      : ' ' + (e.turns === 0
        ? NO_REPLY[e.termination] ?? 'The model never replied, so this run produced no result.'
        /* Not "never reached its findings": a run cut off after writing a
           complete block has them, and they still don't count. */
        : 'The run did not finish, so it produced no result. Only a run the agent ' +
          'ends itself is scored, as it was for the recorded runs, so nothing above ' +
          'counts, including any findings it wrote.'),
    el('b', { text: ' It is not a verdict on this candidate and must not be read as one.' }),
    el('p', { class: 'viz-note', text:
      /* The scorer refuses these two kinds of run for different reasons, in
         different words (agent/eval_canary.py). A run that finished but left
         no block is a parse failure. A run that didn't finish is refused
         before parsing. */
      (e.turns === 0
        ? 'With no reply from the model there is nothing for the scorer to grade. '
        : e.termination === COMPLETED
          ? `The scorer that graded the ${word(runIndex.runs.length)} recorded runs ` +
            `does not score a run like this one: ` +
            (verdict.missing === NO_TEXT
              ? `with no final answer there was nothing to parse, `
              : `the final answer could not be parsed, `) +
            `which it calls a parse failure, not a finding of nothing to report. `
          : `The scorer that graded the ${word(runIndex.runs.length)} recorded runs ` +
            `refuses a run like this one: a partial answer is not an answer and is ` +
            `not scored. `) +
      `${bits.join(' · ')}.` +
      (e.termination === ABORTED ? ` ${NOT_COUNTED}` : '') })));
  $('run-title').textContent = runTitle(chosenCard, e);
}

/* Screen 2's title for a finished run, live or restored after a reload.
   Whether there was a verdict is readVerdict's answer, the same one the
   banner and Screen 3 act on, so a restored run can't be titled as audited
   when it has no verdict. */
function runTitle(card, { termination, turns, finalText }) {
  if (readVerdict(finalText, termination, prompts.answer_format).scoreable) {
    return `Audited Candidate ${card}`;
  }
  if (termination === COMPLETED) return `Candidate ${card} — no verdict`;
  if (turns === 0) return `Candidate ${card} — no turn completed`;
  return `Candidate ${card} — audit cut off`;
}

/* A run can end before the model has replied once in three ways and no
   others. The first request can fail, or fail to be built. The visitor can
   cancel it in flight with a second press of Stop. Or they can press Stop
   while the page is still loading, before the first request goes. The
   ceilings can't end a run at zero turns: the turn ceiling is MAX_TURNS, and
   a spend ceiling is at least MIN_CEILING while a run with no reply has spent
   nothing. Every other ending needs a reply. On these runs nothing was
   investigated, so no sentence may say that anything was cut off, that a
   partial answer exists, or that the visitor paid for a turn.

   A failed or cancelled run did start turn 1, and its card says so ("not
   finished", "cancelled"). What it never got was a reply, which is the true
   thing to say in both cases, and for a request that was never built. */
const NO_REPLY = {
  [FAILED]: 'The agent never got a reply to its first request, so it never looked ' +
    'at anything and this run produced no result.',
  [ABORTED]: 'That was the agent’s first request, so it never got a reply, never ' +
    'looked at anything, and this run produced no result.',
  [STOPPED]: 'That was before its first request was sent, so nothing was sent and ' +
    'nothing was spent.',
};

/* The cost on the page is priced from usage the API reported. A request
   cancelled in flight never reports any, so it is missing from the figure
   whether or not it is billed. */
const NOT_COUNTED = 'The cancelled request is not in that figure, and may still be billed.';

/* Why this run has no verdict, naming the ceiling that actually stopped it
   with the number that was in force. A visitor who hit a limit should be
   able to see which one and what it was set to, without reading a record. */
function noVerdictCause(e, missing) {
  const c = e.config || {};
  switch (e.termination) {
    case TURN_LIMIT:
      return `The run was stopped at its ceiling of ${count(c.maxTurns, 'turn')}, ` +
        `before it could send another request.`;
    /* The call gate runs before a batch, so a run can stop short of the
       ceiling: ?dev=calls stops at 68 of 70, because its next batch asks
       for four. */
    case CALL_LIMIT:
      return `The run stopped at ${count(e.toolCalls, 'tool call')}: the model asked ` +
        `for a batch that would have taken it past the ceiling of ${c.maxToolCalls}, ` +
        `so that batch was not run.`;
    /* The spend gate runs after a turn, so the total is at or past the
       ceiling by the time it stops, never short of it. */
    case COST_LIMIT:
      return spendStopSentence(e.spend, c.maxCost, money);
    case STOPPED:
      return 'You stopped the run.';
    case ABORTED:
      return 'You cancelled the run while a request was in flight.';
    case TRUNCATED:
      return `One turn hit the per-request output ceiling of ` +
        `${num(model.maxTokens)} tokens and was cut off mid-sentence.`;
    case REFUSAL:
      return 'The model declined to continue.';
    case PAUSED:
      return 'The model paused the turn and the run was not resumed.';
    case STOP_SEQUENCE:
      return 'The model stopped on a stop sequence.';
    case UNKNOWN_STOP:
      return 'The model stopped for a reason this page does not recognise.';
    case FAILED:
      return 'The run stopped on an error, which is shown above.';
    case COMPLETED:
      return finishedWithout(missing);
    default:
      return e.reason;
  }
}

/* ----------------------------------------------------------- screen 3 */

/* Loaded only once a run is over. Nothing here is reachable by the tools,
   but keeping the answer key out of the page until the agent has finished
   costs nothing and leaves no argument to make. */
async function loadScoringData() {
  if (scoringData) return scoringData;
  const [scoring, index, layer1, canary, dictionary] = await Promise.all([
    getJSON('data/scoring.json'),
    getJSON('data/runs/index.json'),
    getJSON(`${DATA}/layer1/shap_global.json`),
    getJSON(`${DATA}/canary/shap_global.json`),
    getJSON(`${DATA}/dictionary.json`),
  ]);
  const canaryColumn = onlyCanaryColumn(scoring.canary);
  checkKeyColumnsRead(scoring.true_positives, layer1, canary, canaryColumn);
  scoringData = deepFreeze({
    scoring, index,
    /* Copies, not the shared object. `prompts` is also what Screens 1 and 2
       read, and freezing it here would make their behaviour depend on
       whether Screen 3 had loaded yet: a write that works before the first
       score throws after it. The freeze stays inside the boundary it
       protects. Screen 3 reads figures_by_variant and nothing else. */
    prompts: { figures_by_variant: structuredClone(prompts.figures_by_variant) },
    answerFormat: structuredClone(prompts.answer_format),
    documented: readOnlySet(dictionary.map(e => e.feature)),
    features: { layer1: layer1.map(r => r.feature), canary: canary.map(r => r.feature) },
    featureCounts: { layer1: layer1.length, canary: canary.length },
    keyCounts: {
      truePositives: scoring.true_positives.length,
      hardNegatives: scoring.hard_negatives.length,
    },
    canaryColumn,
    tpByColumn: Object.fromEntries(scoring.true_positives.map(t => [t.column, t])),
    scoredByLabel: Object.fromEntries(scoring.runs.map(r => [r.label, r])),
  });
  return scoringData;
}

/* The object Screen 3 renders from is cached and handed to every render, so
   anything written onto it outlives the call that wrote it and becomes an
   input nobody declared. `data.variant` was exactly that. Removing one such
   field does not stop the next, so the object is frozen all the way down: a
   write into it throws where it happens, on the published page as much as
   under ?dev, instead of quietly working.

   Children are frozen before parents, shared references are frozen once,
   and a Set or Map is refused outright rather than half-frozen —
   Object.freeze does not stop Set.prototype.add, so one left in here would
   be a hole that looks sealed. */
function deepFreeze(root) {
  const seen = new WeakSet();
  (function walk(value, path) {
    if (!value || typeof value !== 'object' || seen.has(value)) return;
    if (value instanceof Set || value instanceof Map) {
      throw new TypeError(`${path} is a ${value.constructor.name}, which ` +
        `Object.freeze cannot seal. Use readOnlySet, or a plain object.`);
    }
    seen.add(value);
    for (const [k, child] of Object.entries(value)) walk(child, `${path}.${k}`);
    Object.freeze(value);
  })(root, 'scoringData');
  return root;
}

/* Screen 3's copy says one column was put back, and means it. The key
   stores the canary as a map, so it could hold more than one. Rather than
   write text that renders whatever count it's given, the page refuses a
   key that doesn't hold exactly one. That can only happen if the bundle
   changes, so, like the Set guard below, it fails loudly and only a
   developer will see it. */
function onlyCanaryColumn(canary) {
  const columns = Object.keys(canary || {});
  if (columns.length !== 1) {
    throw new Error(`scoring.canary holds ${columns.length} columns ` +
      `(${columns.join(', ') || 'none'}). Screen 3 is written for exactly one.`);
  }
  return columns[0];
}

/* Screen 3 says the honest model reads none of the key's leaking columns
   and the canary model reads exactly one, the planted column. The sentences
   that say so ("none of them is among its inputs", "the other thirty-eight")
   depend on it, so the page checks it against the two feature lists instead
   of trusting it, and refuses to render if it doesn't hold. */
function checkKeyColumnsRead(truePositives, layer1, canary, canaryColumn) {
  const leaking = new Set(truePositives.map(t => t.column));
  const read = rows => rows.map(r => r.feature).filter(f => leaking.has(f));
  const honest = read(layer1);
  const planted = read(canary);
  if (honest.length !== 0 || planted.length !== 1 || planted[0] !== canaryColumn) {
    throw new Error(`Expected the honest model to read no key column and the canary ` +
      `model to read only ${canaryColumn}; they read [${honest.join(', ')}] and ` +
      `[${planted.join(', ')}]. Screen 3's copy is written for the first.`);
  }
}

/* A Set cannot be frozen, only replaced. parse.js asks one question of the
   dictionary's column names — is this one of them — so that is the whole
   interface, and the Set behind it is out of reach. */
function readOnlySet(items) {
  const set = new Set(items);
  return Object.freeze({ has: value => set.has(value) });
}

/* The record is the only thing passed in. screen3.js cannot see the current
   assignment, and the reveal reads record.variant. */
async function showScreen3(record) {
  /* A check that refuses to render (the canary columns, the key columns,
     a no-verdict kind with no sentence) throws. Uncaught, that was a click
     on "See how it scored" that did nothing at all. It has to be seen. */
  let body;
  try {
    const data = await loadScoringData();
    const run = view(record);
    const scored = scoreRun(run, data);
    body = renderScreen3(run, data, scored, { turnViewShown });
  } catch (err) {
    body = el('div', { class: 'banner bad' },
      el('b', { text: 'This run was not scored. ' }),
      `The page checks its own data before it scores anything, and it refused: ${err.message}`);
  }
  $('s3-body').replaceChildren(body);
  $('screen1').hidden = true;
  $('screen2').hidden = true;
  $('screen3').hidden = false;
  window.scrollTo({ top: 0 });
}

function offerKeep(record, stored) {
  lastRecord = record;
  $('s3-actions').hidden = false;
  const note = stored
    ? 'Kept in this tab, so a reload will not lose it. It goes when the tab closes.'
    : 'This tab will not keep the run \u2014 storage is unavailable here. Download it if you want it.';
  $('keep-note').textContent = note;
  $('keep-note').dataset.state = stored ? 'ready' : 'blocked';
  if ($('keep-note-2')) $('keep-note-2').textContent = note;
}

/* ------------------------------------------------------------------ run */

async function start() {
  if (running) {
    // Was a silent return. A second click on a button that stays clickable
    // has to say why nothing happened, for the same reason the disabled
    // state was removed.
    $('go-why').textContent = 'A run is already going. Stop it first, below.';
    $('go-why').dataset.state = 'refused';
    return;
  }

  /* The gate. Nothing above this point can reach the network, and nothing
     below it runs until both are present: no ToolLayer is loaded, no request
     is built, no key is read for sending. A missing step is refused here,
     named in the line under the button, and marked in the panel. */
  const missing = missingSteps();
  if (missing.length) {
    refused = true;
    markSteps(missing.map(m => m.step));
    const why = $('go-why');
    why.textContent = `Nothing was sent. First, ${missing.map(m => m.say).join(', and ')}.`;
    why.dataset.state = 'refused';
    const first = document.querySelector('[data-step-state="missing"]');
    if (first) {
      first.scrollIntoView({ block: 'center', behavior: 'smooth' });
      const focusable = first.querySelector('input, .choice');
      if (focusable) focusable.focus();
    }
    return;
  }

  const apiKey = $('key').value.trim();
  ceiling = readCeiling();
  refused = false;
  stopRequested = false;
  controller = new AbortController();
  captured = { list: [], opening: 'Begin your review.' };
  lastRecord = null;
  forget();
  $('s3-actions').hidden = true;
  markSteps([]);
  running = true;
  refreshGo();
  showStop(true);
  $('screen1').hidden = true;
  $('screen2').hidden = false;
  $('stream').replaceChildren(el('p', { class: 'status', text: 'Loading the model’s artefacts…' }));
  turnViewShown = true;

  model = getModel($('model').value);
  const variant = assignment[chosenCard === 'A' ? 0 : 1];

  try {
    const tools = await ToolLayer.load(DATA, variant, {});
    const figures = prompts.figures_by_variant[variant];
    const nFeatures = manifest.variants[variant].features;
    const system = renderSystemPrompt(prompts, {
      maxTurns: MAX_TURNS, maxToolCalls: MAX_CALLS, nFeatures, figures,
    });

    const events = new Events();
    attach(events);
    const startedAt = new Date();

    const result = await runReactLoop({
      apiKey, model, tools, toolSchemas: schemas, system,
      maxTurns: MAX_TURNS, maxToolCalls: MAX_CALLS, cache: true, events,
      maxCost: ceiling,
      priceUsage: u => costOf(model, u),
      shouldStop: () => stopRequested,
      signal: controller.signal,
      // Loaded only in dev, by dynamic import, from outside docs/. On the
      // published site this path does not resolve, which is deliberate:
      // dev mode cannot be switched on by a visitor.
      transport: DEV
        ? (await import('../verify/dev-transport.js')).scriptedTransport({ scenario: DEV_SCENARIO })
        : undefined,
    });

    /* The record carries its own variant. Everything downstream — the
       reveal, the score, the file — reads it from here, not from the
       assignment, which by then may have been dealt again. */
    const record = buildRecord({
      events: captured, result, model, card: chosenCard, variant,
      canaryPresent: variant === 'canary',
      system, toolConfig: tools.config,
      limits: { max_turns: MAX_TURNS, max_tool_calls: MAX_CALLS, max_cost_usd: ceiling },
      startedAt,
    });
    record.termination_sentence = result.reason;
    offerKeep(record, remember(record));
  } catch (err) {
    /* Reached only by a genuine failure of this page's own data or the API.
       The dev transport is behind the DEV flag below, so a visitor without
       ?dev can never see a message originating from that import. */
    $('stream').append(el('div', { class: 'banner bad' },
      el('b', { text: 'Could not start. ' }), err.message));
  } finally {
    running = false;
    controller = null;
    showStop(false);
    refreshGo();
  }
}

boot().catch(err => {
  $('screen1').replaceChildren(
    el('p', { class: 'status error', text: `This page could not load its data: ${err.message}` }));
});
