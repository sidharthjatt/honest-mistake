// Stale copy of docs/agent/parse.js at 1e4df5d. Everything after this line is that file, byte for byte.
/* The final-answer parser, ported from agent/eval_canary.parse_final_answer.
 *
 * Strict on purpose, and the reason is worth keeping in view: malformed
 * output is a result about the agent, not an inconvenience to smooth over.
 * Nothing here repairs or guesses. Every departure from the format the
 * prompt specifies becomes a named warning, and an answer that fails to
 * parse is reported as a parse failure and never as a clean "nothing
 * found" — those two outcomes mean opposite things.
 *
 * It also decides `isScoreable`, which is what tells a page whether it is
 * looking at a verdict or at a run that produced none. A divergence here
 * would surface as a wrong verdict or a wrong banner and would read as a
 * fault in the screen rather than in this file, so it is checked against
 * the Python parser over every recorded final answer plus the malformed
 * cases the twelve never produced. See verify/_verify_parse.html.
 *
 * The markers are read from the exported answer_format block rather than
 * written out here, for the same reason the Python parser imports them:
 * a parser that spells a marker differently from the prompt that demanded
 * it will silently stop finding blocks.
 */

/* Python's repr() for a string, which is what the warning text embeds.
   Prefers single quotes, switches to double when the value contains a
   single quote and no double, and escapes the usual controls. */
function pyRepr(s) {
  const body = String(s)
    .replace(/\\/g, '\\\\')
    .replace(/\n/g, '\\n')
    .replace(/\r/g, '\\r')
    .replace(/\t/g, '\\t');
  if (body.includes("'") && !body.includes('"')) return `"${body}"`;
  return `'${body.replace(/'/g, "\\'")}'`;
}

/* Python's str.strip() trims a wider set than JavaScript's trim() does not
   — in fact trim() is the wider one, since it also strips U+FEFF and the
   Unicode space separators. For the ASCII whitespace these texts contain
   the two agree; this is named so the difference is a decision and not an
   oversight. */
const strip = s => s.trim();

export class ParseResult {
  constructor() {
    this.records = [];
    this.warnings = [];
    this.explicitNoFindings = false;
    this.blockFound = false;
  }
  get flags() {
    return this.records.filter(r => 'FLAG' in r).map(r => r.FLAG);
  }
  /* True when a block was found, even if it declared no findings. A run
     that said NO FINDINGS answered the question; a run with no block did
     not answer it at all. */
  get isScoreable() { return this.blockFound; }
}

/* `format` is the answer_format block from data/tools/system_prompt.json.
   `documentedColumns` is a Set of the dictionary's column names, used only
   for the warning that a FLAG is not a documented name; pass null to skip
   that check, which is what a caller without the dictionary loaded should
   do rather than guess. */
export function parseFinalAnswer(text, format, documentedColumns = null) {
  const out = new ParseResult();
  const ANSWER_START = format.start;
  const ANSWER_END = format.end;
  const SEPARATOR = format.record_separator;
  const NO_FINDINGS = format.no_findings_marker;
  const FIELD_ORDER = format.field_order;
  const CONFIDENCE_VALUES = format.confidence_values;
  const DELIMITER = format.verbatim_delimiter;

  let body_text = String(text ?? '');

  // The runner prefixes a header; everything after the delimiter is the
  // model's own text. Absence of the delimiter is fine — the caller may be
  // passing raw text, which is always the case in a browser run.
  if (DELIMITER && body_text.includes(DELIMITER)) {
    body_text = body_text.slice(body_text.indexOf(DELIMITER) + DELIMITER.length);
  }

  const starts = countOccurrences(body_text, ANSWER_START);
  const ends = countOccurrences(body_text, ANSWER_END);

  if (starts === 0) {
    out.warnings.push(
      `missing start marker: no ${pyRepr(ANSWER_START)} in the answer`);
    return out;
  }
  if (starts > 1) {
    out.warnings.push(
      `repeated start marker: ${pyRepr(ANSWER_START)} appears ${starts} times; ` +
      `the first is used`);
  }
  if (ends === 0) {
    out.warnings.push(
      `unclosed block: no ${pyRepr(ANSWER_END)} after the start marker`);
    return out;
  }
  if (ends > 1) {
    out.warnings.push(
      `repeated end marker: ${pyRepr(ANSWER_END)} appears ${ends} times; ` +
      `the first is used`);
  }

  out.blockFound = true;
  const afterStart = body_text.slice(
    body_text.indexOf(ANSWER_START) + ANSWER_START.length);
  const cut = afterStart.indexOf(ANSWER_END);
  // partition(): everything before the first end marker, everything after.
  let body = cut === -1 ? afterStart : afterStart.slice(0, cut);
  const trailing = cut === -1 ? '' : afterStart.slice(cut + ANSWER_END.length);

  if (strip(trailing)) {
    // " ".join(trailing.split()) — collapse every run of whitespace.
    const preview = trailing.split(/\s+/).filter(Boolean).join(' ').slice(0, 60);
    out.warnings.push(
      `text after the end marker: ${strip(trailing).length} characters ` +
      `follow the block (${pyRepr(preview)}...)`);
  }

  body = strip(body);
  if (body === NO_FINDINGS) {
    out.explicitNoFindings = true;
    return out;
  }
  if (!body) {
    out.warnings.push(
      `empty block: nothing between the markers, and the ` +
      `${pyRepr(NO_FINDINGS)} marker was not used`);
    return out;
  }

  const chunks = body.split(SEPARATOR).map(strip);
  chunks.forEach((chunk, idx) => {
    const i = idx + 1;
    if (!chunk) {
      out.warnings.push(
        `record ${i}: empty record, which means a stray ` +
        `${pyRepr(SEPARATOR)} separator`);
      return;
    }

    const rec = {};
    const seenOrder = [];
    const stray = [];
    for (let line of chunk.split(/\r\n|\r|\n/)) {
      line = strip(line);
      if (!line) continue;
      // str.partition(":") — split on the FIRST colon only.
      const at = line.indexOf(':');
      const name = at === -1 ? strip(line) : strip(line.slice(0, at));
      const value = at === -1 ? '' : line.slice(at + 1);
      if (at === -1 || !FIELD_ORDER.includes(name)) {
        stray.push(line);
        continue;
      }
      if (name in rec) {
        out.warnings.push(
          `record ${i}: field ${name} given more than once; the first is used`);
        continue;
      }
      rec[name] = strip(value);
      seenOrder.push(name);
    }

    if (stray.length) {
      const preview = stray.slice(0, 2).map(s => s.slice(0, 40)).join('; ');
      out.warnings.push(
        `record ${i}: ${stray.length} line(s) are not one of ` +
        `${FIELD_ORDER.join(', ')} (${preview})`);
    }

    const missing = FIELD_ORDER.filter(f => !(f in rec));
    if (missing.length) {
      out.warnings.push(`record ${i}: missing field(s) ${missing.join(', ')}`);
    } else if (seenOrder.length !== FIELD_ORDER.length
               || seenOrder.some((f, n) => f !== FIELD_ORDER[n])) {
      out.warnings.push(
        `record ${i}: fields out of order - got ${seenOrder.join(', ')}, ` +
        `expected ${FIELD_ORDER.join(', ')}`);
    }

    const flag = rec.FLAG ?? '';
    if (flag && documentedColumns && !documentedColumns.has(flag)) {
      out.warnings.push(
        `record ${i}: FLAG ${pyRepr(flag)} is not a documented column name; ` +
        `it is scored as given, and will count against precision`);
    }

    const conf = 'CONFIDENCE' in rec ? rec.CONFIDENCE : null;
    if (conf !== null && !CONFIDENCE_VALUES.includes(conf)) {
      out.warnings.push(
        `record ${i}: CONFIDENCE ${pyRepr(conf)} is not one of ` +
        `${CONFIDENCE_VALUES.join(', ')}`);
    }

    if (flag) {
      out.records.push(rec);
    } else {
      out.warnings.push(
        `record ${i}: no usable FLAG, so the record is not scored`);
    }
  });

  return out;
}

function countOccurrences(haystack, needle) {
  if (!needle) return 0;
  let n = 0, from = 0;
  for (;;) {
    const at = haystack.indexOf(needle, from);
    if (at === -1) return n;
    n += 1;
    from = at + needle.length;
  }
}
