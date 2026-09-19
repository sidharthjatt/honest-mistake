/* The models a visitor may choose, and how each one's request differs.
 *
 * Prices are $ per million tokens, as platform.claude.com/docs/en/about-
 * claude/pricing listed them when it was checked on PRICES_CHECKED. They
 * are here so a run can be costed from its own usage numbers rather than
 * guessed at. That page also says Sonnet 5's $2/$10, introductory at
 * launch, is now its standard price. The tool-use system prompt counts
 * below come from the same page.
 *
 * `shape` is the part that is not cosmetic. Sonnet 5 takes adaptive
 * thinking and an effort level; Haiku 4.5 takes neither and wants the
 * older budget_tokens form instead. Sending one model's shape to the
 * other is a 400, so the shape travels with the model rather than being
 * decided at the call site.
 */

export const PRICES_CHECKED = '2026-09-19';

export const MODELS = [
  {
    id: 'claude-sonnet-5',
    label: 'Claude Sonnet 5',
    note: 'What the twelve recorded runs used. Pick this to compare like with like.',
    isDefault: true,
    shape: 'adaptive',
    maxTokens: 12400,
    effort: 'high',
    contextWindow: 1000000,
    maxOutput: 128000,
    toolUseSystemPromptTokens: 354,
    retirementNotBefore: '2027-06-30',
    price: { input: 2, output: 10, cacheWrite5m: 2.5, cacheRead: 0.2 },
  },
  {
    id: 'claude-haiku-4-5-20251001',
    label: 'Claude Haiku 4.5',
    note: 'Cheaper and faster. Not the model the recorded runs used.',
    isDefault: false,
    shape: 'budget',
    maxTokens: 12400,
    thinkingBudgetTokens: 4000,
    contextWindow: 200000,
    maxOutput: 64000,
    toolUseSystemPromptTokens: 496,
    retirementNotBefore: '2026-10-15',
    price: { input: 1, output: 5, cacheWrite5m: 1.25, cacheRead: 0.1 },
  },
];

export const DEFAULT_MODEL_ID = MODELS.find(m => m.isDefault).id;

export function getModel(id) {
  return MODELS.find(m => m.id === id) || null;
}

/* Cost of one run from its own usage counters, at that model's rates.
   Cache writes are billed at the 5-minute rate: the loop never sets a
   longer TTL. */
export function costOf(model, usage) {
  const p = model.price;
  return (
    (usage.input || 0) / 1e6 * p.input +
    (usage.cache_creation || 0) / 1e6 * p.cacheWrite5m +
    (usage.cache_read || 0) / 1e6 * p.cacheRead +
    (usage.output || 0) / 1e6 * p.output
  );
}

/* Whether a model is within its published retirement commitment. The date
   is the earliest Anthropic will retire it, not a scheduled removal, so
   this is a warning and never a block. */
export function retirementWarning(model, now = new Date()) {
  const when = new Date(model.retirementNotBefore + 'T00:00:00Z');
  const days = Math.ceil((when - now) / 86400000);
  if (days > 90) return null;
  return days > 0
    ? `${model.label} may be retired from ${model.retirementNotBefore} (${days} days). If it stops resolving, pick another model.`
    : `${model.label} passed its earliest retirement date (${model.retirementNotBefore}). It may no longer resolve.`;
}
