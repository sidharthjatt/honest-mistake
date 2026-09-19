/* Whether a run produced a verdict. Screen 2's banner and title and Screen
 * 3's score all ask this question, and they call this one function so that
 * they can't disagree.
 *
 * A run the agent didn't end itself has no verdict, whatever its text
 * holds. That is eval_canary.refusal_reason: only a completed run is usable,
 * and anything else is refused before its answer is parsed.
 *
 * Only the final answer is read: the text of the last turn that wrote any.
 * That is what agent.py keeps as final_text, and what the recorded runs
 * were scored on. A findings block written in an earlier turn doesn't
 * count, and the markers come from the same answer_format the parser
 * reads, not from a copy kept here.
 *
 * When there is no verdict, `missing` says which way the answer fell short,
 * so both screens can say the same true thing about it.
 */

import { parseFinalAnswer } from './parse.js';
import { COMPLETED } from './loop.js';

/* The ways a completed run can leave no verdict. The parser has two
   exits before it finds a block (no start marker; a start marker with no
   end), and the delimiter cut can sit in front of either. NO_TEXT is not
   one of the parser's outcomes: to the parser an empty answer is just a
   missing start marker, so it is told apart by the text, here. */
export const NO_TEXT = 'no_text';
export const NO_START = 'no_start';
export const UNCLOSED = 'unclosed';
export const CUT_NO_START = 'cut_no_start';
export const CUT_UNCLOSED = 'cut_unclosed';

export function readVerdict(finalText, termination, answerFormat, documentedColumns = null) {
  // Refused before parsing, as the Python scorer does, so `parsed` is null.
  if (termination !== COMPLETED) return { scoreable: false, parsed: null, missing: null };
  const parsed = parseFinalAnswer(finalText, answerFormat, documentedColumns);
  if (parsed.isScoreable) return { scoreable: true, parsed, missing: null };
  return { scoreable: false, parsed, missing: whyNoBlock(finalText, parsed) };
}

function whyNoBlock(finalText, parsed) {
  // Whitespace is nothing a visitor can read, so it counts as no text.
  if (!String(finalText ?? '').trim()) return NO_TEXT;
  const unclosed = parsed.noBlock === 'unclosed';
  if (parsed.cutAtDelimiter) return unclosed ? CUT_UNCLOSED : CUT_NO_START;
  return unclosed ? UNCLOSED : NO_START;
}

/* The sentence that opens the no-verdict text on both screens. "In the
   required form" is there because the parser matches the markers exactly:
   a near-miss spelling is invisible to it and visible to the visitor. The
   two CUT_ cases need the model to write the runner's internal delimiter
   line unprompted, since it is never shown it. They are rare, but they
   must not fall through to a sentence that is false for them. */
export function finishedWithout(missing) {
  switch (missing) {
    case NO_TEXT:
      return 'The agent finished, but it wrote no final answer.';
    case UNCLOSED:
      return 'The agent finished, but its final answer began a findings block ' +
        'and did not close it in the required form.';
    case CUT_NO_START:
      return 'The agent finished, but its final answer contained a line the scorer ' +
        'treats as the start of the answer, and no findings block in the required ' +
        'form after it.';
    case CUT_UNCLOSED:
      return 'The agent finished, but its final answer contained a line the scorer ' +
        'treats as the start of the answer, and the findings block after that line ' +
        'was not closed in the required form.';
    case NO_START:
      return 'The agent finished, but its final answer contained no findings block ' +
        'in the required form.';
    default:
      throw new Error(`No sentence for a run without a verdict of kind ${missing}.`);
  }
}
