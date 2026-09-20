# Scan page defect register

Written 2026-09-20. This is a defect register and nothing else. It freezes nothing and specifies nothing.

The scan pages under `docs/` were built after Layer 3 closed, and no preregistration covers them. Each `PREREGISTRATION*.md` file was written, or frozen, before the work it specifies existed, and its defect register belongs to that work. These defects fall outside all of them, so they are recorded here, not inside a frozen specification they were never under.

Numbering continues from D18 in `PREREGISTRATION_PHASE4.md`.

**D19. 2026-09-19.** A run that ends on an error is saved without saying which error.
- **What the code does:** when a request fails, the loop keeps the error's kind and message in `failure`, along with a `detail` that holds the HTTP status, the error type and the API's own message (`docs/agent/loop.js:204-208`), and returns it with the result. `buildRecord` in `docs/agent/runfile.js` never reads `result.failure`, and its event switch (line 49) has no case for the `error` event. The record says only `termination: "failed"`, and `docs/scan-page.js:1021` adds the loop's sentence for that ending, "The run stopped on an error."
- **Where it shows:** in the downloaded file and in the copy the tab keeps. The error appears only in the live banner (`docs/scan-page.js:617-620`). After a reload the page restores the run from the kept copy, so the reason is gone from the page too, and the only reason Screen 3 gives is "The run stopped on an error."
- **What it does not affect:** every other ending is saved with its reason: `termination`, `last_stop_reason` and the loop's sentence for it.
- **What is not known:** whether any visitor's run has failed this way. Nothing reports runs back.

This is recorded because a failed run's file is the only lasting record of it, and it can't say what went wrong. Until it is fixed, a screenshot of the banner is the only record of the reason.

**D20. 2026-09-19.** Every HTTP 429 is shown as a passing rate limit, including one that lasts until the next month.
- **What the code does:** `classify` in `docs/agent/provider.js` turns any 429 (line 119) into "Rate limited by the API. Wait a moment and run again." (line 121). It looks at the status alone. The API's message goes only into the error's detail, which the banner doesn't show and the record doesn't keep (D19).
- **What it is grounded in:** Anthropic's rate-limits page (platform.claude.com/docs/en/api/rate-limits), read on 2026-09-20. It gives three causes for a 429: exceeding a rate limit, which comes with a `retry-after` header; acceleration limits, when an organisation's usage rises sharply; and reaching the organisation's monthly spend cap. The spend-cap 429 has `error.details.error_code` set to `enforced_spend_limit_reached` and no `retry-after`, and the page says usage pauses until 00:00 UTC on the first of the next month unless a higher limit is requested sooner, that moving to a higher tier restores access, and that retrying fails until access resumes. For that cause, "Wait a moment and run again" is false.
- **What is not known:** whether the browser lets the page read `retry-after`, which depends on the API's CORS headers and wasn't checked; how often a visitor's run would meet any 429, since the page sends one request at a time; and whether the docs page still says the same.
- **What it does not affect:** how the run ends. Every error ends it as `failed`; the classification changes only the sentence shown.

This is recorded because the advice, followed, doesn't work in one of the cases it covers, and the visitor isn't shown the API's own message that would say so.

**D21. 2026-09-19.** Any 404, and any 400 whose error message contains "model", is shown as a retired or mistyped model.
- **What the code does:** `docs/agent/provider.js:103` tests `status === 404 || (status === 400 && /model/i.test(msg))`, where `msg` is the API's `error.message` (line 99). The match is on the letters, case-insensitive, anywhere in the message. The visitor is told "The model '<id>' was not accepted: <message>. It may have been retired. Choose another model and run again."
- **How it was first noted, and why that was wrong:** as "any 400 whose body contains the word model". The test reads the message field, not the whole body; matches the letters, not the word; and takes every 404 whatever it says.
- **What the visitor still gets:** the API's own message, quoted after the colon, so the real cause is on screen, after a sentence pointing at the wrong one.
- **What is not known:** which real 400 messages contain "model". None has been seen through this page. A self-set spend limit's error is documented as HTTP 400 with type `invalid_request_error`; an organisation limit's message opens "You have reached your specified API usage limits", and a workspace limit's opens "You have reached your specified workspace API usage limits". Neither opening contains "model", so neither would be misfiled by this test. The rest of either message, which states when access resumes, has not been seen.
- **What is untested:** `classify` itself. The loop page's invalid-model case (`verify/_verify_loop.html:70`) throws a ready-made error with the retired-model sentence, so it tests how the loop shows an error, not how a response is classified.

This is recorded because it tells a visitor to change a setting that may have nothing to do with the failure.

**D22. 2026-09-20.** `docs/README.md` says the site has three pages, and it now has four.
- **What the file says:** `docs/README.md:5` reads "`index.html` is the landing page; it and the other two pages read the exported JSON under `data/` at load." That was written on 2026-09-16 (1cb18cd), when `docs/` held `index.html`, `runs.html` and `replay.html`.
- **What is there now:** `docs/scan.html` was added on 2026-09-19 (f8d3df0), so `index.html` has three other pages, not two. The scan page also reads the exported JSON under `data/` at load: `docs/scan-page.js:129-132` fetches the system prompt, the tool schemas, the manifest and the run index, and `:799-803` fetches the scoring, the run index, both SHAP exports and the dictionary. So the count is wrong, and the page it leaves out is one the sentence would otherwise have covered.
- **Where it shows:** in the repository, and in GitHub's rendering of the `docs/` folder. It is not part of the published site, which serves `index.html` rather than this file.
- **What it does not affect:** nothing the pages themselves say, and nothing the scan page does. No code reads this file.
- **What is not known:** whether anyone has read it since the scan page was added. Nothing reports readers.

This is recorded rather than fixed because the sentence is a claim, and changing a claim is a decision of its own, not part of a design pass.
