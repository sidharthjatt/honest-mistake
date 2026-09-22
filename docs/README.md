# The benchmark site

This folder is the static site published at <https://sidharthjatt.github.io/honest-mistake/>.

```bash
python3 -m http.server -d docs 8000
```

Run that from the repository root and open the address it prints. There is no build step.

`index.html` is the landing page; it and the other three pages, `runs.html`, `replay.html` and `scan.html`, read the exported JSON under `data/` at load.

It is named `docs/` rather than `site/` because GitHub Pages deploying from a
branch will serve the repository root or `docs/`, and nothing else.

`.nojekyll` keeps Jekyll away from what is served. Nothing here starts with an
underscore, so nothing was being dropped; the file removes the possibility
rather than fixing a live problem.
