export const BUILD = '91493d637f81';
/* The scan page's loader. It has no static imports on purpose.
 *
 * GitHub Pages lets a browser keep each file for up to ten minutes, and it
 * keeps them one by one. For a while after a deploy, a visitor can get some
 * modules from the new build and some from the old one. Mixed like that,
 * the page can run and say things that are false, such as that an answer
 * has no findings block when one is plainly there. A mixed set has to be
 * refused, not run.
 *
 * The check can't be a static import. If an old module lacks a name that a
 * new one imports, the whole module graph fails to link before any code in
 * it runs, and nothing could show a refusal. So every module is loaded here
 * with import(), each one separately. A module's stamp is read from its own
 * namespace, which gives undefined for a module with no stamp rather than
 * an error. The stamp is read by the JavaScript engine, not parsed out of
 * the file's text, so a correctly stamped file can't be misread.
 *
 * Every stamp is the same value, written into each file by
 * scripts/stamp_modules.py from the contents of the whole set. A change to
 * any module changes all of them. MODULES is written by the same script.
 *
 * What a refusal says depends on what was found, in this order:
 * - A module that loaded carries a different stamp, or none: the files
 *   come from different builds. Different builds aren't always
 *   incompatible: a module from before stamps existed has none, and may
 *   run perfectly well. So the refusal says only that the page can't
 *   confirm its files are from one version, never that they don't work
 *   together. The page tries to fix it itself once (below), and says so
 *   only if it can't.
 * - A module failed to load and can't be fetched at all: a network failure.
 * - A module failed to load for any other reason: a 404 or a server error
 *   on the file, a file that is cut short or corrupt, a module that throws,
 *   a blip during load that has cleared by the time the page checks, or a
 *   stale copy of a module that imports a name the new build no longer
 *   exports. That last one is a version mismatch, but it lands here, not in
 *   the branch above: the stale module fails to link, so its stamp is never
 *   read, and the modules that did load all agree. The browser's error
 *   doesn't tell these causes apart reliably, so the page says only that a
 *   file failed to load, that it can't tell why, and that coming back later
 *   may or may not help. scripts/check_export_diff.py finds the deploy that
 *   would make the stale-module case possible. The opt-in pre-push hook in
 *   .githooks/ runs it and refuses such a push to main, on a clone where the
 *   hook is turned on and the push doesn't skip it.
 *
 * Nothing here runs after startPage(). The only reload is in selfFix(), which
 * is reached only from load(), before the page has started, so it can't
 * interrupt a run. A run kept from before is in sessionStorage, which a
 * reload leaves alone, and the page restores it once it does start.
 */

const MODULES = [
  './scan-page.js',
  './agent/ceilings.js',
  './agent/loop.js',
  './agent/models.js',
  './agent/parse.js',
  './agent/pipeline.js',
  './agent/provider.js',
  './agent/runfile.js',
  './agent/scoring.js',
  './agent/screen3.js',
  './agent/tools.js',
  './agent/verdict.js',
  './agent/viz.js',
  './agent/words.js',
];

const FIX_TRIED = 'honest-mistake:stale-fix-tried';

/* Each is [the bold first sentence, the rest]. */
const SAY = {
  mixed: ['This page didn’t load properly.',
    'It can’t confirm all of its files are from the same version, so it won’t run. ' +
    'Copies of its files can be kept for up to ten minutes, so this can clear on its ' +
    'own — come back in a few minutes and it should load.'],
  unreachable: ['This page couldn’t load one of its files.',
    'Check your connection and reload.'],
  cannotStart: ['This page couldn’t start.',
    'One of its files failed to load, and the page can’t tell why. Some causes clear up ' +
    'on their own and some need the site to be fixed, so coming back later may or may ' +
    'not help.'],
};

/* A module's URL as the browser resolves it for import(), import maps
   included, so that what is fetched is what failed to load. */
const resolve = path => (import.meta.resolve
  ? import.meta.resolve(path)
  : new URL(path, import.meta.url).href);

function refuse(kind) {
  const [lead, rest] = SAY[kind];
  const box = document.createElement('div');
  box.className = 'banner bad';
  box.setAttribute('role', 'alert');
  box.dataset.refusal = kind;
  const b = document.createElement('b');
  b.textContent = `${lead} `;
  box.append(b, rest);
  (document.getElementById('screen1') || document.body).prepend(box);
  const go = document.getElementById('go');
  if (go) go.disabled = true;
}

/* true: already tried in this tab. false: not tried. null: storage is
   unavailable, which means the attempt can't be recorded, so it is not
   made at all. */
function fixTried() {
  try { return sessionStorage.getItem(FIX_TRIED) !== null; } catch { return null; }
}
function forgetFix() {
  try { sessionStorage.removeItem(FIX_TRIED); } catch { /* nothing to forget */ }
}

/* One attempt per tab, recorded before the reload so the reload can't
   loop. Every module, and this loader, is fetched again past the cache;
   that replaces the cached copies the next load reads. Tested with a
   Pages-like server: a plain reload keeps a stale module (no request is
   made for it), and this refetch followed by one reload loads the new
   one. Once, on a local server, the refetch did not cure a stale
   models.js, and why was never established. So the attempt is not
   trusted: the reloaded page checks every stamp again, and if they
   still disagree it refuses instead of trying a second time. */
async function selfFix() {
  if (fixTried() !== false) return false;
  try { sessionStorage.setItem(FIX_TRIED, BUILD); } catch { return false; }
  await Promise.all([...MODULES, './scan.js'].map(path =>
    fetch(resolve(path), { cache: 'reload' }).catch(() => null)));
  location.reload();
  return true;
}

async function reachable(path) {
  try { await fetch(resolve(path)); return true; } catch { return false; }
}

async function load() {
  const loaded = await Promise.allSettled(MODULES.map(path => import(path)));
  const mixed = loaded.some(r => r.status === 'fulfilled' && r.value.BUILD !== BUILD);
  if (mixed) {
    if (await selfFix()) return;
    forgetFix();
    refuse('mixed');
    return;
  }
  forgetFix();
  const failed = MODULES.filter((_, i) => loaded[i].status === 'rejected');
  if (failed.length) {
    const reached = await Promise.all(failed.map(reachable));
    refuse(reached.includes(false) ? 'unreachable' : 'cannotStart');
    return;
  }
  loaded[MODULES.indexOf('./scan-page.js')].value.startPage();
}

load();
