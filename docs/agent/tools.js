export const BUILD = '91493d637f81';
/* The eight tools, in the browser, over the exported JSON.
 *
 * A port of agent/tools.py. The tables are the ones that file reads,
 * exported once by scripts/export_tool_artefacts.py; get_feature_shap_detail
 * is served from summaries that file computed, because the parquet behind
 * it is 30 MB.
 *
 * The loaded JSON is private to this module and leaves it only as the
 * return value of dispatch(). The agent sees tool output and nothing else.
 * That is the whole basis of the test: dictionary.json carries `populated`
 * for all 224 columns, which is the field the answer key is derived from,
 * and the include_populated switch is only honest if the agent can never
 * reach around the tool to the file.
 *
 * One tool is not a faithful port and says so. search_data_dictionary has
 * two tiers; tier 2 is semantic retrieval over description embeddings in
 * the recorded runs, and here it is the substring-over-descriptions
 * fallback that agent/data_dictionary.py already defines. Its results
 * differ from the recorded runs by design, not by accident.
 */

const SEARCH_LIMIT = 25;
const DEFAULT_TOP_K = 5;
const MAX_TOP_K = 15;
const SPLIT_SCOPES = ['train', 'test'];
const VINTAGE_SCOPES = ['2014', '2015', '2016', '2017'];
const VINTAGE_AUCS = ['auc_2014', 'auc_2015', 'auc_2016'];

const SCOPE_OF = {
  auc_train: 'the training split',
  auc_test: 'the test split',
  auc_2014: '2014',
  auc_2015: '2015',
  auc_2016: '2016',
};

/* Python's int(): truncates a float, accepts an integer-looking string,
   and raises on anything else. Null here stands for the raise. */
function toInt(value) {
  if (typeof value === 'boolean') return value ? 1 : 0;
  if (typeof value === 'number') return Number.isFinite(value) ? Math.trunc(value) : null;
  if (typeof value === 'string' && /^[+-]?\d+$/.test(value.trim())) {
    return parseInt(value.trim(), 10);
  }
  return null;
}

function isName(value) {
  return typeof value === 'string' && value.trim() !== '';
}

/* The CSVs leave a cell empty where a statistic was undefined. The export
   turned those into null, and they stay null: never a substituted default. */
function optFloat(value) {
  return value === null || value === undefined ? null : value;
}

export class ToolLayer {
  #dictionary; #shapGlobal; #shapDetail; #ablation; #coverage;
  #univariate; #correlations; #byFeature; #log;

  constructor(data, { includePopulated = true, includeVintageScopes = true } = {}) {
    this.#dictionary = data.dictionary;
    this.#shapGlobal = data.shapGlobal;
    this.#shapDetail = data.shapDetail;
    this.#ablation = data.ablation;
    this.#coverage = data.coverage;
    this.#univariate = data.univariate;
    this.#correlations = data.correlations;
    this.includePopulated = includePopulated;
    this.includeVintageScopes = includeVintageScopes;
    this.#log = [];

    // Row lookups the Python side gets from pandas.
    this.#byFeature = {
      dictionary: new Map(this.#dictionary.map(e => [e.feature, e])),
      shapGlobal: new Map(this.#shapGlobal.map(r => [r.feature, r])),
      ablation: new Map(this.#ablation.map(r => [r.feature, r])),
      univariate: new Map(this.#univariate.map(r => [r.feature, r])),
      coverage: groupBy(this.#coverage, r => r.feature),
      correlations: groupBy(this.#correlations, r => r.feature),
    };
  }

  static async load(base, variant, options) {
    const at = async path => {
      const res = await fetch(`${base}/${path}`, { cache: 'no-cache' });
      if (!res.ok) throw new Error(`${path} could not be loaded (${res.status}).`);
      return res.json();
    };
    const [dictionary, shapGlobal, shapDetail, ablation, coverage, univariate, correlations] =
      await Promise.all([
        at('dictionary.json'),
        at(`${variant}/shap_global.json`),
        at(`${variant}/shap_detail.json`),
        at(`${variant}/ablation.json`),
        at(`${variant}/coverage.json`),
        at(`${variant}/univariate.json`),
        at(`${variant}/correlations.json`),
      ]);
    return new ToolLayer(
      { dictionary, shapGlobal, shapDetail, ablation, coverage, univariate, correlations },
      options);
  }

  /* Drop `populated` entirely when suppressed; touch nothing else. */
  #shapeEntry(entry) {
    if (this.includePopulated) return { ...entry };
    const out = {};
    for (const [k, v] of Object.entries(entry)) if (k !== 'populated') out[k] = v;
    return out;
  }

  // ---------------------------------------------------------------- 1
  lookup_feature(feature) {
    if (!isName(feature)) {
      return { found: false, message: 'Provide a feature name as a non-empty string.' };
    }
    const name = feature.trim();
    const entry = this.#byFeature.dictionary.get(name);
    if (!entry) {
      return {
        found: false,
        feature: name,
        message: `No dictionary entry exists for '${name}'. Check the spelling, ` +
          `or use search_data_dictionary to find related columns.`,
      };
    }
    return { found: true, ...this.#shapeEntry(entry) };
  }

  // ---------------------------------------------------------------- 2
  search_data_dictionary(query) {
    if (!isName(query)) {
      return {
        query: '', match_count: 0, returned: 0, results: [],
        message: 'Provide a search term as a non-empty string.',
      };
    }
    const q = query.trim();
    const lower = q.toLowerCase();

    // Tier 1: name substring, in dictionary order.
    const nameHits = this.#dictionary.filter(e => e.feature.toLowerCase().includes(lower));
    const seen = new Set(nameHits.map(e => e.feature));
    // Tier 2, fallback form: description substring, excluding tier 1.
    const descHits = this.#dictionary.filter(
      e => !seen.has(e.feature) && e.description.toLowerCase().includes(lower));

    const hits = [...nameHits, ...descHits];
    const shown = hits.slice(0, SEARCH_LIMIT).map(h => this.#shapeEntry(h));
    const out = { query: q, match_count: hits.length, returned: shown.length, results: shown };
    if (hits.length > SEARCH_LIMIT) {
      out.message = `${hits.length} columns matched; the first ${SEARCH_LIMIT} are shown. ` +
        `Narrow the search term to see the rest.`;
    } else if (!hits.length) {
      out.message = `No column name or definition contains '${q}'.`;
    }
    return out;
  }

  // ---------------------------------------------------------------- 3
  get_shap_ranking(top_n = 20) {
    const df = this.#shapGlobal;
    if (!df || !df.length) return { message: 'The global SHAP ranking is not available.' };
    const parsed = toInt(top_n);
    if (parsed === null) return { message: 'top_n must be a whole number.' };
    const n = Math.max(1, Math.min(parsed, df.length));
    return {
      total_features: df.length,
      returned: n,
      note: 'mean_abs_shap is in log-odds units, averaged over 30,000 sampled test rows.',
      ranking: df.slice(0, n).map(r => ({
        rank: r.rank, feature: r.feature, mean_abs_shap: r.mean_abs_shap,
      })),
    };
  }

  // ---------------------------------------------------------------- 4
  get_feature_shap_detail(feature) {
    if (!isName(feature)) {
      return { found: false, message: 'Provide a feature name as a non-empty string.' };
    }
    const name = feature.trim();
    if (!this.#shapDetail) {
      return { found: false, message: 'The per-row SHAP values are not available.' };
    }
    const hit = this.#shapDetail[name];
    if (!hit) {
      return {
        found: false,
        feature: name,
        message: `'${name}' is not one of the model's features, so it has no SHAP ` +
          `values. Use get_shap_ranking to see the feature names.`,
      };
    }
    return { found: true, feature: name, ...hit };
  }

  // ---------------------------------------------------------------- 5
  get_ablation_result(feature) {
    if (!isName(feature)) {
      return { available: false, message: 'Provide a feature name as a non-empty string.' };
    }
    const name = feature.trim();
    const df = this.#ablation;
    if (!df || !df.length) {
      return { available: false, message: 'The ablation results are not available.' };
    }
    const r = this.#byFeature.ablation.get(name);
    if (!r) {
      const nCovered = df.length;
      const known = this.#byFeature.shapGlobal.has(name);
      const why = known
        // The covered set is exactly the SHAP top-N, so naming its members
        // here would hand over that ranking in one call.
        ? `Ablation was precomputed only for the ${nCovered} highest-ranked features ` +
          `by mean absolute SHAP, and '${name}' is not among them. Use get_shap_ranking ` +
          `to see which features rank where.`
        : `'${name}' is not one of the model's features, and ablation was precomputed ` +
          `only for the ${nCovered} highest-ranked of those.`;
      return {
        available: false,
        feature: name,
        precomputed_count: nCovered,
        message: why + ' No ablation figure can be given for it.',
      };
    }
    return {
      available: true,
      feature: name,
      note: 'Model retrained without this column, then scored on the held-out 2017 ' +
        'test set. Deltas are relative to the same model trained with every feature.',
      roc_auc_without_feature: r.roc_auc,
      pr_auc_without_feature: r.pr_auc,
      delta_roc_auc: r.delta_roc_auc,
      delta_pr_auc: r.delta_pr_auc,
    };
  }

  // ---------------------------------------------------------------- 6
  get_feature_coverage(feature) {
    if (!isName(feature)) {
      return { found: false, message: 'Provide a feature name as a non-empty string.' };
    }
    const name = feature.trim();
    if (!this.#coverage || !this.#coverage.length) {
      return { found: false, message: 'The coverage profile is not available.' };
    }
    const rows = this.#byFeature.coverage.get(name);
    if (!rows || !rows.length) {
      return {
        found: false,
        feature: name,
        message: `'${name}' is not one of the columns in the model's feature matrix, ` +
          `so it has no coverage profile. Use get_shap_ranking to see the feature names.`,
      };
    }

    const wanted = this.includeVintageScopes
      ? [...SPLIT_SCOPES, ...VINTAGE_SCOPES]
      : [...SPLIT_SCOPES];
    const byScope = new Map(rows.map(r => [String(r.scope), r]));
    const hasFlag = Boolean(rows[0].has_missingness_flag);

    const scopes = [];
    for (const scope of wanted) {
      const r = byScope.get(scope);
      if (!r) continue;
      const entry = { scope, n_rows: r.n_rows, has_missingness_flag: hasFlag };
      if (hasFlag) entry.pct_flagged_missing = optFloat(r.pct_flagged_missing);
      entry.pct_zero = optFloat(r.pct_zero);
      entry.pct_at_999 = optFloat(r.pct_at_999);
      entry.n_unique = r.n_unique;
      entry.mean = optFloat(r.mean);
      entry.std = optFloat(r.std);
      entry.p50 = optFloat(r.p50);
      scopes.push(entry);
    }

    const out = {
      found: true,
      feature: name,
      has_missingness_flag: hasFlag,
      note: 'pct_zero and pct_at_999 count rows holding exactly that value. std is ' +
        'the sample standard deviation and p50 the median, both within the scope.',
      scopes,
    };
    if (!hasFlag) {
      out.missingness_flag_note = `'${name}' has no companion _was_missing column, ` +
        `so no flagged-missing percentage exists for it and none is reported.`;
    }
    return out;
  }

  // ---------------------------------------------------------------- 7
  get_feature_target_association(feature) {
    if (!isName(feature)) {
      return { found: false, message: 'Provide a feature name as a non-empty string.' };
    }
    const name = feature.trim();
    if (!this.#univariate || !this.#univariate.length) {
      return { found: false, message: 'The univariate association figures are not available.' };
    }
    const r = this.#byFeature.univariate.get(name);
    if (!r) {
      return {
        found: false,
        feature: name,
        message: `'${name}' is not one of the columns in the model's feature matrix, ` +
          `so it has no univariate association figures. Use get_shap_ranking to see ` +
          `the feature names.`,
      };
    }

    const aucFields = this.includeVintageScopes
      ? ['auc_train', 'auc_test', ...VINTAGE_AUCS]
      : ['auc_train', 'auc_test'];

    const out = {
      found: true,
      feature: name,
      reading: 'Each AUC is rank-based, computed from the Mann-Whitney U statistic ' +
        'using the raw feature value as the score. It is not corrected for direction: ' +
        '0.5 means the feature does not order the outcome, above 0.5 means it orders ' +
        'it in the same direction, and below 0.5 means it orders it in reverse.',
    };
    for (const f of aucFields) out[f] = optFloat(r[f]);
    out.point_biserial_test = optFloat(r.point_biserial_test);
    out.n_unique_test = r.n_unique_test;
    out.is_constant_test = Boolean(r.is_constant_test);

    // Only over the fields actually reported, so the note cannot name a
    // vintage the caller was not given.
    const empty = aucFields.filter(f => out[f] === null).map(f => SCOPE_OF[f]);
    if (empty.length) {
      out.undefined_note = `'${name}' takes a single value within ${empty.join(', ')}, ` +
        `so no association could be computed there and those figures are null rather ` +
        `than substituted.`;
    }
    return out;
  }

  // ---------------------------------------------------------------- 8
  get_correlated_features(feature, top_k = DEFAULT_TOP_K) {
    if (!isName(feature)) {
      return { available: false, message: 'Provide a feature name as a non-empty string.' };
    }
    const name = feature.trim();
    const parsed = toInt(top_k);
    if (parsed === null) return { available: false, message: 'top_k must be a whole number.' };

    let clampNote = null;
    if (parsed > MAX_TOP_K) {
      clampNote = `${parsed} neighbours were requested; only ${MAX_TOP_K} were ` +
        `precomputed per feature, so ${MAX_TOP_K} are returned.`;
    }
    const k = Math.max(1, Math.min(parsed, MAX_TOP_K));

    if (!this.#correlations || !this.#correlations.length) {
      return { available: false, message: 'The correlation neighbours are not available.' };
    }
    const all = this.#byFeature.correlations.get(name);
    if (!all || !all.length) {
      return {
        available: false,
        feature: name,
        message: `'${name}' is not one of the columns in the model's feature matrix, ` +
          `so it has no correlation neighbours. Use get_shap_ranking to see the ` +
          `feature names.`,
      };
    }
    const sorted = [...all].sort((a, b) => a.rank - b.rank);
    if (sorted.every(r => r.neighbour === null || r.neighbour === undefined)) {
      return {
        available: false,
        feature: name,
        message: `Correlations are undefined for '${name}': it holds a single value ` +
          `throughout the evaluation split, so it has no variation to relate to any ` +
          `other column. No neighbours can be reported.`,
      };
    }
    const rows = sorted.filter(r => r.neighbour !== null && r.neighbour !== undefined).slice(0, k);
    const out = {
      available: true,
      feature: name,
      returned: rows.length,
      precomputed_count: MAX_TOP_K,
      note: 'Pearson correlation between the two columns over the full held-out test ' +
        'set, ordered by absolute value. pearson_r keeps its sign.',
      neighbours: rows.map(r => ({
        rank: r.rank,
        neighbour: String(r.neighbour),
        pearson_r: r.pearson_r,
        abs_pearson_r: r.abs_pearson_r,
      })),
    };
    if (clampNote) out.message = clampNote;
    return out;
  }

  // ------------------------------------------------------- dispatch
  /* The agent's only entry point. Never throws; never leaks internals. */
  dispatch(name, args) {
    const handlers = {
      lookup_feature: ['feature'],
      search_data_dictionary: ['query'],
      get_shap_ranking: ['top_n'],
      get_feature_shap_detail: ['feature'],
      get_ablation_result: ['feature'],
      get_feature_coverage: ['feature'],
      get_feature_target_association: ['feature'],
      get_correlated_features: ['feature', 'top_k'],
    };
    // Parameters with no default in the Python signature; omitting one
    // there is a TypeError, and the same message comes back here.
    const required = {
      lookup_feature: ['feature'],
      search_data_dictionary: ['query'],
      get_shap_ranking: [],
      get_feature_shap_detail: ['feature'],
      get_ablation_result: ['feature'],
      get_feature_coverage: ['feature'],
      get_feature_target_association: ['feature'],
      get_correlated_features: ['feature'],
    };

    const allowed = handlers[name];
    if (!allowed) {
      this.#record(name, args || {}, false, 'unknown_tool');
      return { message: `There is no tool called '${name}'. Available tools: ` +
        `${Object.keys(handlers).sort().join(', ')}.` };
    }
    const a = args === undefined || args === null ? {} : args;
    if (typeof a !== 'object' || Array.isArray(a)) {
      this.#record(name, a, false, 'bad_arguments');
      return { message: 'Tool arguments must be supplied as an object.' };
    }
    const unexpected = Object.keys(a).filter(k => !allowed.includes(k));
    if (unexpected.length) {
      this.#record(name, a, false, 'unexpected_argument');
      return { message: `'${name}' does not accept ${unexpected.slice().sort().join(', ')}. ` +
        `It accepts: ${allowed.join(', ')}.` };
    }
    if (required[name].some(k => !(k in a))) {
      this.#record(name, a, false, 'bad_arguments');
      return { message: `'${name}' was called with the wrong arguments. ` +
        `It accepts: ${allowed.join(', ')}.` };
    }

    let result;
    try {
      switch (name) {
        case 'lookup_feature': result = this.lookup_feature(a.feature); break;
        case 'search_data_dictionary': result = this.search_data_dictionary(a.query); break;
        case 'get_shap_ranking':
          result = 'top_n' in a ? this.get_shap_ranking(a.top_n) : this.get_shap_ranking(); break;
        case 'get_feature_shap_detail': result = this.get_feature_shap_detail(a.feature); break;
        case 'get_ablation_result': result = this.get_ablation_result(a.feature); break;
        case 'get_feature_coverage': result = this.get_feature_coverage(a.feature); break;
        case 'get_feature_target_association':
          result = this.get_feature_target_association(a.feature); break;
        case 'get_correlated_features':
          result = 'top_k' in a
            ? this.get_correlated_features(a.feature, a.top_k)
            : this.get_correlated_features(a.feature);
          break;
      }
    } catch (err) {
      // Deliberately opaque: no stack, no path, no module name.
      this.#record(name, a, false, 'failed');
      return { message: `'${name}' could not be completed.` };
    }
    this.#record(name, a, true, 'ok');
    return result;
  }

  #record(tool, args, ran, outcome) {
    this.#log.push({ tool, arguments: args, ran, outcome, at: Date.now() });
  }

  getCallLog() {
    return this.#log.map(e => ({ ...e }));
  }

  get config() {
    return {
      tool_layer_version: '2.0',
      dictionary_populated_field: this.includePopulated ? 'included' : 'suppressed',
      coverage_scopes: this.includeVintageScopes ? 'all' : 'splitonly',
      retrieval: 'substring-fallback',
    };
  }
}

function groupBy(rows, key) {
  const map = new Map();
  for (const row of rows) {
    const k = key(row);
    if (!map.has(k)) map.set(k, []);
    map.get(k).push(row);
  }
  return map;
}

/* agent/agent.py sends each tool result as json.dumps(output, default=str),
 * which uses Python's default separators: ", " between items and ": " after
 * a key. JSON.stringify uses neither, so the same result would reach the
 * model as different bytes, and a different token count, than it did in the
 * recorded runs. This reproduces Python's spacing so the browser agent reads
 * what the recorded agent read.
 *
 * ensure_ascii is not reproduced because it has nothing to do: the exported
 * data and every message in this file are ASCII, checked at export time.
 *
 * The other difference is that Python has a float type and JavaScript does
 * not. Python writes a float of 36 as 36.0; JSON.parse turns that into the
 * number 36 and JSON.stringify writes it back as 36. The fields below are
 * the ones Python emits as floats — the float64 columns of the exported
 * tables, plus the float() calls in get_feature_shap_detail — so an
 * integral value in one of them is written with its trailing .0 and the
 * bytes match. Getting this list wrong shows up immediately as a wire
 * mismatch in scripts/verify_js_tools.py, which is how it was checked.
 */
const FLOAT_FIELDS = new Set([
  // coverage_profile
  'pct_flagged_missing', 'pct_zero', 'pct_at_999', 'mean', 'std', 'p50',
  // univariate_assoc
  'auc_train', 'auc_test', 'auc_2014', 'auc_2015', 'auc_2016', 'auc_2017',
  'point_biserial_test',
  // ablation_cache
  'roc_auc_without_feature', 'pr_auc_without_feature',
  'delta_roc_auc', 'delta_pr_auc',
  // shap_global
  'mean_abs_shap',
  // shap_values summary
  'share_of_total_abs_shap', 'mean_signed_shap', 'min', 'p1', 'p5', 'q25',
  'median', 'q75', 'p95', 'p99', 'max', 'pct_positive', 'pct_negative',
  'pct_near_zero', 'top1pct_abs_share',
  // correlation_topk
  'pearson_r', 'abs_pearson_r',
]);

export function serialiseToolResult(value) {
  /* Python's repr() for a float, which differs from JavaScript's twice
     over: it always shows a decimal point, and it switches to exponential
     notation below 1e-4 where JavaScript waits until 1e-6. Both show up
     as different bytes for the same number. Above 1e16 Python goes
     exponential too; no exported value is that large, but the branch is
     here rather than being a latent surprise. */
  const pyFloat = v => {
    if (!Number.isFinite(v)) return JSON.stringify(v);
    if (v === 0) return Object.is(v, -0) ? '-0.0' : '0.0';
    const magnitude = Math.abs(v);
    if (magnitude >= 1e-4 && magnitude < 1e16) {
      return Number.isInteger(v) ? `${v}.0` : JSON.stringify(v);
    }
    // toExponential() with no argument is the shortest round-trip
    // mantissa, matching repr(); only the exponent needs padding to the
    // two digits Python always writes.
    return v.toExponential().replace(/e([+-])(\d)$/, 'e$10$2');
  };
  const num = (v, isFloat) => (isFloat ? pyFloat(v) : JSON.stringify(v));
  const enc = (v, isFloat = false) => {
    if (v === null || v === undefined) return 'null';
    if (typeof v === 'boolean') return v ? 'true' : 'false';
    if (typeof v === 'number') return num(v, isFloat);
    if (typeof v === 'string') return JSON.stringify(v);
    if (Array.isArray(v)) return '[' + v.map(x => enc(x, isFloat)).join(', ') + ']';
    if (typeof v === 'object') {
      return '{' + Object.entries(v)
        .map(([k, val]) => JSON.stringify(String(k)) + ': ' + enc(val, FLOAT_FIELDS.has(k)))
        .join(', ') + '}';
    }
    return JSON.stringify(String(v));
  };
  return enc(value);
}
