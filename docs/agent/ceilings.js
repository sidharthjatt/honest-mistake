export const BUILD = 'ed6b67583fac';
/* The spend beside its ceiling, and the sentence for a run the spend
 * ceiling stopped, shared by Screen 2 and Screen 3 so they write the same
 * figures the same way.
 *
 * The gate is spend >= ceiling, tested after each turn, so a run it stops
 * has spent at least the ceiling: exactly the ceiling, or past it. Each
 * screen passes its own money formatter, so the figures here are written
 * the way the rest of that screen writes them.
 */

/* The spend written so it can be told apart from the ceiling whenever the
   two differ. The formatter rounds to the cent from $1 up, so $1.002
   against $1.00 would read "$1.00, past your ceiling of $1.00". Places
   are added until the two differ. The loop ends: two unequal doubles as
   large as the smallest ceiling differ within eighteen decimal places.
   Anywhere the spend is shown next to the ceiling uses this, so a figure
   in a sentence can't disagree with the same figure on the meter. */
export function spentApart(spend, ceiling, money) {
  const s = money(spend);
  if (spend === ceiling || s !== money(ceiling)) return s;
  let d = 3;
  while (spend.toFixed(d) === ceiling.toFixed(d)) d += 1;
  return `$${spend.toFixed(d)}`;
}

export function spendStopSentence(spend, ceiling, money) {
  return `The run had spent ${spentApart(spend, ceiling, money)} when its last turn ` +
    `ended, ${spend > ceiling ? 'past' : 'at'} your ceiling of ${money(ceiling)}, so it ` +
    `was stopped before it could send another request.`;
}
