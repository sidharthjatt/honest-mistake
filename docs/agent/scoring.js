export const BUILD = '0e79a15923b6';
/* The scorer, ported from agent/answer_key.py.
 *
 * Scores a list of flagged column names against the answer key exported in
 * data/scoring.json. It is a port, not a reimplementation: every rule here
 * exists because the Python one has it, and verify/_verify_scoring.html
 * checks the two agree exactly over the eight scored runs and a set of
 * synthetic cases. A disagreement is a defect in this file.
 *
 * What it does not do is decide what the numbers mean. Precision and recall
 * are computed because the Python scorer computes them and parity would be
 * untestable without them, but the denominator for recall is all 39 true
 * positives regardless of how many were reachable in the run's data — none
 * in the 180-feature model, exactly one in the 181-feature one. A run that
 * finds the only findable column scores a recall of 0.0256. Presenting that
 * as a result is a mistake this file cannot prevent; see the caller.
 */

export const TRUE_POSITIVES = 'TRUE_POSITIVES';
export const OUT_OF_SCOPE = 'OUT_OF_SCOPE';
export const HARD_NEGATIVES = 'HARD_NEGATIVES';

/* The answer key, wrapped so the sets are built once rather than per call. */
export class AnswerKey {
  #truth; #oos; #hard; #graded; #residual; #clean; #tierLabels;
  #wasMissing; #families; #canary;

  constructor(scoring) {
    this.#truth = new Set(scoring.true_positives.map(t => t.column));
    this.#oos = new Set(Object.keys(scoring.out_of_scope));
    this.#hard = new Set(scoring.hard_negatives);
    this.#graded = new Set([...this.#truth, ...this.#oos, ...this.#hard]);

    /* RESIDUAL_TIMING_LEAK is the tiered subset. A true positive that is
       clean under suppression carries no tier and is excluded, which is
       what makes the per-tier counts add up to less than 39. */
    this.#residual = new Map();
    this.#clean = new Set();
    for (const t of scoring.true_positives) {
      if (t.clean_under_suppression) this.#clean.add(t.column);
      else this.#residual.set(t.column, t.tier);
    }
    this.#tierLabels = scoring.tier_labels;

    const rules = scoring.derivative_rules;
    this.#wasMissing = rules.was_missing_suffix;
    this.#families = [...rules.one_hot_families];
    this.#canary = scoring.canary || {};
  }

  get canaryColumns() { return Object.keys(this.#canary).sort(); }
  get canaryDetail() { return JSON.parse(JSON.stringify(this.#canary)); }
  get truthSize() { return this.#truth.size; }

  /* Python's tier_counts(): how many residual columns sit in each tier. */
  tierCounts() {
    const counts = {};
    for (const tier of Object.keys(this.#tierLabels)) counts[tier] = 0;
    for (const tier of this.#residual.values()) counts[tier] += 1;
    return counts;
  }

  /* derivative_parent(): the column a name derives from, or null. The
     suffix is tested first, exactly as Python does, so a name that is both
     a one-hot value and ends in the suffix resolves the same way. */
  derivativeParent(name) {
    if (name.endsWith(this.#wasMissing)) {
      const parent = name.slice(0, -this.#wasMissing.length);
      if (parent) return { parent, kind: 'was_missing' };
    }
    for (const family of this.#families) {
      if (name.startsWith(family + '_') && name !== family) {
        return { parent: family, kind: 'one_hot' };
      }
    }
    return null;
  }

  /* _resolve(): the name a flag is scored as. A flag that is itself graded
     is used as-is; otherwise its parent, if that parent is graded. An
     ungraded name with an ungraded parent stays itself. */
  resolve(name) {
    if (this.#graded.has(name)) return { name, kind: null };
    const hit = this.derivativeParent(name);
    if (hit && this.#graded.has(hit.parent)) {
      return { name: hit.parent, kind: hit.kind };
    }
    return { name, kind: null };
  }

  setOf(column) {
    if (this.#truth.has(column)) return TRUE_POSITIVES;
    if (this.#oos.has(column)) return OUT_OF_SCOPE;
    if (this.#hard.has(column)) return HARD_NEGATIVES;
    return null;
  }

  has(column, which) {
    if (which === TRUE_POSITIVES) return this.#truth.has(column);
    if (which === OUT_OF_SCOPE) return this.#oos.has(column);
    if (which === HARD_NEGATIVES) return this.#hard.has(column);
    return false;
  }

  tierOf(column) { return this.#residual.get(column) ?? null; }
  isCleanUnderSuppression(column) { return this.#clean.has(column); }
  get truth() { return new Set(this.#truth); }
  get tierLabels() { return { ...this.#tierLabels }; }
}

/* Python sorts strings by code point; JavaScript's default sort does too,
   but localeCompare does not, so the comparison is explicit. Every column
   name here is ASCII, and this keeps it correct if one ever is not. */
const byCodePoint = (a, b) => (a < b ? -1 : a > b ? 1 : 0);
const sorted = xs => [...xs].sort(byCodePoint);

/* Python rounds half to even; JavaScript's toFixed rounds half away from
   zero. Every rounded value here comes from a ratio of small integers, so
   an exact tie at the fourth decimal is possible (0.12345 is not, but
   1/8 = 0.125 at two places would be). Banker's rounding is implemented
   rather than assumed away. */
function pyRound(value, digits) {
  if (!Number.isFinite(value)) return value;
  const factor = 10 ** digits;
  const scaled = value * factor;
  const floor = Math.floor(scaled);
  const diff = scaled - floor;
  let n;
  if (Math.abs(diff - 0.5) < Number.EPSILON * Math.abs(scaled) * 8) {
    n = floor % 2 === 0 ? floor : floor + 1;   // exact tie -> even
  } else {
    n = Math.round(scaled);
  }
  return n / factor;
}

/* Whether each credited flag names a column the model actually read.

   Scoring matches a flag against the key by name and never asks whether
   the column was a model input. For these runs the two come apart: every
   true positive was removed during construction, yet all 39 remain in the
   dictionary the agent can search. So a flag can be credited for naming a
   leaking column that the audited model never had — which says nothing
   about that model.

   Recorded, not acted on. No verdict and no metric changes. The caller
   passes the variant's feature list because the Python key's own source
   for it, X_test.parquet, holds the honest matrix only and is not
   committed. Omit it and reachability reports itself unknown. */
function reachability(tp, resolved, modelColumns) {
  if (!modelColumns) {
    return { known: false, model_column_count: null, by_flag: {},
             reachable_count: null, unreachable_count: null };
  }
  const columns = modelColumns instanceof Set ? modelColumns : new Set(modelColumns);
  const byFlag = {};
  for (const f of tp) byFlag[f] = columns.has(resolved.get(f).name);
  const values = Object.values(byFlag);
  return {
    known: true,
    model_column_count: columns.size,
    by_flag: byFlag,
    reachable_count: values.filter(Boolean).length,
    unreachable_count: values.filter(v => !v).length,
  };
}

/* score(), ported. `canaryPresent` is three-valued exactly as in Python:
   true, false, or null for not stated. `modelColumns` is the audited
   model's feature list, or null for unknown. */
export function score(flagged, key, canaryPresent = null, modelColumns = null) {
  // dict.fromkeys: strip, drop empties, keep first occurrence order.
  const seen = new Set();
  const flags = [];
  for (const raw of flagged || []) {
    if (!raw) continue;
    const f = String(raw).trim();
    if (!f || seen.has(f)) continue;
    seen.add(f);
    flags.push(f);
  }

  const resolved = new Map(flags.map(f => [f, key.resolve(f)]));
  const parentOf = f => resolved.get(f).name;
  const kindOf = f => resolved.get(f).kind;

  const derivations = flags
    .filter(f => kindOf(f))
    .map(f => ({
      flag: f,
      parent: parentOf(f),
      kind: kindOf(f),
      parent_set: key.setOf(parentOf(f)),
    }));

  const outOfScopeFlagged = sorted(flags.filter(f => key.has(parentOf(f), OUT_OF_SCOPE)));
  const scoredFlags = flags.filter(f => !key.has(parentOf(f), OUT_OF_SCOPE));

  const tp = sorted(scoredFlags.filter(f => key.has(parentOf(f), TRUE_POSITIVES)));
  const fp = sorted(scoredFlags.filter(f => !key.has(parentOf(f), TRUE_POSITIVES)));

  // Distinct, so flagging a column and its derivative is one find.
  const tpDistinct = new Set(tp.map(parentOf));
  const fn = sorted([...key.truth].filter(c => !tpDistinct.has(c)));

  const hnFlagged = sorted(fp.filter(f => key.has(parentOf(f), HARD_NEGATIVES)));
  const hnRaw = hnFlagged.filter(f => kindOf(f) === null);
  const hnDerived = hnFlagged.filter(f => kindOf(f) !== null);
  const hnDistinct = new Set(hnFlagged.map(parentOf));

  const precision = scoredFlags.length ? tp.length / scoredFlags.length : 0.0;
  const recall = key.truthSize ? tpDistinct.size / key.truthSize : 0.0;
  const f1 = (precision + recall)
    ? (2 * precision * recall) / (precision + recall)
    : 0.0;

  const tierLabels = key.tierLabels;
  const tierCounts = key.tierCounts();
  const byTier = {};
  for (const tier of Object.keys(tierLabels)) byTier[tier] = [];
  for (const f of tp) {
    const tier = key.tierOf(parentOf(f));
    if (tier) byTier[tier].push(f);
  }

  const byResidualTier = {};
  for (const [tier, names] of Object.entries(byTier)) {
    byResidualTier[tier] = {
      label: tierLabels[tier],
      count: names.length,
      of_possible: tierCounts[tier],
      features: names,
    };
  }

  return {
    flagged_count: flags.length,
    scored_count: scoredFlags.length,
    true_positives: tp,
    true_positive_count: tp.length,
    false_positives: fp,
    false_positive_count: fp.length,
    false_negatives: fn,
    false_negative_count: fn.length,
    precision: pyRound(precision, 4),
    recall: pyRound(recall, 4),
    f1: pyRound(f1, 4),
    out_of_scope_flagged: outOfScopeFlagged,
    out_of_scope_flagged_count: outOfScopeFlagged.length,
    hard_negatives_flagged: hnFlagged,
    hard_negatives_flagged_count: hnFlagged.length,
    canary: canaryBlock(flags, resolved, key, canaryPresent),
    hard_negatives_flagged_raw: hnRaw,
    hard_negatives_flagged_via_derivative: hnDerived,
    hard_negatives_distinct_count: hnDistinct.size,
    derivative_resolutions: derivations,
    true_positives_by_residual_tier: byResidualTier,
    true_positives_clean_under_suppression:
      tp.filter(f => key.isCleanUnderSuppression(f)),
    // Appended, so every key above keeps the position it had before.
    true_positive_reachability: reachability(tp, resolved, modelColumns),
  };
}

/* _canary_block(), ported. The three-valued shape is the whole point: a
   run with no canary in its data must not report a miss, because there was
   nothing to miss. See agent/EVAL_NOTES.md, the 2026-09-17 correction. */
export function canaryBlock(flags, resolved, key, canaryPresent) {
  if (canaryPresent === false) {
    return { applicable: false, planted: [], caught: [], missed: [],
             detected: null, detail: {} };
  }
  if (canaryPresent === null || canaryPresent === undefined) {
    return { applicable: null, planted: null, caught: null, missed: null,
             detected: null, detail: {} };
  }
  const columns = key.canaryColumns;
  const reached = c => flags.some(f => resolved.get(f).name === c);
  const caught = columns.filter(reached);
  const missed = columns.filter(c => !reached(c));
  return {
    applicable: true,
    planted: columns,
    caught,
    missed,
    detected: columns.length > 0 && missed.length === 0,
    detail: key.canaryDetail,
  };
}
