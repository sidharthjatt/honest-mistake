/* Screen 3: score the run, reveal the candidate, compare against the twelve.
 *
 * This module renders from one record and nothing else. That is deliberate
 * and it is the point of the file boundary: the candidate a run audited is
 * a property of the run, and the assignment scan.js deals at boot belongs
 * to the *next* run. A restored run rendered against the current deal would
 * name the wrong candidate half the time and look entirely correct doing
 * it — a silent failure, in the worst way.
 *
 * So nothing here imports the assignment, and there is no parameter to
 * pass it in by. render() reads record.variant, which travels with the
 * record through sessionStorage and into the downloaded file. If that
 * coupling is ever wanted, it has to be added on purpose rather than
 * reached for by accident.
 *
 * The copy carries one argument that the ordering depends on: a flag can
 * be credited for naming a leaking column the audited model never read,
 * because the scorer matches names against the key. Section 2 states that
 * in two sentences; the card makes the case, because a visitor who scrolls
 * to their own flags never read section 2.
 */

import { AnswerKey, score } from './scoring.js';
import { parseFinalAnswer } from './parse.js';
import { costOf } from './models.js';
import { TEST_YEAR } from './pipeline.js';
import { count, word } from './words.js';
import { COMPLETED, TURN_LIMIT, ABORTED } from './loop.js';

const $n = (tag, attrs = {}, ...kids) => {
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
};

const money = v => (v < 0.01 ? `$${v.toFixed(4)}` : v < 1 ? `$${v.toFixed(3)}` : `$${v.toFixed(2)}`);
const num = v => Number(v).toLocaleString('en-US');


/* "11, 12, 14, 16 and 16", not "11, 12, 14, 16, 16". A list read aloud
   wants the conjunction, and these are read aloud in the head. */
const listOf = xs => xs.length < 2 ? String(xs[0] ?? '')
  : `${xs.slice(0, -1).join(', ')} and ${xs.at(-1)}`;

/* ---------------------------------------------------------------- scoring */

/* Everything screen 3 shows, derived once. `record` is the run; `data` is
   the answer key, the two feature lists and the run index. */
export function scoreRun(record, data) {
  const key = new AnswerKey(data.scoring);
  const features = data.features[record.variant];
  const parsed = parseFinalAnswer(record.finalText, data.answerFormat, data.documented);

  if (!parsed.isScoreable) {
    return { scoreable: false, parsed, key, features };
  }
  const result = score(parsed.flags, key, record.canaryPresent, features);
  return { scoreable: true, parsed, key, features, result };
}

/* What the key says about one flag, and therefore which card it gets. The
   five verdicts are ordered by how the copy reads them, not by severity. */
function verdictOf(flag, result, key, featureSet) {
  const resolved = key.resolve(flag);
  const column = resolved.name;
  const isInput = featureSet.has(column);

  if (result.out_of_scope_flagged.includes(flag)) {
    return { kind: 'out_of_scope', column, isInput, resolved };
  }
  if (result.true_positives.includes(flag)) {
    return { kind: isInput ? 'credited' : 'credited_unreachable', column, isInput, resolved };
  }
  if (result.hard_negatives_flagged.includes(flag)) {
    return { kind: 'hard_negative', column, isInput, resolved };
  }
  return { kind: 'not_credited', column, isInput, resolved };
}

/* ---------------------------------------------------------------- render */

export function render(record, data, scored) {
  const out = $n('div', { class: 's3' });
  const honest = !record.canaryPresent;

  out.append(sectionReveal(record, data, honest));

  if (!scored.scoreable) {
    out.append(sectionNoVerdict(record, data));
    /* A run with no reply has nothing to compare. */
    if (record.turns > 0) out.append(sectionCompare(record, data));
    return out;
  }

  out.append(sectionFindable(record, data, scored, honest));
  out.append(sectionFlags(record, data, scored));
  out.append(sectionCanary(scored.result, data));
  out.append(sectionCompare(record, data));
  out.append(sectionMetrics(scored.result, data, scored.features));
  return out;
}

/* ---- 1. the reveal. Reads record.variant, never a current assignment. -- */

function sectionReveal(record, data, honest) {
  const f = data.prompts.figures_by_variant;
  const box = $n('section', { class: 's3-block s3-reveal' });
  /* A run with no reply audited nothing, so it can't say "audited". */
  const verb = record.turns === 0 ? 'chose' : 'audited';
  box.append($n('h2', { text: `You ${verb} Candidate ${record.card}. It was ` +
    (honest ? 'the honest model.' : 'the one carrying the canary.') }));

  if (honest) {
    box.append($n('p', {}, 'Nothing was planted in it. All ',
      word(data.keyCounts.truePositives), ' columns the answer key lists as leaking ' +
      'were taken out before this model was built, and none of them is among its ',
      num(data.featureCounts.layer1), ' inputs. The ',
      $n('b', { text: f.layer1.test_roc_auc_text }),
      ` it scores on held-out ${TEST_YEAR} loans is what the model is actually worth.`));
  } else {
    /* The column's name, what it holds and why it leaks all come from the
       key's own entry for it. No claim about the key as a whole: it also
       holds hard negatives and out-of-scope columns, and even its leaking
       columns share only a negative definition. */
    const column = data.canaryColumn;
    const tp = data.tpByColumn[column];
    box.append($n('p', {}, 'One column was put back: ',
      $n('code', { text: column }), '.',
      tp && tp.description ? ` The dictionary describes it as “${tp.description}”` : '',
      tp && tp.tier
        ? ` The answer key lists it at tier ${tp.tier} — ${tp.tier_label}.`
        : ' The answer key lists it as leaking, without a tier.',
      ' It is the whole of the gap you saw on the first screen — ',
      $n('b', { text: f.canary.test_roc_auc_text }), ' with it, ',
      $n('b', { text: f.layer1.test_roc_auc_text }), ' without.'));
  }
  return box;
}

/* ---- 2. what was there to find. Two sentences; the card explains. ------ */

function sectionFindable(record, data, scored, honest) {
  const box = $n('section', { class: 's3-block' });
  box.append($n('h3', { text: 'What was there to find' }));
  const n = data.featureCounts[record.variant];

  if (honest) {
    box.append($n('p', {}, 'The model has ', num(n), ' inputs, and not one of them ' +
      'is a column the answer key scores — all ', word(data.keyCounts.truePositives),
      ' were taken out before it was built. The key matches flags by name and does ' +
      'not check that, so a leaking column can still be named and credited; the ' +
      'cards below mark which of your flags the model was actually reading.'));
  } else {
    box.append($n('p', {}, 'The model has ', num(n), ' inputs, and one of them is a ' +
      'column the key scores: ', $n('code', { text: data.canaryColumn }),
      '. That was the leak and the only one in the model — the other ',
      word(data.keyCounts.truePositives - 1),
      ' are in the dictionary but not in it, so the cards below mark which of your ' +
      'flags the model was actually reading.'));
  }
  return box;
}

/* ---- 3. the flags ----------------------------------------------------- */

function sectionFlags(record, data, scored) {
  const { result, key, features } = scored;
  const featureSet = new Set(features);
  const box = $n('section', { class: 's3-block' });
  box.append($n('h3', { text: 'What the scorer made of your flags' }));
  /* run3 is the example because its flags were a fair objection that the key
     does not score. How many it flagged, and that it scored zero, are read
     from its own recorded score; if the bundle ever says otherwise, the
     example is left out rather than misstated. */
  const run3 = data.scoredByLabel.run3?.score;
  const run3Example = run3 && run3.precision === 0 && run3.false_positives?.length
    ? ` — run3 flagged ${word(run3.false_positives.length)} ` +
      `${run3.false_positives.length === 1 ? 'column that is' : 'columns that are'} ` +
      `near-constant in the ${TEST_YEAR} window, which is a real objection to reading ` +
      'the held-out figure as a forecast, and scored zero for it'
    : '';
  box.append($n('p', { class: 's3-framing' },
    'The key scores one kind of problem: columns carrying information that could ' +
    'only be known after the loan’s outcome. It is narrow on purpose. A flag it ' +
    `does not credit is not automatically wrong${run3Example}. What follows is the ` +
    'scorer’s verdict, not a ruling on whether you were right.'));

  if (!scored.parsed.records.length) {
    box.append($n('p', { class: 'note', text:
      'The agent reported no findings. Nothing to score, and on this candidate ' +
      'that may well be the right answer.' }));
    return box;
  }

  const cards = $n('div', { class: 's3-cards' });
  for (const rec of scored.parsed.records) {
    cards.append(flagCard(rec, verdictOf(rec.FLAG, result, key, featureSet), record, data, result));
  }
  box.append(cards);
  return box;
}

const VERDICT_LABEL = {
  credited: 'Credited.',
  credited_unreachable: 'Credited — and a good catch, though not about this model.',
  hard_negative: 'Not credited — and this is the interesting one.',
  not_credited: 'Not credited.',
  out_of_scope: 'Not scored.',
};

function flagCard(rec, verdict, record, data, result) {
  const card = $n('div', { class: `s3-card v-${verdict.kind}` });
  card.append($n('div', { class: 's3-card-head' },
    $n('code', { class: 's3-flag', text: rec.FLAG }),
    rec.CONFIDENCE ? $n('span', { class: 's3-conf', text: `confidence: ${rec.CONFIDENCE}` }) : null));

  card.append($n('p', { class: 's3-verdict' },
    $n('b', { text: VERDICT_LABEL[verdict.kind] }), ' ',
    ...verdictBody(rec, verdict, record, data, result)));

  if (rec.REASON) {
    card.append($n('div', { class: 's3-said' },
      $n('div', { class: 's3-said-k', text: 'the agent said' }),
      $n('p', { text: rec.REASON })));
  }
  if (rec.EVIDENCE) {
    card.append($n('div', { class: 's3-said' },
      $n('div', { class: 's3-said-k', text: 'resting on' }),
      $n('p', { text: rec.EVIDENCE })));
  }
  return card;
}

/* What the key says about one of its own columns, in its own words. The
   outcome sentence belongs to loan_status alone and is keyed on the name:
   another tier-A column is post-outcome without being the outcome. A column
   with no tier is one whose description matched none of the lifecycle
   phrases the tiers are built from; the published key carries no
   description for those, so none is shown. */
function aboutKeyColumn(column, tp) {
  if (column === 'loan_status') {
    return [' at tier A, the most explicit kind: it is the loan’s own outcome, and ' +
      '“Charged Off” is the thing being predicted. Naming it means reading the ' +
      'dictionary and recognising a column that could only be known after the fact.'];
  }
  if (!tp || !tp.tier) {
    return [' without a tier. Its dictionary description carries none of the ' +
      'lifecycle wording the tiers are matched on, so there was no phrase to spot. ' +
      'Naming it means knowing what the column holds, not reading when it is filled in.'];
  }
  return [
    ` at tier ${tp.tier} — ${tp.tier_label}.`,
    tp.description ? ` The dictionary describes it as “${tp.description}”` : '',
    ' Naming it means reading the dictionary and recognising a column that could ' +
    'only be known after the fact.',
  ];
}

function verdictBody(rec, verdict, record, data, result) {
  const tp = data.tpByColumn[verdict.column];
  const nInputs = num(data.featureCounts[record.variant] ?? 0);

  switch (verdict.kind) {
    case 'credited':
      return [
        $n('code', { text: verdict.column }), ' is one of the ',
        word(data.keyCounts.truePositives), ' columns the key scores, and it is one ' +
        'of this model’s inputs.',
        tp && tp.tier ? ` Tier ${tp.tier} — ${tp.tier_label}.` : ' The key gives it no tier.',
      ];

    /* The one the copy was rewritten for. It has to stand alone: someone
       who scrolls straight to their own flags never read section 2. */
    case 'credited_unreachable':
      return [
        $n('code', { text: verdict.column }), ' is in the answer key',
        ...aboutKeyColumn(verdict.column, tp),
        ' That is the skill the whole benchmark is trying to measure.',
        $n('br'), $n('br'),
        'It is not one of the model’s ', nInputs, ' inputs. It was removed before ' +
        'the model was built, so reading it back does not tell you anything is wrong ' +
        'with the held-out figure — the model never had it.',
        $n('br'), $n('br'),
        'The scorer credits it anyway, because it matches names against the key and ' +
        'does not ask what the model read. Your precision of ',
        result.precision.toFixed(2), ' includes this flag. The scoring records the ' +
        'distinction as ', $n('code', { text: 'reachable: false' }),
        ' rather than taking the credit away.',
      ];

    case 'hard_negative':
      return [
        $n('code', { text: verdict.column }), ' is one of ',
        word(data.keyCounts.hardNegatives), ' columns put in the key precisely because ' +
        'they look like leakage without being it. Flagging one means the agent went ' +
        'after the right kind of thing and landed on a column that holds up.',
        verdict.resolved.kind
          ? [' It was scored as ', $n('code', { text: verdict.column }),
             ', the column it derives from.']
          : '',
      ];

    case 'not_credited':
      return [
        $n('code', { text: rec.FLAG }), verdict.isInput
          ? [' is one of the model’s ', nInputs, ' inputs and is not a column the ' +
             'key scores. It may still be a fair objection, but the key scores ' +
             'post-outcome information only, and this earns nothing.']
          : [' is not one of the model’s inputs and is not a column the key ' +
             'scores. It earns nothing, and the model was not reading it either.'],
      ];

    /* The key's reason is written for the key, not for a visitor, and
       half of it means nothing outside the repository. Quoting it, or
       cutting it down to the part that reads well, are both worse than
       saying only what can be said plainly. But the card still says the
       reason exists and where to read it, rather than leaving it out as
       if there were none. No other page on the site shows it. */
    case 'out_of_scope':
      return [
        $n('code', { text: verdict.column }), ' is out of scope. The key sets it ' +
        'aside, and it counts neither for you nor against you.',
        $n('br'), $n('br'),
        'The key does record why, but in wording written for the scorer rather ' +
        'than for you; it is in ',
        $n('a', { href: 'https://github.com/sidharthjatt/honest-mistake/blob/main/agent/answer_key.py',
                  text: 'agent/answer_key.py' }),
        ', under ', $n('code', { text: 'OUT_OF_SCOPE' }), '.',
      ];
    default:
      return [''];
  }
}

/* ---- the three canary states ------------------------------------------ */

function sectionCanary(result, data) {
  const c = result.canary;
  const box = $n('section', { class: 's3-block s3-canary' });
  box.append($n('h3', { text: 'The canary' }));

  if (c.applicable === false) {
    box.append($n('p', { class: 's3-canary-line na' },
      $n('b', { text: 'No canary here. ' }),
      'Nothing was planted in this candidate, so there was nothing to find, and not ' +
      'finding it is the right answer. This is not a zero. The question does not ' +
      'apply, and the scorer records it as ', $n('code', { text: 'null' }),
      ' rather than ', $n('code', { text: 'false' }),
      ' — a run cannot miss a test it was never set.'));
    return box;
  }
  if (c.applicable === null) {
    box.append($n('p', { class: 's3-canary-line na', text:
      'Whether a canary was planted in this candidate was not recorded, so this ' +
      'run cannot be read either way.' }));
    return box;
  }

  const planted = c.planted.join(', ');
  const detail = c.detail[c.planted[0]] || {};
  if (c.detected) {
    box.append($n('p', { class: 's3-canary-line found' },
      $n('b', { text: 'You found it. ' }), $n('code', { text: planted }),
      ' was planted in this model and you flagged it. That is the test, and you ' +
      'passed it.'));
  } else {
    const drop = (detail.canary_test_roc_auc != null && detail.baseline_test_roc_auc != null)
      ? (detail.canary_test_roc_auc - detail.baseline_test_roc_auc).toFixed(4) : null;
    /* "Largest" is read off the canary model's own ranking (shap_global,
       most important first), not assumed. */
    const largest = data.features.canary[0] === c.planted[0];
    box.append($n('p', { class: 's3-canary-line missed' },
      $n('b', { text: 'You did not find it. ' }), $n('code', { text: planted }),
      ' was among this model’s inputs and went unflagged.',
      largest ? ' It is the largest single contributor to the model’s score' : '',
      largest && drop ? `, and taking it out costs ${drop} of held-out AUC.`
        : largest ? '.'
        : drop ? ` Taking it out costs ${drop} of held-out AUC.` : ''));
  }
  return box;
}

/* ---- the truncated run ------------------------------------------------ */

/* The loop's own sentence describes how the run ended, which is not the
   same question as why there is no verdict. A run can end as `completed`
   and still have written nothing an answer could be read from, and using
   "the agent finished and gave its answer" to open a section headed "no
   verdict" says two opposite things in consecutive lines. */
/* A run with no reply at all (failed, cancelled or stopped before the
   model answered once) investigated nothing. It has no partial
   investigation to point at and no partial answer for the scorer to
   refuse, and a visitor who stopped it before the first request paid
   nothing. scan.js holds the same rule for Screen 2. */
function sectionNoVerdict(record, data) {
  const noReply = record.turns === 0;
  const box = $n('section', { class: 's3-block s3-noverdict' });
  box.append($n('h3', { text: 'No verdict, so nothing to score.' }));
  box.append($n('p', {},
    record.termination === COMPLETED
      ? 'The agent ended its turn without writing the findings block its brief ' +
        'asks for, so it stopped of its own accord but left nothing to read. ' +
        'What is on the previous screen is an investigation without a conclusion.'
      : [record.terminationSentence || 'The run ended before the agent wrote its findings.',
         /* With turns, the billing note sits on the comparison line next to
            the dollar figure. At zero turns there is no comparison, so it
            goes here instead, and only here. */
         noReply && record.termination === ABORTED
           ? ' The cancelled request may still be billed by Anthropic.' : '',
         noReply
           ? ' The model never replied, so there is no investigation on the previous ' +
             'screen, partial or otherwise.'
           : ' What is on the previous screen is a partial investigation, not a conclusion.']));
  /* On a run with no reply the heading already says there is nothing to
     score, so this line would only repeat it. */
  if (!noReply) {
    box.append($n('p', {}, 'The scorer that graded the ', word(data.index.runs.length),
      ' recorded runs refuses a run like this one, in its own words: a partial answer ' +
      'is not an answer, and is not scored.'));
  }
  /* The heading and the reveal above have already said which candidate it
     was. What they don't say is why a run with no verdict is told at all. */
  box.append($n('p', {}, noReply
    ? 'You are told which it was because reloading deals the two candidates again, ' +
      'so holding it back would buy you nothing.'
    : 'You are told which it was because you paid for the run, and because reloading ' +
      'deals the two candidates again, so holding it back would buy you nothing.'));
  return box;
}

/* ---- 4. against the twelve -------------------------------------------- */

function sectionCompare(record, data) {
  const box = $n('section', { class: 's3-block' });
  box.append($n('h3', { text: 'How your run compares' }));

  const runs = data.index.runs;
  const finished = v => runs
    .filter(r => !!r.canary.present === v && r.termination === COMPLETED)
    .map(r => r.turns).sort((a, b) => a - b);
  const honestTurns = finished(false);
  const canaryTurns = finished(true);
  const stopped = runs.filter(r => !r.canary.present && r.termination === TURN_LIMIT);
  const maxCalls = Math.max(...runs.filter(r => r.termination === COMPLETED)
    .map(r => r.tool_calls));

  box.append($n('p', { class: 's3-yours' },
    $n('b', { text: 'Your run: ' }),
    `${count(record.turns, 'turn')}, ${count(record.toolCalls, 'tool call')}, ${money(record.spend)}.`,
    /* Priced from reported usage, which a request cancelled in flight never
       gets. Same sentence as Screen 2. */
    record.termination === ABORTED
      ? ' The cancelled request is not in that figure, and may still be billed.' : ''));

  /* Every count here comes from the run index. A sentence that names one
     run's ceiling is only written when exactly one run hit it. */
  box.append($n('p', {},
    honestTurns.length
      ? ['Of the recorded runs on the honest model, those that finished took ',
         listOf(honestTurns), ' turns.']
      : '',
    stopped.length === 1
      ? ` One hit a ${stopped[0].limits.max_turns}-turn ceiling and was scored as no answer at all.`
      : stopped.length > 1
        ? ` ${count(stopped.length, 'run')} hit their turn ceilings and were scored as no answer at all.`
        : '',
    canaryTurns.length
      ? [' The ', word(canaryTurns.length), canaryTurns.length === 1 ? ' canary run finished in ' : ' canary runs finished in ',
         listOf(canaryTurns), ' — when there is something to find, the agent finds it and stops.']
      : ''));

  if (record.toolCalls > maxCalls) {
    box.append($n('p', {}, 'Your ', count(record.toolCalls, 'tool call'), ' are more ' +
      'than any recorded run made. The previous highest was ', String(maxCalls), '.'));
  }
  return box;
}

/* ---- the small print -------------------------------------------------- */

function sectionMetrics(result, data, features) {
  const box = $n('section', { class: 's3-block s3-smallprint' });
  box.append($n('h3', { text: 'The numbers the scorer produces' }));
  box.append($n('p', { class: 's3-figures', text:
    `Precision ${result.precision.toFixed(2)} · Recall ${result.recall.toFixed(3)} ` +
    `· F1 ${result.f1.toFixed(3)}` }));

  const reach = result.true_positive_reachability;
  const unreachable = Object.entries(reach.by_flag || {})
    .filter(([, ok]) => !ok).map(([f]) => f);

  /* Names the credited flags the model never read, as a list read aloud,
     and says whether that is all of the credited flags or only some. */
  const names = unreachable.flatMap((f, i) => [
    i === 0 ? '' : i === unreachable.length - 1 ? ' and ' : ', ',
    $n('code', { text: f })]);
  const n = unreachable.length;
  const all = n === result.true_positive_count;
  const cap = t => t[0].toUpperCase() + t.slice(1);
  if (result.scored_count) {
    box.append($n('p', {}, 'Precision is ', String(result.true_positive_count), ' of ',
      String(result.scored_count), '.',
      n
        ? [all
             ? (n === 1 ? ' The credited flag is ' : ' The credited flags are ')
             : ` ${cap(word(n))} of the credited flags ${n === 1 ? 'is' : 'are'} `,
           ...names,
           `, which the model never read — see ${n === 1 ? 'its card' : 'their cards'}.`]
        : ''));
  }

  /* Recall, split the way the scorer's own reachability field splits it.
     The scored figure credits a flag by name, whether or not the model reads
     the column, so it has no ceiling below the key's size. Only the part
     over columns this model reads is capped, by how many key columns are
     among its inputs. That count comes from its own feature list. */
  const total = data.keyCounts.truePositives;
  const inModel = features.filter(f => f in data.tpByColumn).length;
  const over = inModel === 1 ? 'that one column' : `those ${word(inModel)} columns`;
  box.append($n('p', {}, 'Recall is ', String(result.true_positive_count), ' of ',
    String(total), '. The denominator is every leaking column in the key, and a flag ' +
    'is credited by name, whether or not this model reads the column.',
    inModel === 0
      ? [' This model reads none of the ', word(total), ', so counted over the columns ' +
         'it reads there was nothing to find.']
      : reach.known
        ? [' This model reads ', word(inModel), ' of the ', word(total), '; counted over ',
           over, ', your recall is ', String(reach.reachable_count), ' of ', String(inModel), '.']
        : [' This model reads ', word(inModel), ' of the ', word(total), '. Which of your ' +
           'credited flags name them was not recorded.']));

  /* The recorded example, read from its own score. If the bundle does not
     carry it, or it did not credit the planted column, it is left out: the
     number it quotes is never supplied from here. */
  const run5 = data.scoredByLabel['run5-canary']?.score;
  if (run5 && typeof run5.recall === 'number' && run5.true_positives?.includes(data.canaryColumn)) {
    box.append($n('p', {}, 'For comparison, ', $n('code', { text: 'run5-canary' }),
      ' flagged the one planted column, the only one there was, and scored a recall of ',
      String(run5.recall), ' for it.'));
  }

  box.append($n('p', {}, 'That is why these three sit down here. They are the ' +
    'scorer’s output, unchanged, and as a mark out of ten they are wrong about ' +
    'what happened.'));
  return box;
}
