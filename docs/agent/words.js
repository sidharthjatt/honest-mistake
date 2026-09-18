/* A count and its noun, agreeing: "1 turn", "2 turns", "0 tool calls".
 * Every count of turns or tool calls the pages print goes through here, so
 * that a run which happens to make exactly one of something doesn't read
 * as "1 turns".
 */
export function count(n, noun, plural = `${noun}s`) {
  return `${Number(n).toLocaleString('en-US')} ${n === 1 ? noun : plural}`;
}

/* Numbers a sentence reads better for having spelled out. Only as far as
   the copy needs; anything larger stays a numeral. */
const WORDS = { 0: 'none', 1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five',
                6: 'six', 7: 'seven', 8: 'eight', 9: 'nine', 10: 'ten', 11: 'eleven',
                12: 'twelve', 13: 'thirteen', 14: 'fourteen', 38: 'thirty-eight',
                39: 'thirty-nine', 41: 'forty-one', 55: 'fifty-five' };
export const word = n => WORDS[n] ?? Number(n).toLocaleString('en-US');
