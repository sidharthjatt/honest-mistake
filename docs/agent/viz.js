export const BUILD = 'ed6b67583fac';
/* Tool results as pictures. Inline SVG, hand-built: no chart library, no
 * external request, nothing loaded at runtime. Colours come from the
 * stylesheet's custom properties so both themes work without a second
 * palette here.
 *
 * Every renderer takes the tool's own result object and reads the numbers
 * out of it. None of them holds a figure of its own.
 */

const NS = 'http://www.w3.org/2000/svg';

function svg(width, height, extra = {}) {
  const el = document.createElementNS(NS, 'svg');
  el.setAttribute('viewBox', `0 0 ${width} ${height}`);
  el.setAttribute('role', 'img');
  for (const [k, v] of Object.entries(extra)) el.setAttribute(k, v);
  return el;
}

function node(name, attrs = {}, text) {
  const el = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined) continue;
    el.setAttribute(k, String(v));
  }
  if (text !== undefined) el.textContent = String(text);
  return el;
}

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

const INK = 'var(--ink)';
const SOFT = 'var(--ink-soft)';
const FAINT = 'var(--ink-faint)';
const RULE = 'var(--rule)';
const ACCENT = 'var(--accent)';
const UP = 'var(--credited)';
const DOWN = 'var(--uncredited)';

const fmt = (v, dp = 4) => (v === null || v === undefined ? '—' : Number(v).toFixed(dp));
const pct = v => (v === null || v === undefined ? '—' : `${Number(v).toFixed(2)}%`);
const wrapViz = (...kids) => el('div', { class: 'viz' }, ...kids);

/* ---------------------------------------------------------------- thesis
   The two headline AUCs, side by side. Used on screen 1. */
export function thesisChart(leaked, honest, leakedText, honestText) {
  const W = 700, H = 150, L = 92, R = 88;
  const lo = 0.5, hi = 0.95;
  const x = v => L + (v - lo) / (hi - lo) * (W - L - R);
  const s = svg(W, H, { 'aria-label': `Leaked ${leakedText} against honest ${honestText}` });

  for (const t of [0.5, 0.6, 0.7, 0.8, 0.9]) {
    s.append(node('line', { x1: x(t), y1: 26, x2: x(t), y2: H - 26, stroke: RULE, 'stroke-width': 1 }));
    s.append(node('text', { x: x(t), y: H - 10, fill: FAINT, 'font-size': 11,
      'text-anchor': 'middle', 'font-family': 'var(--sans)' }, t.toFixed(1)));
  }

  const rows = [
    { label: 'leaked', v: leaked, text: leakedText, y: 38, colour: DOWN },
    { label: 'honest', v: honest, text: honestText, y: 84, colour: UP },
  ];
  for (const r of rows) {
    s.append(node('text', { x: L - 12, y: r.y + 19, fill: INK, 'font-size': 13,
      'text-anchor': 'end', 'font-family': 'var(--sans)', 'font-weight': 600 }, r.label));
    s.append(node('rect', { x: L, y: r.y, width: Math.max(0, x(r.v) - L), height: 28,
      fill: r.colour, rx: 3 }));
    s.append(node('text', { x: x(r.v) + 8, y: r.y + 19, fill: INK, 'font-size': 14,
      'font-family': 'var(--sans)', 'font-weight': 650 }, r.text));
  }
  return s;
}

/* -------------------------------------------------- get_shap_ranking */
function shapRanking(r) {
  if (!r.ranking || !r.ranking.length) return null;
  const CAP = 25;
  const rows = r.ranking.slice(0, CAP);
  const max = Math.max(...rows.map(d => d.mean_abs_shap));
  const rowH = 20, L = 186, R = 74, W = 700;
  const H = rows.length * rowH + 16;
  const s = svg(W, H, { 'aria-label': 'Features by mean absolute SHAP' });

  rows.forEach((d, i) => {
    const y = i * rowH + 8;
    s.append(node('text', { x: L - 8, y: y + 11, fill: INK, 'font-size': 11,
      'text-anchor': 'end', 'font-family': 'var(--mono)' }, d.feature));
    const w = max > 0 ? (d.mean_abs_shap / max) * (W - L - R) : 0;
    s.append(node('rect', { x: L, y, width: Math.max(1, w), height: rowH - 7,
      fill: i === 0 ? ACCENT : SOFT, rx: 2 }));
    s.append(node('text', { x: L + w + 6, y: y + 11, fill: FAINT, 'font-size': 10,
      'font-family': 'var(--mono)' }, d.mean_abs_shap.toFixed(4)));
  });

  const note = rows.length < r.ranking.length
    ? `Top ${rows.length} of ${r.ranking.length} returned; ${r.total_features} features in the model.`
    : `${r.returned} of ${r.total_features} features. Mean absolute SHAP, log-odds.`;
  return wrapViz(s, el('p', { class: 'viz-note', text: note }));
}

/* ------------------------------------------------ get_ablation_result */
function ablation(r) {
  if (!r.available) return null;
  // The tool reports the score without the feature and the delta against
  // the full model, so the full model's score is the one derived here.
  const without = r.roc_auc_without_feature;
  const withIt = without - r.delta_roc_auc;
  const W = 700, H = 132, L = 104, R = 92;
  const lo = 0.5, hi = Math.max(0.95, withIt + 0.03);
  const x = v => L + (v - lo) / (hi - lo) * (W - L - R);
  const s = svg(W, H, { 'aria-label': 'Score with and without the feature' });

  const rows = [
    { label: 'with', v: withIt, y: 24, colour: DOWN },
    { label: 'without', v: without, y: 66, colour: UP },
  ];
  for (const row of rows) {
    s.append(node('text', { x: L - 10, y: row.y + 18, fill: INK, 'font-size': 12,
      'text-anchor': 'end', 'font-family': 'var(--sans)', 'font-weight': 600 }, row.label));
    s.append(node('rect', { x: L, y: row.y, width: Math.max(1, x(row.v) - L), height: 26,
      fill: row.colour, rx: 3 }));
    s.append(node('text', { x: x(row.v) + 8, y: row.y + 18, fill: INK, 'font-size': 13,
      'font-family': 'var(--sans)', 'font-weight': 650 }, fmt(row.v)));
  }
  const drop = r.delta_roc_auc;
  s.append(node('text', { x: L, y: H - 8, fill: drop < 0 ? DOWN : FAINT, 'font-size': 12,
    'font-family': 'var(--sans)', 'font-weight': 600 },
    `${drop < 0 ? 'drops' : 'changes'} ${Math.abs(drop).toFixed(4)} ROC-AUC when removed`));
  return wrapViz(s, el('p', { class: 'viz-note',
    text: `PR-AUC without the feature ${fmt(r.pr_auc_without_feature)}, a change of ${fmt(r.delta_pr_auc)}.` }));
}

/* ----------------------------------------------- get_feature_coverage */
function coverage(r) {
  if (!r.found || !r.scopes || !r.scopes.length) return null;
  const scopes = r.scopes;
  const useFlag = Boolean(r.has_missingness_flag);
  const valueOf = sc => (useFlag ? sc.pct_flagged_missing : sc.pct_zero);
  const label = useFlag ? 'flagged missing' : 'exactly zero';

  const W = 700, H = 176, T = 22, B = 56;
  const colW = (W - 40) / scopes.length;
  const s = svg(W, H, { 'aria-label': `Coverage of ${r.feature} by scope` });
  s.append(node('line', { x1: 20, y1: H - B, x2: W - 20, y2: H - B, stroke: RULE }));

  scopes.forEach((sc, i) => {
    const cx = 20 + colW * i + colW / 2;
    const v = valueOf(sc);
    const h = v === null || v === undefined ? 0 : (v / 100) * (H - B - T);
    const isSplit = sc.scope === 'train' || sc.scope === 'test';
    s.append(node('rect', { x: cx - Math.min(26, colW / 3), y: H - B - h,
      width: Math.min(52, colW / 1.5), height: Math.max(v ? 2 : 0, h),
      fill: isSplit ? ACCENT : SOFT, rx: 2, opacity: isSplit ? 1 : .75 }));
    s.append(node('text', { x: cx, y: H - B - h - 6, fill: INK, 'font-size': 11,
      'text-anchor': 'middle', 'font-family': 'var(--sans)' }, pct(v)));
    s.append(node('text', { x: cx, y: H - B + 16, fill: isSplit ? INK : FAINT, 'font-size': 11,
      'text-anchor': 'middle', 'font-family': 'var(--sans)',
      'font-weight': isSplit ? 600 : 400 }, sc.scope));
    s.append(node('text', { x: cx, y: H - B + 31, fill: FAINT, 'font-size': 9.5,
      'text-anchor': 'middle', 'font-family': 'var(--sans)' }, `μ ${fmt(sc.mean, 3)}`));
    s.append(node('text', { x: cx, y: H - B + 44, fill: FAINT, 'font-size': 9.5,
      'text-anchor': 'middle', 'font-family': 'var(--sans)' },
      `${sc.n_rows.toLocaleString('en-US')} rows`));
  });
  s.append(node('text', { x: 20, y: 13, fill: FAINT, 'font-size': 10,
    'font-family': 'var(--sans)' }, `% of rows ${label}`));
  return wrapViz(s, r.missingness_flag_note
    ? el('p', { class: 'viz-note', text: r.missingness_flag_note }) : null);
}

/* ------------------------------- get_feature_target_association */
function association(r) {
  if (!r.found) return null;
  const fields = [
    ['auc_train', 'train'], ['auc_test', 'test'],
    ['auc_2014', '2014'], ['auc_2015', '2015'], ['auc_2016', '2016'],
  ].filter(([k]) => k in r);
  if (!fields.length) return null;

  const W = 700, H = 176, T = 22, B = 44, MID = (H - B + T) / 2;
  const colW = (W - 40) / fields.length;
  // Bars read against 0.5, which is where a feature orders nothing.
  const span = Math.max(0.12, ...fields.map(([k]) =>
    r[k] === null || r[k] === undefined ? 0 : Math.abs(r[k] - 0.5) * 1.2));
  const y = v => MID - ((v - 0.5) / span) * ((H - B - T) / 2);
  const s = svg(W, H, { 'aria-label': `Standalone AUC of ${r.feature} by scope` });

  s.append(node('line', { x1: 20, y1: MID, x2: W - 20, y2: MID, stroke: RULE, 'stroke-width': 1.5 }));
  s.append(node('text', { x: 20, y: MID - 6, fill: FAINT, 'font-size': 10,
    'font-family': 'var(--sans)' }, '0.5 — orders nothing'));

  fields.forEach(([k, name], i) => {
    const cx = 20 + colW * i + colW / 2;
    const v = r[k];
    if (v === null || v === undefined) {
      s.append(node('text', { x: cx, y: MID - 10, fill: FAINT, 'font-size': 11,
        'text-anchor': 'middle', 'font-family': 'var(--sans)' }, 'null'));
    } else {
      const top = Math.min(MID, y(v)), h = Math.abs(y(v) - MID);
      s.append(node('rect', { x: cx - Math.min(24, colW / 3), y: top,
        width: Math.min(48, colW / 1.6), height: Math.max(1.5, h),
        fill: v >= 0.5 ? UP : DOWN, rx: 2 }));
      s.append(node('text', { x: cx, y: v >= 0.5 ? top - 6 : top + h + 14, fill: INK,
        'font-size': 11, 'text-anchor': 'middle', 'font-family': 'var(--sans)' }, fmt(v, 3)));
    }
    s.append(node('text', { x: cx, y: H - B + 20, fill: FAINT, 'font-size': 11,
      'text-anchor': 'middle', 'font-family': 'var(--sans)' }, name));
  });

  const bits = [`Pearson on test ${fmt(r.point_biserial_test)}`,
    `${r.n_unique_test} distinct values on test`];
  if (r.is_constant_test) bits.push('constant on test');
  return wrapViz(s,
    el('p', { class: 'viz-note', text: bits.join(' · ') }),
    r.undefined_note ? el('p', { class: 'viz-note', text: r.undefined_note }) : null);
}

/* --------------------------------------------- get_correlated_features */
function correlated(r) {
  if (!r.available || !r.neighbours || !r.neighbours.length) return null;
  const rows = r.neighbours;
  const rowH = 20, L = 196, W = 700, MID = L + (W - L - 40) / 2;
  const H = rows.length * rowH + 16;
  const half = (W - L - 40) / 2;
  const s = svg(W, H, { 'aria-label': `Features correlated with ${r.feature}` });
  s.append(node('line', { x1: MID, y1: 4, x2: MID, y2: H - 4, stroke: RULE }));

  rows.forEach((d, i) => {
    const y = i * rowH + 8;
    s.append(node('text', { x: L - 8, y: y + 11, fill: INK, 'font-size': 11,
      'text-anchor': 'end', 'font-family': 'var(--mono)' }, d.neighbour));
    const w = Math.abs(d.pearson_r) * half;
    s.append(node('rect', { x: d.pearson_r >= 0 ? MID : MID - w, y,
      width: Math.max(1, w), height: rowH - 7, fill: d.pearson_r >= 0 ? UP : DOWN, rx: 2 }));
    s.append(node('text', { x: d.pearson_r >= 0 ? MID + w + 6 : MID - w - 6, y: y + 11,
      fill: FAINT, 'font-size': 10, 'text-anchor': d.pearson_r >= 0 ? 'start' : 'end',
      'font-family': 'var(--mono)' }, d.pearson_r.toFixed(3)));
  });
  return wrapViz(s, el('p', { class: 'viz-note',
    text: `${r.returned} of ${r.precomputed_count} precomputed neighbours, Pearson on the test split.` }));
}

/* ----------------------------------------- get_feature_shap_detail */
function shapDetail(r) {
  if (!r.found) return null;
  const W = 700, H = 92, L = 20, R = 20;
  const lo = Math.min(r.min, 0), hi = Math.max(r.max, 0);
  const span = hi - lo || 1;
  const x = v => L + (v - lo) / span * (W - L - R);
  const s = svg(W, H, { 'aria-label': `SHAP distribution of ${r.feature}` });

  s.append(node('line', { x1: x(0), y1: 14, x2: x(0), y2: 58, stroke: RULE, 'stroke-width': 1.5 }));
  // p5–p95 as the body, q25–q75 heavier, median as a tick.
  s.append(node('rect', { x: x(r.p5), y: 28, width: Math.max(1, x(r.p95) - x(r.p5)),
    height: 16, fill: SOFT, opacity: .35, rx: 2 }));
  s.append(node('rect', { x: x(r.q25), y: 24, width: Math.max(1, x(r.q75) - x(r.q25)),
    height: 24, fill: ACCENT, opacity: .55, rx: 2 }));
  s.append(node('line', { x1: x(r.median), y1: 20, x2: x(r.median), y2: 52,
    stroke: INK, 'stroke-width': 2 }));
  for (const [v, label] of [[r.min, 'min'], [r.max, 'max']]) {
    s.append(node('text', { x: x(v), y: 72, fill: FAINT, 'font-size': 10,
      'text-anchor': v === r.min ? 'start' : 'end', 'font-family': 'var(--mono)' },
      `${label} ${v.toFixed(3)}`));
  }
  s.append(node('text', { x: x(r.median), y: 14, fill: INK, 'font-size': 10,
    'text-anchor': 'middle', 'font-family': 'var(--sans)' }, `median ${r.median.toFixed(3)}`));

  const kv = el('div', { class: 'kv' });
  const pairs = [
    ['rank', r.rank_by_mean_abs_shap], ['mean |shap|', fmt(r.mean_abs_shap, 4)],
    ['share of total', pct((r.share_of_total_abs_shap ?? 0) * 100)],
    ['pushes up', pct(r.pct_positive)], ['pushes down', pct(r.pct_negative)],
    ['near zero', pct(r.pct_near_zero)],
    ['top 1% carry', pct(r.top1pct_abs_share * 100)], ['rows', r.rows.toLocaleString('en-US')],
  ];
  for (const [k, v] of pairs) {
    kv.append(el('div', {}, el('div', { class: 'k', text: k }), el('div', { class: 'v', text: String(v) })));
  }
  return wrapViz(s, kv);
}

/* ----------------------------------------------------- lookup_feature */
function lookup(r) {
  if (!r.found) return null;
  const dl = el('dl', {});
  dl.append(el('dt', { text: 'column' }), el('dd', { class: 'name', text: r.feature }));
  dl.append(el('dt', { text: 'means' }), el('dd', { text: r.description }));
  if ('populated' in r) dl.append(el('dt', { text: 'populated' }), el('dd', { text: r.populated }));
  if (r.source) dl.append(el('dt', { text: 'source' }), el('dd', { text: r.source }));
  return el('div', { class: 'defn' }, dl);
}

/* ---------------------------------------------- search_data_dictionary */
function search(r) {
  if (!r.results || !r.results.length) return null;
  const list = el('div', { class: 'hits' });
  for (const hit of r.results) {
    list.append(el('div', { class: 'hit' },
      el('b', { text: hit.feature }), ' ',
      el('span', { text: hit.description }),
      'populated' in hit ? el('span', { text: ` — ${hit.populated}` }) : null));
  }
  return el('div', {},
    el('p', { class: 'viz-note',
      text: `${r.match_count} matched "${r.query}"; ${r.returned} shown.` }),
    list);
}

/* A result with no picture of its own still does not appear as raw JSON. */
function fallback(r) {
  const kv = el('div', { class: 'kv' });
  for (const [k, v] of Object.entries(r)) {
    if (v === null || typeof v === 'object') continue;
    const text = typeof v === 'number' ? String(v) : String(v);
    if (text.length > 120) continue;
    kv.append(el('div', {}, el('div', { class: 'k', text: k }),
      el('div', { class: 'v', text })));
  }
  const message = r.message || r.note;
  return el('div', {},
    kv.children.length ? kv : null,
    message ? el('p', { class: 'viz-note', text: message }) : null);
}

const RENDERERS = {
  get_shap_ranking: shapRanking,
  get_ablation_result: ablation,
  get_feature_coverage: coverage,
  get_feature_target_association: association,
  get_correlated_features: correlated,
  get_feature_shap_detail: shapDetail,
  lookup_feature: lookup,
  search_data_dictionary: search,
};

/* One tool result, drawn. A tool that returned found=false or available=false
   has nothing to plot, so its own message is shown instead — which is the
   point of those messages. */
export function renderResult(toolName, result) {
  const draw = RENDERERS[toolName];
  let out = null;
  try {
    out = draw ? draw(result) : null;
  } catch (err) {
    console.error('viz failed for', toolName, err);
    out = null;
  }
  return out || fallback(result);
}
