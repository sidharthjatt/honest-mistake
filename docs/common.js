/* Shared helpers. Every figure on every page is read from the JSON at
   runtime; nothing here carries a number of its own. */

const DATA = 'data/';

async function getJSON(path) {
  const res = await fetch(DATA + path, { cache: 'no-cache' });
  if (!res.ok) throw new Error(path + ' could not be loaded (' + res.status + ').');
  return res.json();
}

function el(tag, attrs, ...kids) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'class') node.className = v;
    else if (k === 'text') node.textContent = v;
    else if (k === 'html') node.innerHTML = v;
    else node.setAttribute(k, v);
  }
  for (const kid of kids.flat()) {
    if (kid === null || kid === undefined || kid === false) continue;
    node.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return node;
}

/* Element.append() renders null as the string "null", so anything built from
   conditional branches goes through here rather than through append directly. */
function add(node, ...kids) {
  for (const kid of kids.flat()) {
    if (kid === null || kid === undefined || kid === false) continue;
    node.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return node;
}

function pill(cls, label) {
  return el('span', { class: 'pill ' + cls, text: label });
}

function dash() {
  return el('span', { class: 'dash', text: '—' });
}

function bytes(n) {
  return Number(n).toLocaleString('en-US');
}

/* A datetime as written in the record, with no conversion or re-formatting:
   the export wrote an offset and re-rendering it would change what it says. */
function asRecorded(s) {
  return s === null || s === undefined ? '—' : String(s);
}

function shortHash(h) {
  return String(h).slice(0, 12);
}

function replayHref(label, hash) {
  return 'replay.html?run=' + encodeURIComponent(label) + (hash || '');
}

function flagAnchor(name) {
  return 'flag-' + String(name).replace(/[^A-Za-z0-9_-]/g, '_');
}

function prettyJSON(value) {
  return JSON.stringify(value, null, 2);
}

/* Tool results are JSON strings in the record. Pretty-print when they parse,
   and otherwise show the string exactly as it was returned. */
function formatResult(raw) {
  if (typeof raw !== 'string') return prettyJSON(raw);
  const t = raw.trim();
  if (t.startsWith('{') || t.startsWith('[')) {
    try { return prettyJSON(JSON.parse(t)); } catch (e) { /* leave it alone */ }
  }
  return raw;
}

function setStatus(node, message, isError) {
  node.replaceChildren(el('p', { class: 'status' + (isError ? ' error' : ''), text: message }));
}

/* The provenance block, built from bundle.json and placed on every page.
   It is open on first paint rather than tucked away. */
function renderProvenance(bundle) {
  const stripped = bundle.stripped || {};
  const inner = el('div', { class: 'inner' });

  inner.append(
    el('h4', { text: 'This bundle' }),
    el('p', { class: 'prov-line' },
      el('b', { text: 'Exported ' }), asRecorded(bundle.exported_at),
      ' from commit ',
      el('code', { text: shortHash(bundle.exported_from_commit) }), '.'),
    el('p', { class: 'prov-line' },
      el('b', { text: 'Uncommitted changes in the source paths at export: ' }),
      (bundle.uncommitted_changes_in_source_paths || []).length === 0
        ? 'none.'
        : (bundle.uncommitted_changes_in_source_paths || []).join(', ')),
    el('p', { class: 'prov-line' },
      el('b', { text: 'Export script SHA-256: ' }),
      el('code', { text: shortHash(bundle.export_script_sha256) }))
  );

  add(inner,
    el('h4', { text: 'What was stripped, and why' }),
    el('p', { class: 'prov-line' },
      el('b', { text: (stripped.fields || []).join(', ') }),
      ' — ', bytes(stripped.bytes_removed || 0), ' bytes removed.'),
    el('p', { class: 'note', text: stripped.why || '' }),
    bundle.reasoning_note ? el('p', { class: 'note', text: bundle.reasoning_note }) : null
  );

  inner.append(
    el('h4', { text: 'Scoring cannot be recomputed from a fresh clone' }),
    el('div', { class: 'caveat' }, bundle.scoring_note || '')
  );

  const hashes = el('div', { class: 'hashes' });
  for (const [file, hash] of Object.entries(bundle.scoring_sources_sha256 || {})) {
    hashes.append(el('div', {}, el('b', { text: file }), ' ', hash));
  }
  inner.append(el('h4', { text: 'Every file the scoring was built from' }), hashes);

  if ((bundle.cannot_carry || []).length) {
    const list = el('ul', { class: 'plain note' });
    for (const item of bundle.cannot_carry) {
      list.append(el('li', {}, el('b', { text: item.what }), ' — ', item.why));
    }
    inner.append(el('h4', { text: 'What this bundle cannot carry' }), list);
  }

  return el('details', { class: 'prov', open: 'open' },
    el('summary', { text: 'Provenance — where every figure on this page comes from' }),
    inner);
}

async function mountProvenance(node) {
  try {
    node.replaceChildren(renderProvenance(await getJSON('bundle.json')));
  } catch (err) {
    node.replaceChildren(el('p', { class: 'status error', text: 'Provenance unavailable: ' + err.message }));
  }
}
