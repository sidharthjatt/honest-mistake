# Design pass

Written 2026-09-20. This file scopes the design pass. It is not a defect register, and it records no finding.

## In scope

Exactly seven files:

- `docs/index.html`
- `docs/runs.html`
- `docs/replay.html`
- `docs/scan.html`
- `docs/style.css`
- `README.md`
- `docs/README.md`

`docs/style.css` is in because checks 1 and 5 are layout checks, and they can't be met without it. The alternatives were inline styles or restructured HTML, and both are worse.

Every file not listed here is out of scope.

## Out of scope, and why

- `PREREGISTRATION*.md`, `REPORT.md`, `SCAN_DEFECTS.md`, `outputs/agent_cache/LAYER2_EVAL.md` and `outputs/agent_cache/RETRIEVAL_EVAL.md`. These are records, not presentation. Restyling them would mean editing frozen text, and this project changes frozen text only by dated amendment.
- On every in-scope page, any sentence that makes a claim: numbers, verdicts, ceiling wording, refusal banners. Those were checked against the code, and they stay byte-identical through this pass. If one of them needs to change, that is a defect, not a design change, and it goes in `SCAN_DEFECTS.md`. The claim manifest below lists which sentences these are.

### One narrow exception: text written by JavaScript

Some of the text on the pages is written by `docs/scan-page.js`, `docs/agent/*.js`, `docs/common.js` and `docs/scan.js`. Those files stay out of scope, with one exception:

- **If the text is a claim sentence**, it doesn't change. The only allowed fixes are splitting it into separate `<p>`s with the sentences unchanged, or changing its width in `docs/style.css`.
- **If it is not a claim sentence**, its string literal may be edited in `docs/scan-page.js`, `docs/agent/*.js`, `docs/common.js` or `docs/scan.js`. Visible-text string literals only, non-claims only, and never logic, conditions or variables.

The exception never covers a string that is sent to the API or compared by code. `docs/agent/tools.js` is frozen whole.

## Done

The pass is done when all seven checks below pass, run in this order:

1. No rendered paragraph is longer than 4 lines at 1280px, on any in-scope page.
2. Each page's first screen, before any scrolling, shows what the page does and at least one control.
3. A banned-phrase check passes over the six text files: em-dash-heavy phrasing, "delve", "leverage", "robust", "seamless", "dive into", "it's worth noting", "in today's world".
4. Both READMEs say what the thing is and how to run it within their first three lines.
5. No horizontal scroll and no overlap at 390px width, on any in-scope page.
6. In `docs/*.html`, `docs/*.js` and `docs/agent/*.js`, every sentence in the claim manifest is byte-identical to its text at `62f8d3e`.
7. Every claim sentence this pass changed in `README.md` or `docs/README.md` has been re-verified, with an entry recorded below.

**Check 6 applies to `docs/*.html`, `docs/*.js` and `docs/agent/*.js`, and to nothing else.** Rewriting those files is not the goal of this pass, so freezing their claim sentences costs nothing. The two READMEs are not under check 6.

**Check 7 is re-verification, not comparison.** Any claim sentence in either README that this pass changes is re-verified against the code or data it describes before the pass closes, and the verification is recorded below as a numbered entry: the sentence as it now reads, the file and line that establishes it, and what was checked. A claim sentence left byte-identical needs no entry. A claim that cannot be re-verified is not rewritten. It is left exactly as it is, or, if it turns out to be wrong, it goes in `SCAN_DEFECTS.md` as a defect and stays unchanged in this pass.

**Em-dashes (check 3)** are measured by density, not by total. The rule is at most 1 per paragraph, and 0 in each README's first three lines. Claim sentences are exempt, and the check skips them.

**Paragraph length (check 3)** applies to the two READMEs: no paragraph in `README.md` or `docs/README.md` exceeds 360 characters. Table rows are excluded. `check_design_text.py` enforces it.

**A punctuation-only change to a claim sentence is allowed (check 7).** Replacing an em-dash with a comma, colon or full stop, with no word added, removed or reordered, cannot change what the sentence asserts, so it needs no re-verification. All such changes are recorded together as a single check 7 entry listing the file and line of each. Any change that touches a word is not punctuation-only and follows the normal check 7 rule.

**"What it is" (check 4)** is the first non-heading line, and it must not be empty. "How to run it", within the first three non-blank lines, is a shell line, a fenced block that opens there and holds a command, or an instruction to open or serve something with an address or a command on the same line. A code span alone does not count. This was tightened on 2026-09-23, after the first baseline: a code span let `docs/README.md` pass on `` `index.html` ``, which runs nothing.

## The check

Each check passes or fails; none is a judgement. Two scripts under `verify/` run them, both added in ff8e639:

- `verify/check_design_text.py` runs checks 3 and 4, and check 6 against the manifest. It is plain Python with nothing to install.
- `verify/_verify_design.html` runs checks 1, 2 and 5 in the browser. It loads each page in a same-origin frame at 1280×800 and at 390×844.

Check 7 has no script. It is done by reading, and its record is the numbered list at the end of this file.

**What check 6 compares.** For HTML and Markdown, each sentence's source with runs of whitespace collapsed and tags kept. Collapsing whitespace is a deliberate loosening, so that re-wrapping a paragraph and splitting it into separate `<p>`s stay allowed. For JavaScript, each string literal is compared byte for byte, with no loosening. In both cases a sentence may move within its file, because line numbers will shift.

What the checks can't show:

- **Check 2** proves the paragraph is on the first screen. It can't judge whether the paragraph says what the page does.
- **Check 6** proves only that the manifest's sentences did not change. It says nothing about any sentence this pass rewrote.
- **Check 7 is the only gate on a rewritten README claim, and it is done by reading, not by a script.** That is deliberate: no script can tell whether rewritten prose is still true.
- **On `scan.html`**, checks 1 and 5 cover what renders at load, plus the 17 `?dev=` scenarios that exist at `62f8d3e`, and nothing else. They are `1` (the default six-turn script), `endless`, `calls`, `costly`, `slow`, `costexact`, `costnear`, `blockstop`, `blockturns`, `blockcost`, `noblock`, `named`, `credited`, `oos`, `late`, `unclosed` and `empty`.

## Claim manifest: `docs/*.html`, `docs/*.js` and `docs/agent/*.js`

This is check 6's scope. Every sentence below stays byte-identical to `62f8d3e`, compared as set out above. The unit is the sentence for page text and the string literal for JavaScript. Lines are at `62f8d3e`, and a sentence may move within its file. Each entry prints the first 110 characters of its sentence, for reading; check 6 compares the whole sentence, not the excerpt.

Page text is listed sentence by sentence with no filtering, because the classifier used for the READMEs missed sentences whose numbers sit in a `<span>`, and freezing costs nothing in these files, so nothing here depends on that classifier.


### docs/index.html (page text)

1. `docs/index.html:7` meta description: "An agent audits a credit default model for target leakage. Twelve real runs, replayable turn by turn, with the scorer’s own output unchanged."
2. `docs/index.html:28-32` A credit default model was built clean: 180 features, a temporal split, and every column that could only be kn
3. `docs/index.html:28-32` Then a single leaking column was planted back into some of the data, and an agent with eight read-only tools w
4. `docs/index.html:34-39` The agent never sees the data.
5. `docs/index.html:34-39` It sees a fixed set of artefacts through eight tools — a data dictionary it can search, a SHAP ranking, per-fe
6. `docs/index.html:34-39` Twelve real runs were recorded against live API calls.
7. `docs/index.html:34-39` Every one of them is replayable here, turn by turn, including the tool arguments and the full results the agen
8. `docs/index.html:47-52` Across the scorable runs the agent raised flags.
9. `docs/index.html:47-52` The answer key credits of them.
10. `docs/index.html:47-52` It is tempting to call the rest errors, and that would be wrong: the key recognises exactly one kind of proble
11. `docs/index.html:47-52` A flag it does not credit is a flag outside that list, which is not the same as a flag that is mistaken.
12. `docs/index.html:58-62` None of these claims leakage in the sense the key scores.
13. `docs/index.html:58-62` They argue distribution shift, missingness that tracks loan vintage, drift across vintages, and whether the 20
14. `docs/index.html:58-62` Those arguments are ungraded: the scorer cannot settle them.
15. `docs/index.html:58-62` Each card links to the turn in the replay where the agent produced it, so the evidence can be read rather than
16. `docs/index.html:65` The scorer's output, unchanged
17. `docs/index.html:67-70` Nothing above re-derives a verdict.
18. `docs/index.html:67-70` Every figure is read from the scorer's own output at page load, and that output is reproduced here in full — p

### docs/runs.html (page text)

19. `docs/runs.html:28-29` Every recorded run, with the configuration that distinguishes it and the scorer's decision on it.
20. `docs/runs.html:31-36` These are the real runs against live API calls.
21. `docs/runs.html:31-36` They were not all configured alike: the tool surface changed between versions, the per-vintage coverage scopes
22. `docs/runs.html:31-36` A run the scorer refused is one that stopped before the agent said it had finished; a partial answer is not sc
23. `docs/runs.html:56-57` The wording below is the export's own, unedited.
24. `docs/runs.html:56-57` The short name in the table points at one of these.

### docs/scan.html (page text)

25. `docs/scan.html:233-235` Give the agent something to audit and an API key, and it works in your browser while you watch: it forms a hyp
26. `docs/scan.html:239` Three steps.
27. `docs/scan.html:239` Nothing is sent until you press the button.
28. `docs/scan.html:247-249` Two candidates, described identically on purpose: you are not told which is which.
29. `docs/scan.html:247-249` One of them may be reading the answer off the back of the page.
30. `docs/scan.html:258-259` Which Claude model runs the agent.
31. `docs/scan.html:258-259` This is the auditor, not the thing being audited.
32. `docs/scan.html:268` Stop the run once its cost reaches
33. `docs/scan.html:290-292` Your key is never stored.
34. `docs/scan.html:290-292` Not in storage, not in a cookie, not in a URL, and not in the run this page keeps.
35. `docs/scan.html:290-292` It is held in memory and goes when you close the tab.
36. `docs/scan.html:293-295` The finished run is kept in this tab, so reloading does not lose it.
37. `docs/scan.html:293-295` It holds the transcript, the tool results and the token counts, and never the key.
38. `docs/scan.html:293-295` It goes when the tab closes.
39. `docs/scan.html:296-297` Sent to one place: api.anthropic.com, straight from your browser.
40. `docs/scan.html:296-297` No backend here, no key of mine.
41. `docs/scan.html:298-301` Check it yourself: the only file that builds or sends a request is agent/provider.js, and this page is scan.ht

### docs/index.html (inline script)

42. `docs/index.html:111-114` el('p', {}, 'The leaking column ', el('code', { text: plantedColumns.join(', ') }), ' was planted into ', Stri
43. `docs/index.html:115-116` el('p', {}, 'All ', String(present.length), ' were scored. They are not repeats of ', 'one setup: they differ 
44. `docs/index.html:119` el('div', { class: 'figure', text: 'none of ' + keySize }),
45. `docs/index.html:120-122` el('p', {}, 'In the other ', String(absent.length), ' runs the column was absent, and ', 'so was every one of 
46. `docs/index.html:123-125` el('p', {}, 'No correct flag was reachable in those runs. ', String(absentScored.length), ' were scored and ',
47. `docs/index.html:129-131` 'Whether the column was present is read from each run’s manifest where it records one, and for the ' + runs.fi
48. `docs/index.html:149-151` f.verdict === 'true_positive' ? pill('credited', 'credited') : pill('uncredited', 'not credited'), f.hard_nega
49. `docs/index.html:158-162` dl.append(el('dt', { text: 'Scored as' }), el('dd', {}, 'Mapped to its parent column ', el('code', { text: f.s
50. `docs/index.html:191` el('p', { class: 'note' }, el('b', { text: 'Refused, not scored. ' }), s.reason));
51. `docs/index.html:193` el('summary', {}, s.label + ' — ' + (s.scored ? 'scored' : 'refused')), body));

### docs/runs.html (inline script)

52. `docs/runs.html:85` const shortName = w => w.startsWith('derived') ? 'derived' : 'manifest field';
53. `docs/runs.html:91` el('dt', {}, shortName(w) + ' — ' + covered.length + ' of ' + runs.length + ' runs'),
54. `docs/runs.html:107` canary.present ? pill('present', 'present') : pill('absent', 'absent'),
55. `docs/runs.html:110-121` shortName(canary.established_by || ''), counts ? el('span', { class: 'note', style: 'display:block' }, counts.
56. `docs/runs.html:123-127` run.scorer_accepted ? pill('scored', 'scored') : pill('refused', 'refused'), run.scorer_refusal_reason ? el('s
57. `docs/runs.html:128-131` el('td', { class: 'num' }, String(run.turns), el('span', { class: 'note', style: 'display:block' }, 'max ' + r
58. `docs/runs.html:137-139` document.getElementById('lede').textContent = runs.length + ' recorded runs. ' + scored + ' were scored and ' 

### docs/replay.html (inline script)

59. `docs/replay.html:54-56` el('h1', { text: label ? 'No such run' : 'No run chosen' }), el('p', {}, label ? el('span', {}, 'There is no r
60. `docs/replay.html:90-91` facts.model, ' · ', String(facts.turns), ' turns · ', String(facts.tool_calls), ' tool calls · started ', asRe
61. `docs/replay.html:93-95` canary.present ? pill('present', 'canary present') : pill('absent', 'canary absent'), ' ', facts.scorer_accept
62. `docs/replay.html:97-103` el('span', { class: 'note' }, 'tool layer v' + facts.tool_layer_version + ' · populated ' + facts.dictionary_p
63. `docs/replay.html:105` ? el('p', { class: 'note' }, 'The planted column was ', el('code', { text: canary.column }), '.')
64. `docs/replay.html:109` el('b', { text: 'Not scored. ' }), facts.scorer_refusal_reason) : null));
65. `docs/replay.html:116-118` el('b', {}, per.tool_calls_without_results + ' tool calls in this run have no result. '), unrunCalls.why, ' Th
66. `docs/replay.html:122-123` el('b', {}, 'This run has no final answer turn. '), noFinalTurn.why, ' Every tool call it made did run and ret
67. `docs/replay.html:127-128` el('b', {}, 'The system prompt is not reproduced. '), noSystemPrompt.why, ' The manifest records it as ', Stri
68. `docs/replay.html:132` el('b', {}, 'No per-turn token usage. '), run.per_turn_usage_note || noPerTurn.why));
69. `docs/replay.html:141-144` out.append(el('p', { class: 'note' }, 'Parsed from the final answer below. The verdict on each is the scorer’s
70. `docs/replay.html:152-154` el('dd', {}, 'Mapped to its parent column ', el('code', { text: f.scored_as_parent.parent }), ' (', f.scored_a
71. `docs/replay.html:162-164` f.verdict === 'true_positive' ? pill('credited', 'credited') : pill('uncredited', 'not credited'), f.hard_nega
72. `docs/replay.html:169` el('p', { class: 'note' }, 'None were scored. ', scored.reason));
73. `docs/replay.html:174-178` out.append(el('p', { class: 'note' }, 'Messages are in the order they were recorded. Thinking blocks are summa
74. `docs/replay.html:191` el('summary', { text: b.summary_empty ? 'Thinking — no summary in the record' : 'Thinking' }),
75. `docs/replay.html:193` ? el('p', { class: 'note', text: 'The run recorded an empty summary for this block. Nothing was dropped here b
76. `docs/replay.html:207-208` b.result_is_error ? pill('uncredited', 'returned an error') : null, b.executed === false ? pill('hardneg', 'ne
77. `docs/replay.html:215` : 'No result is recorded for this call.';
78. `docs/replay.html:221` el('summary', { text: (b.result_is_error ? 'Error result' : 'Result') + ' — ' + bytes(text.length) + ' charact
79. `docs/replay.html:229-230` 'The result for ', tool ? el('b', { text: tool }) : 'a call', ' was returned in this turn. It is shown on the 
80. `docs/replay.html:248` el('p', { class: 'note' }, 'Recorded request by request for this run only.'),
81. `docs/replay.html:255` el('summary', { text: 'The console record this run wrote, unedited' }),

### docs/scan-page.js

82. `docs/scan-page.js:90` ${path} could not be loaded (${res.status}).
83. `docs/scan-page.js:159-163` One credit-default model, scored the same way on the same held-out ${TEST_YEAR}  loans, with and without a sin
84. `docs/scan-page.js:173` Candidate ${letter}, a credit-default model under audit
85. `docs/scan-page.js:183-184` held out not stated
86. `docs/scan-page.js:216` — about ${money(costOf(m, rep.usage))} a run
87. `docs/scan-page.js:231-237` ${m.label}: $${m.price.input}/MTok in, $${m.price.output}/MTok out,  $${m.price.cacheRead}/MTok on cache hits,
88. `docs/scan-page.js:239-240` ${m.label}: $${m.price.input}/MTok in, $${m.price.output}/MTok out,  as Anthropic's pricing page listed them o
89. `docs/scan-page.js:305` Restored from this tab \u2014 the turn-by-turn view is not re-shown.
90. `docs/scan-page.js:307-309` This run was kept when the page reloaded. The turn-by-turn view is not  restored, but the record is: what came
91. `docs/scan-page.js:334` set a spend ceiling between $${MIN_CEILING.toFixed(2)} and $${MAX_CEILING.toFixed(2)}
92. `docs/scan-page.js:345` check your API key — it should start with "${KEY_PREFIX}" and be much longer
93. `docs/scan-page.js:372` Enter a ceiling between $${MIN_CEILING.toFixed(2)} and $${MAX_CEILING.toFixed(2)}.
94. `docs/scan-page.js:377-378` A recorded run of this agent costs about ${money(typical)} at these rates,  so this is roughly ${(v / typical)
95. `docs/scan-page.js:384-388` Checked after every turn, before the next request is sent. A turn already  under way is always finished, so th
96. `docs/scan-page.js:412` Nothing was sent. First, ${missing.map(m => m.say).join(', and ')}.
97. `docs/scan-page.js:419-420` Ready. This will send requests to Anthropic with your key,  one per turn, for at most ${count(MAX_TURNS, 'turn
98. `docs/scan-page.js:440-441` Stopping. No further request will be sent. A request already in flight  is paid for, so it is allowed to finis
99. `docs/scan-page.js:447` Cancelled mid-request. That turn may still be billed.
100. `docs/scan-page.js:456` Ends the run at the end of the current turn.
101. `docs/scan-page.js:544` Auditing Candidate ${chosenCard}
102. `docs/scan-page.js:546-549` Auditor: ${e.model.label} · ceilings ${count(e.config.maxTurns, 'turn')},  ${count(e.config.maxToolCalls, 'too
103. `docs/scan-page.js:611-614` banner bad Cancelled.  The request for turn ${e.turn} was abandoned in flight. It may still be  billed by Anth
104. `docs/scan-page.js:618-619` banner bad The run stopped.
105. `docs/scan-page.js:630-634` banner bad This run’s ending could not be shown.  The page refused rather than guess: ${err.message}  Nothing 
106. `docs/scan-page.js:645-647` tool call ${spentApart(e.spend, e.config.maxCost, money)} spent against a  ${money(e.config.maxCost)} ceiling
107. `docs/scan-page.js:654` Run finished.
108. `docs/scan-page.js:657-658` ${e.reason} ${bits.join(' · ')}.  Press “See how it scored” below to find out which candidate this was.
109. `docs/scan-page.js:668-669` banner bad verdictless No verdict.
110. `docs/scan-page.js:675-676` Only the final answer is scored, as it was for the recorded runs, so  anything written before it, above, does 
111. `docs/scan-page.js:678` The model never replied, so this run produced no result.
112. `docs/scan-page.js:681-684` The run did not finish, so it produced no result. Only a run the agent  ends itself is scored, as it was for t
113. `docs/scan-page.js:691` With no reply from the model there is nothing for the scorer to grade.
114. `docs/scan-page.js:693-694` The scorer that graded the ${word(runIndex.runs.length)} recorded runs  does not score a run like this one:
115. `docs/scan-page.js:696-702` with no final answer there was nothing to parse,  the final answer could not be parsed,  which it calls a pars
116. `docs/scan-page.js:713` Audited Candidate ${card}
117. `docs/scan-page.js:715-717` Candidate ${card} — no verdict Candidate ${card} — no turn completed Candidate ${card} — audit cut off
118. `docs/scan-page.js:734-739` The agent never got a reply to its first request, so it never looked  at anything and this run produced no res
119. `docs/scan-page.js:745` The cancelled request is not in that figure, and may still be billed.
120. `docs/scan-page.js:754-755` The run was stopped at its ceiling of ${count(c.maxTurns, 'turn')},  before it could send another request.
121. `docs/scan-page.js:760-762` The run stopped at ${count(e.toolCalls, 'tool call')}: the model asked  for a batch that would have taken it p
122. `docs/scan-page.js:768` You stopped the run.
123. `docs/scan-page.js:770` You cancelled the run while a request was in flight.
124. `docs/scan-page.js:772-773` One turn hit the per-request output ceiling of  ${num(model.maxTokens)} tokens and was cut off mid-sentence.
125. `docs/scan-page.js:775` The model declined to continue.
126. `docs/scan-page.js:777` The model paused the turn and the run was not resumed.
127. `docs/scan-page.js:779` The model stopped on a stop sequence.
128. `docs/scan-page.js:781` The model stopped for a reason this page does not recognise.
129. `docs/scan-page.js:783` The run stopped on an error, which is shown above.
130. `docs/scan-page.js:846-847` ${path} is a ${value.constructor.name}, which  Object.freeze cannot seal. Use readOnlySet, or a plain object.
131. `docs/scan-page.js:865-866` scoring.canary holds ${columns.length} columns  (${columns.join(', ') || 'none'}). Screen 3 is written for exa
132. `docs/scan-page.js:882-884` Expected the honest model to read no key column and the canary  model to read only ${canaryColumn}; they read 
133. `docs/scan-page.js:909-911` banner bad This run was not scored.  The page checks its own data before it scores anything, and it refused: $
134. `docs/scan-page.js:924-925` Kept in this tab, so a reload will not lose it. It goes when the tab closes. This tab will not keep the run \u
135. `docs/scan-page.js:938` A run is already going. Stop it first, below.
136. `docs/scan-page.js:952` Nothing was sent. First, ${missing.map(m => m.say).join(', and ')}.
137. `docs/scan-page.js:1027-1028` banner bad Could not start.
138. `docs/scan-page.js:1043` status error This page could not load its data: ${err.message}

### docs/scan.js

139. `docs/scan.js:73-82` This page didn’t load properly. It can’t confirm all of its files are from the same version, so it won’t run. 

### docs/common.js

140. `docs/common.js:8` could not be loaded ( ).
141. `docs/common.js:97` from commit
142. `docs/common.js:100` Uncommitted changes in the source paths at export:
143. `docs/common.js:105` Export script SHA-256:
144. `docs/common.js:113` bytes removed.
145. `docs/common.js:119` Scoring cannot be recomputed from a fresh clone
146. `docs/common.js:138` Provenance — where every figure on this page comes from
147. `docs/common.js:146` status error Provenance unavailable:

### docs/agent/screen3.js

148. `docs/agent/screen3.js:125-126` You ${verb} Candidate ${record.card}. It was  the honest model. the one carrying the canary.
149. `docs/agent/screen3.js:129-132` Nothing was planted in it. All   columns the answer key lists as leaking  were taken out before this model was
150. `docs/agent/screen3.js:134` it scores on held-out ${TEST_YEAR} loans is what the model is actually worth.
151. `docs/agent/screen3.js:142` One column was put back:
152. `docs/agent/screen3.js:144` The dictionary describes it as “${tp.description}”
153. `docs/agent/screen3.js:146-150` The answer key lists it at tier ${tp.tier} — ${tp.tier_label}.  The answer key lists it as leaking, without a 
154. `docs/agent/screen3.js:163-167` The model has   inputs, and not one of them  is a column the answer key scores — all   were taken out before i
155. `docs/agent/screen3.js:169-171` The model has   inputs, and one of them is a  column the key scores:  . That was the leak and the only one in 
156. `docs/agent/screen3.js:173-174` are in the dictionary but not in it, so the cards below mark which of your  flags the model was actually readi
157. `docs/agent/screen3.js:192-195` — run3 flagged ${word(run3.false_positives.length)}  ${run3.false_positives.length === 1 ? 'column that is' : 
158. `docs/agent/screen3.js:198-201` The key scores one kind of problem: columns carrying information that could  only be known after the loan’s ou
159. `docs/agent/screen3.js:205-206` The agent reported no findings. Nothing to score, and on this candidate  that may well be the right answer.
160. `docs/agent/screen3.js:220-223` Credited — and a good catch, though not about this model. Not credited — and this is the interesting one. Not 
161. `docs/agent/screen3.js:257-259` at tier A, the most explicit kind: it is the loan’s own outcome, and  “Charged Off” is the thing being predict
162. `docs/agent/screen3.js:262-264` without a tier. Its dictionary description carries none of the  lifecycle wording the tiers are matched on, so
163. `docs/agent/screen3.js:267-270` at tier ${tp.tier} — ${tp.tier_label}.  The dictionary describes it as “${tp.description}”  Naming it means re
164. `docs/agent/screen3.js:281-284` is one of the   columns the key scores, and it is one  of this model’s inputs.  Tier ${tp.tier} — ${tp.tier_la
165. `docs/agent/screen3.js:291` is in the answer key
166. `docs/agent/screen3.js:295-297` It is not one of the model’s   inputs. It was removed before  the model was built, so reading it back does not
167. `docs/agent/screen3.js:299-303` The scorer credits it anyway, because it matches names against the key and  does not ask what the model read. 
168. `docs/agent/screen3.js:308-311` is one of   columns put in the key precisely because  they look like leakage without being it. Flagging one me
169. `docs/agent/screen3.js:313-314` It was scored as  , the column it derives from.
170. `docs/agent/screen3.js:321-325` is one of the model’s   inputs and is not a column the  key scores. It may still be a fair objection, but the 
171. `docs/agent/screen3.js:336-337` is out of scope. The key sets it  aside, and it counts neither for you nor against you.
172. `docs/agent/screen3.js:339-340` The key does record why, but in wording written for the scorer rather  than for you; it is in
173. `docs/agent/screen3.js:358-364` s3-canary-line na No canary here.  Nothing was planted in this candidate, so there was nothing to find, and no
174. `docs/agent/screen3.js:368-370` s3-canary-line na Whether a canary was planted in this candidate was not recorded, so this  run cannot be read
175. `docs/agent/screen3.js:377-380` s3-canary-line found You found it.   was planted in this model and you flagged it. That is the test, and you  
176. `docs/agent/screen3.js:387-391` s3-canary-line missed You did not find it.   was among this model’s inputs and went unflagged.  It is the larg
177. `docs/agent/screen3.js:393` Taking it out costs ${drop} of held-out AUC.
178. `docs/agent/screen3.js:412-413` s3-block s3-noverdict No verdict, so nothing to score.
179. `docs/agent/screen3.js:422-425` Only the final answer is scored, so anything it wrote before that, on  the previous screen, does not count.  O
180. `docs/agent/screen3.js:431` The run ended before the agent finished.
181. `docs/agent/screen3.js:436` The cancelled request may still be billed by Anthropic.
182. `docs/agent/screen3.js:439-441` The model never replied, so there is no investigation on the previous  screen, partial or otherwise.  The mode
183. `docs/agent/screen3.js:445-448` Only a run the agent ends itself is scored, so nothing on the previous  screen counts, including any findings 
184. `docs/agent/screen3.js:455-456` The scorer that graded the   recorded runs
185. `docs/agent/screen3.js:458-459` does not score a run like this one, in its own words: “the answer could  not be parsed. This is a parse failur
186. `docs/agent/screen3.js:461-462` refuses a run like this one, in its own words: “A partial answer is not an  answer and is not scored.”
187. `docs/agent/screen3.js:467-470` You are told which it was because reloading deals the two candidates again,  so holding it back would buy you 
188. `docs/agent/screen3.js:491-493` Your run:  ${count(record.turns, 'turn')}, ${count(record.toolCalls, 'tool call')},  ${record.maxCost === null
189. `docs/agent/screen3.js:497` The cancelled request is not in that figure, and may still be billed.
190. `docs/agent/screen3.js:503-504` Of the recorded runs on the honest model, those that finished took   turns.
191. `docs/agent/screen3.js:507` One hit a ${stopped[0].limits.max_turns}-turn ceiling and was scored as no answer at all.
192. `docs/agent/screen3.js:509` ${count(stopped.length, 'run')} hit their turn ceilings and were scored as no answer at all.
193. `docs/agent/screen3.js:512-513` canary run finished in   canary runs finished in   — when there is something to find, the agent finds it and s
194. `docs/agent/screen3.js:517-518` tool call  are more  than any recorded run made. The previous highest was
195. `docs/agent/screen3.js:529-530` Precision ${result.precision.toFixed(2)} · Recall ${result.recall.toFixed(3)}  · F1 ${result.f1.toFixed(3)}
196. `docs/agent/screen3.js:545` Precision is
197. `docs/agent/screen3.js:549-550` The credited flag is   The credited flags are   ${cap(word(n))} of the credited flags ${n === 1 ? 'is' : 'are'
198. `docs/agent/screen3.js:552` , which the model never read — see ${n === 1 ? 'its card' : 'their cards'}.
199. `docs/agent/screen3.js:563-566` that one column Recall is  . The denominator is every leaking column in the key, and a flag  is credited by na
200. `docs/agent/screen3.js:568-569` This model reads none of the  , so counted over the columns  it reads there was nothing to find.
201. `docs/agent/screen3.js:571-574` This model reads   of the  ; counted over  , your recall is   This model reads   of the  . Which of your  cred
202. `docs/agent/screen3.js:581-583` For comparison,   flagged the one planted column, the only one there was, and scored a recall of   for it.
203. `docs/agent/screen3.js:586-588` That is why these three sit down here. They are the  scorer’s output, unchanged, and as a mark out of ten they

### docs/agent/ceilings.js

204. `docs/agent/ceilings.js:28-30` The run had spent ${spentApart(spend, ceiling, money)} when its last turn  ended, ${spend > ceiling ? 'past' :

### docs/agent/verdict.js

205. `docs/agent/verdict.js:59` The agent finished, but it wrote no final answer.
206. `docs/agent/verdict.js:61-62` The agent finished, but its final answer began a findings block  and did not close it in the required form.
207. `docs/agent/verdict.js:64-66` The agent finished, but its final answer contained a line the scorer  treats as the start of the answer, and n
208. `docs/agent/verdict.js:68-70` The agent finished, but its final answer contained a line the scorer  treats as the start of the answer, and t
209. `docs/agent/verdict.js:72-73` The agent finished, but its final answer contained no findings block  in the required form.
210. `docs/agent/verdict.js:75` No sentence for a run without a verdict of kind ${missing}.

### docs/agent/loop.js

211. `docs/agent/loop.js:52-63` The agent finished and gave its answer. The agent was cut off mid-sentence: one turn hit the per-request outpu
212. `docs/agent/loop.js:112` The system prompt still contains ${left[0]} after rendering.
213. `docs/agent/loop.js:165` A spend ceiling was set without a way to price usage.
214. `docs/agent/loop.js:311` The run ended (${termination}).

### docs/agent/provider.js

215. `docs/agent/provider.js:40` No model selected.
216. `docs/agent/provider.js:50` Unknown request shape '${model.shape}' for ${model.id}.
217. `docs/agent/provider.js:58` A cached request must end on a user turn.
218. `docs/agent/provider.js:67` The last user turn has no block to mark.
219. `docs/agent/provider.js:80` The request carries ${found} cache breakpoints; the API allows ${MAX_BREAKPOINTS}.
220. `docs/agent/provider.js:105-106` The model '${modelId}' was not accepted: ${msg || 'no such model'}.  It may have been retired. Choose another 
221. `docs/agent/provider.js:111` That API key was not accepted. Check it and try again.
222. `docs/agent/provider.js:116` The key was recognised but is not allowed to do this: ${msg}
223. `docs/agent/provider.js:121` Rate limited by the API. Wait a moment and run again.
224. `docs/agent/provider.js:126` The API returned a server error (${status}). This is not your key or your input.
225. `docs/agent/provider.js:130` The API rejected the request: ${msg} The API returned ${status}.
226. `docs/agent/provider.js:154-155` The request never reached the API. Check the connection; a blocked  request also looks like this.
227. `docs/agent/provider.js:164` The API returned a response that was not JSON.

### docs/agent/runfile.js

228. `docs/agent/runfile.js:90-91` browser-${startedAt.toISOString().replace(/[:.]/g, '-')} docs/scan.html, in a visitor’s browser
229. `docs/agent/runfile.js:96-106` Cost is computed from token counts against the price table in  docs/agent/models.js. It is not read from a bil
230. `docs/agent/runfile.js:118` assigned by this page
231. `docs/agent/runfile.js:144-145` From the loop’s own events, one entry per request. Cost is estimated  from token counts, not billed.

### docs/agent/viz.js

232. `docs/agent/viz.js:64` Leaked ${leakedText} against honest ${honestText}
233. `docs/agent/viz.js:109-110` Top ${rows.length} of ${r.ranking.length} returned; ${r.total_features} features in the model. ${r.returned} o
234. `docs/agent/viz.js:141` ${drop < 0 ? 'drops' : 'changes'} ${Math.abs(drop).toFixed(4)} ROC-AUC when removed
235. `docs/agent/viz.js:143` PR-AUC without the feature ${fmt(r.pr_auc_without_feature)}, a change of ${fmt(r.delta_pr_auc)}.
236. `docs/agent/viz.js:203` 0.5 — orders nothing
237. `docs/agent/viz.js:223-225` Pearson on test ${fmt(r.point_biserial_test)} ${r.n_unique_test} distinct values on test constant on test
238. `docs/agent/viz.js:253` ${r.returned} of ${r.precomputed_count} precomputed neighbours, Pearson on the test split.
239. `docs/agent/viz.js:318` ${r.match_count} matched "${r.query}"; ${r.returned} shown.

### docs/agent/models.js

240. `docs/agent/models.js:23-24` Claude Sonnet 5 What the twelve recorded runs used. Pick this to compare like with like.
241. `docs/agent/models.js:37-38` Claude Haiku 4.5 Cheaper and faster. Not the model the recorded runs used.
242. `docs/agent/models.js:78-79` ${model.label} may be retired from ${model.retirementNotBefore} (${days} days). If it stops resolving, pick an

242 entries.


## Check 7 scope: the claim sentences in the two READMEs

These are not frozen. This pass may rewrite any of them, and each one it changes needs a check 7 entry. A sentence left byte-identical needs no entry. Sentences listed as released prose below need no entry either.

Markdown table header and separator rows are structure, not text. They are outside both checks and are not listed. Table data rows are listed: each one states what a script does or what a run did.

Every sentence in `docs/README.md` is a claim. The file is five sentences about where the site is published, which pages read the exported data, why the folder is named `docs/`, and what `.nojekyll` does.


### README.md

1. `README.md:5` Most public models on the Lending Club data report AUCs above 0.90.
2. `README.md:5` Almost all of them are wrong: they train on columns that only exist *after* a loan's outcome is known, so the 
3. `README.md:5` It strips out every post-outcome column, keeps only what a lender would have at the moment of decision, and la
4. `README.md:7` A second layer hands an autonomous agent eight read-only tools and asks it to audit the finished model, withou
5. `README.md:7` Twelve live runs, eight of them usable, a planted canary, and an ablation that failed for a reason worth repor
6. `README.md:9` *Honest* is the discipline of surfacing it instead of hiding behind a flattering metric — including when the h
7. `README.md:13` All twelve recorded runs are replayable there turn by turn — every tool call, its arguments, and the full resu
8. `README.md:13` The page reads its figures from the exported bundle as it loads; none of them is typed in.
9. `README.md:21` Lending Club accepted loans, 2007–2018 (`accepted_2007_to_2018Q4.csv`, ~1.68 GB, kept read-only).
10. `README.md:25` | Raw | 2,260,701 |
11. `README.md:26` | Resolved loans only (Fully Paid / Charged Off) | 1,345,310 |
12. `README.md:27` | Issued 2014–2017 | 1,061,042 |
13. `README.md:29` `Current` and other in-progress statuses are dropped: an unresolved loan has no label to learn from.
14. `README.md:29` The final set is **1,061,042 loans at a 21.14% default rate**.
15. `README.md:29` The 2014–2017 window is chosen deliberately — earlier vintages sit inside the 2008 crisis, and by the data's D
16. `README.md:31` Target: `is_default`, 1 for Charged Off, 0 for Fully Paid.
17. `README.md:35` `total_pymnt` (how much the borrower has repaid) is the outcome wearing a disguise: high for paid loans, low f
18. `README.md:37` **41 columns** came out, and it took three passes to catch them all:
19. `README.md:39` - **Pattern matching (33 columns).** Payment totals, recoveries, refreshed FICO scores, the whole hardship and
20. `README.md:40` - **Reading the data dictionary (4 columns).** `last_credit_pull_d`, `payment_plan_start_date`, `deferral_term
21. `README.md:40` Automation misses these; a human reading each column's meaning does not.
22. `README.md:41` - **Missingness analysis (1 column).** `orig_projected_additional_accrued_interest` survived both earlier pass
23. `README.md:41` It is almost entirely missing because it only exists for borrowers already on a hardship plan — a leak that sh
24. `README.md:43` Every dropped column is logged with a one-line reason in `outputs/leakage_drop_log.txt`.
25. `README.md:43` Those 41 columns are also the ground truth Layer 2 was later built to rediscover from scratch.
26. `README.md:47` The split is **temporal, never random**: train on 2014–2016, test on 2017.
27. `README.md:47` A random split would let the model train on 2017 loans and test on 2014 ones, learning from the future to pred
28. `README.md:47` That never happens in deployment, and it quietly inflates every metric.
29. `README.md:49` Default rates rise across vintages (18.45% → 20.18% → 23.28% → 23.12%), so the 2017 test set is genuinely hard
30. `README.md:51` The 2017 test set is scored **exactly once**, at the very end.
31. `README.md:51` Tuning runs against a 2016 validation year carved out of training data, so the test set stays untouched until 
32. `README.md:53` Accuracy is never used.
33. `README.md:53` At a 21% default rate, a model that predicts "no default" for everyone scores 79% accuracy while catching zero
34. `README.md:53` Reported instead: **ROC-AUC** for ranking quality, **PR-AUC** for the minority class that actually matters.
35. `README.md:57` All on the 2017 temporal test set.
36. `README.md:61` | Logistic Regression (reference) | 0.7136 | 0.4105 | 0.2259 |
37. `README.md:62` | XGBoost (baseline) | 0.7181 | 0.4275 | 0.2139 |
38. `README.md:63` | XGBoost (tuned) | **0.7296** | **0.4404** | 0.2173 |
39. `README.md:67` *Baseline models only — Logistic Regression and untuned XGBoost.
40. `README.md:67` The tuned model is not plotted here.*
41. `README.md:69` PR-AUC against a prevalence floor of 0.2312: the tuned model roughly doubles what random ranking gives on the 
42. `README.md:73` **The tuned model generalises cleanly.** Validation AUC on 2016 was 0.72732; test AUC on 2017 was 0.7296.
43. `README.md:73` A gap of −0.0023.
44. `README.md:73` The tuning did not memorise the validation year.
45. `README.md:75` **0.73 is the honest ceiling here.** Origination-only information on this data tops out in the low 0.70s.
46. `README.md:75` If I had seen 0.85+, my first move would have been to hunt for the leak that survived, not to celebrate.
47. `README.md:75` Layer 2 later put that instinct to the test directly.
48. `README.md:77` Tuning was 50 Optuna trials (TPE, seed 42, 17.2 minutes).
49. `README.md:77` Best trial #21: depth 8, learning rate 0.019, 900 trees, 50% row subsampling.
50. `README.md:77` Regularisation done by sampling rather than explicit penalties.
51. `README.md:81` `07_audit.py` interrogates the trained model with SHAP and a set of rule-based honesty checks.
52. `README.md:85` **What carries the model.** `term`, `sub_grade`, `grade`, `dti`, `int_rate` lead, and eight of the top ten slo
53. `README.md:85` Every direction makes sense: longer terms, worse grades, higher DTI, higher rates and lower FICO all push risk
54. `README.md:85` Nothing with a leakage signature appears.
55. `README.md:87` **Three flags, three different verdicts.** The rule flags anything unexpected with high attribution; the judgm
56. `README.md:89` - `home_ownership_RENT` (rank 7).
57. `README.md:90` - `emp_length_was_missing` (rank 14).
58. `README.md:90` A genuine finding, and one I followed up.
59. `README.md:90` Applicants who do not state their employment length are measurably riskier, so the model uses "declined to ans
60. `README.md:90` Dropping it and retraining costs **0.0003 ROC-AUC** (`08_fairness_ablation.py`).
61. `README.md:90` The model does not depend on it, so it can go for fairness at essentially no cost.
62. `README.md:90` Also a case where SHAP overstates importance: rank 14, yet almost fully substitutable by correlated signals.
63. `README.md:91` - The bureau `_was_missing` flags.
64. `README.md:91` Layer 1 recorded these as dead weight at test time — Lending Club collected the underlying fields for everyone
65. `README.md:91` That was true of the column I checked and false of the family.
66. `README.md:91` Eleven of the twenty-two flags are constant zero in the 2017 test set; the other eleven fire, including `il_ut
67. `README.md:91` The original figure was wrong in both its count and its claim, and is corrected in `outputs/audit_notes.txt` w
68. `README.md:91` Layer 2 later turned these same flags into a deliberate trap, and the agent walked into it twice.
69. `README.md:93` **No slice failures.** AUC holds at 0.7268–0.7334 across all four 2017 quarters.
70. `README.md:93` Within-grade AUC is lower (0.629–0.706), which is expected: grade already does much of the ranking, so residua
71. `README.md:99` The model's most confident false positive was a G5, 60-month, 31%-interest small-business loan from a renter w
72. `README.md:99` Scored 0.96.
73. `README.md:99` The model was not wrong to call that risky — grade G loans default 50.8% of the time.
74. `README.md:99` That is irreducible uncertainty, not a bug, and separating the two is exactly what an audit is for.
75. `README.md:107` Layer 2 is the test.
76. `README.md:107` An agent gets eight read-only tools and the trained model, and is asked to report anything that would make the
77. `README.md:107` **It is never told what to look for.**
78. `README.md:111` The easy version of this project tells the agent to find target leakage, watches it find target leakage, and r
79. `README.md:113` So the system prompt contains no mention of leakage, of timing, of when a field is populated, or of anything h
80. `README.md:113` A self-check greps the prompt for seventeen steering terms and all 224 documented column names, and fails the 
81. `README.md:113` Even a column name in a code comment fails it, because the next person editing the prompt would read it.
82. `README.md:115` The agent gets the modelling task, eight tools, a budget, and a required output format.
83. `README.md:119` Eight read-only tools.
84. `README.md:119` Five came first: look up a column, search the dictionary, rank features by mean absolute SHAP, describe one fe
85. `README.md:121` Three were added later.
86. `README.md:121` Each reads a precomputed artefact and answers a question the original five could not.
87. `README.md:123` `get_feature_coverage` reports how one column is distributed and how complete it is, in the training data as a
88. `README.md:123` It is the only view with a time axis.
89. `README.md:125` `get_feature_target_association` reports how strongly one column orders the outcome on its own, apart from the
90. `README.md:125` Rank-based AUC, not corrected for direction, so a column that orders the outcome in reverse lands below 0.5 an
91. `README.md:125` A column can be near-invisible in both SHAP and ablation and still be a strong standalone predictor.
92. `README.md:127` `get_correlated_features` lists the columns that move most with a given column, by Pearson correlation on the 
93. `README.md:127` Ablation alone cannot tell "carries no information" apart from "another column carries the same information".
94. `README.md:127` This separates them.
95. `README.md:131` `search_data_dictionary` used to be case-insensitive substring matching over names and descriptions.
96. `README.md:131` Asking it about utilisation returned nothing, because no description contains that word.
97. `README.md:133` It has two tiers now.
98. `README.md:133` Names are still matched literally, in dictionary order, so a query like `mths_since` returns the whole family 
99. `README.md:133` Beyond that, entries are ranked by cosine distance between the query and the description embedding.
100. `README.md:133` The model is `BAAI/bge-small-en-v1.5`, pinned to a commit rather than a branch, 384 dimensions, L2-normalised.
101. `README.md:133` Vectors live in Postgres with pgvector, running locally in Docker on port 5433.
102. `README.md:135` There is no HNSW or IVFFlat index on the vectors, and that is a decision rather than an omission.
103. `README.md:135` The table holds 224 rows.
104. `README.md:135` A sequential scan over 224 vectors of 384 dimensions runs in well under a millisecond and returns the true nea
105. `README.md:135` An approximate index would be slower to build, no faster to query, and would introduce a recall parameter capa
106. `README.md:137` Only the `description` field is embedded.
107. `README.md:137` Not the column name, not `source`, and not `populated`.
108. `README.md:137` `populated` is stored and returned alongside a hit but is never indexed, filtered on, or scored, because one o
109. `README.md:139` If the database is unreachable the search falls back to the old substring matching.
110. `README.md:139` The agent is told nothing about which path served it.
111. `README.md:139` The run's configuration stamp records it, so a fallback run is never mistaken for an indexed one.
112. `README.md:141` Retrieval quality is measured against 28 probes in [RETRIEVAL_EVAL.md](outputs/agent_cache/RETRIEVAL_EVAL.md).
113. `README.md:141` Paraphrase questions went from returning nothing to usually returning the right answer first.
114. `README.md:141` Conceptual questions about provenance and lifecycle remain the weak family.
115. `README.md:145` Both are constructor arguments on the tool layer.
116. `README.md:145` Neither appears in any published tool schema, and `dispatch()` rejects either if the agent sends it as a tool 
117. `README.md:147` `include_populated` drops the dictionary's `populated` field, which says when a column receives its value.
118. `README.md:147` The definition stays; the lifecycle position goes.
119. `README.md:149` `include_vintage_scopes` drops every per-vintage measurement.
120. `README.md:149` `get_feature_coverage` returns only train and test, and `get_feature_target_association` drops its three per-y
121. `README.md:149` The keys are absent rather than blanked, and nothing says anything was withheld, because saying so would tell 
122. `README.md:153` Two full runs against the real model.
123. `README.md:153` Both completed, both stopped on their own budget, both produced correctly formatted answers.
124. `README.md:155` **Neither found any leakage.
125. `README.md:155` Recall 0.0.**
126. `README.md:157` Every leaking column had already been removed in Layer 1.
127. `README.md:157` They are not inputs to the model it was auditing.
128. `README.md:159` In one run the agent looked up `loan_status`, identified it as the likely source of the default label, reasone
129. `README.md:161` What it flagged instead were distribution problems: two features that are near-constant in the 2017 window, an
130. `README.md:161` They are just not the concern the answer key scores.
131. `README.md:163` So the zero says something about the ground truth, not only about the agent.
132. `README.md:163` That mismatch is recorded as unresolved in `EVAL_NOTES.md` rather than papered over.
133. `README.md:169` I put `recoveries` back into the feature matrix — a column whose value is set only after a loan has already ch
134. `README.md:173` | Layer 1 model (180 features) | 0.7296 | 0.4404 |
135. `README.md:174` | Canary model (181 features) | **0.8730** | **0.8017** |
136. `README.md:176` `out_prncp` and `hardship_flag` look like obvious leaks on paper but are constant in the resolved 2014–2017 su
137. `README.md:176` `recoveries` fires on two thirds of defaults with probability 1.0 — genuinely leaking, but not so overwhelming
138. `README.md:180` One long bar and nineteen short ones.
139. `README.md:180` `recoveries` takes 44.6% of total attribution, 8.7× the next feature.
140. `README.md:180` `int_rate` — rank 5 in the honest model — falls to rank 18 here.
141. `README.md:180` That is what leakage does: it does not just add signal, it crowds out the real one.
142. `README.md:182` **Caught. 13 tool calls, 6 turns, high confidence, zero false positives.** The earlier runs had each taken aro
143. `README.md:182` Its stated reason cited three independent routes: the field's description, its SHAP rank, and the ablation del
144. `README.md:184` `recoveries` is the loudest possible case, and that limit belongs in the result.
145. `README.md:184` A catch here establishes that detection works when the leak is a model input and signalled three ways at once.
146. `README.md:184` It says nothing about a subtle one.
147. `README.md:188` The plan was to measure how much the agent depended on the data dictionary's timing field by suppressing it an
148. `README.md:190` Before running it, I scanned every true positive's description.
149. `README.md:190` **Thirty-six of thirty-nine carry lifecycle wording in the description itself.** `recoveries` is defined as mo
150. `README.md:190` `hardship_amount` as interest owed while a hardship plan is in effect.
151. `README.md:190` Suppressing one uniform field removes almost nothing.
152. `README.md:194` It showed nothing.
153. `README.md:194` Same two flags, same zero recall, 50 calls against 52.
154. `README.md:194` The finding is that on this dataset, leakage detection cannot be cleanly separated from reading definitions, b
155. `README.md:198` **The scorer had a blind spot.** Each of the 14 hard negatives has a `_was_missing` twin in the feature matrix
156. `README.md:198` The agent flagged two derivatives; they scored as unremarkable false positives, and the report read as two ord
157. `README.md:200` The gap was one-directional — it could only ever undercount false positives, never inflate recall — because tr
158. `README.md:200` That property is now asserted in the answer key's self-check, so it fails loudly if a future change breaks it.
159. `README.md:202` **Two paid runs were lost to a token ceiling set too low.** Both are in the register with the reason they were
160. `README.md:202` A register showing one successful run and nothing else would misrepresent what this took.
161. `README.md:206` The planted column was caught in every canary configuration, including with the per-vintage view withheld.
162. `README.md:206` What varied between configurations was the number of false positives, not whether the leak was found.
163. `README.md:208` Detection never depended on the annual breakdown.
164. `README.md:208` The split-only run's stated evidence was the dictionary entry, a 44.6% share of total absolute SHAP, and the a
165. `README.md:210` On the honest cache the expanded surface did not improve the score.
166. `README.md:210` Every scored honest-cache run in this project sits at precision 0.000, recall 0.000 and f1 0.000, on both tool
167. `README.md:210` Suppressing `populated` moved neither number, which is what I predicted from the description scan below, thoug
168. `README.md:212` The full results, the figures, and what the evaluation cannot measure are in [LAYER2_EVAL.md](outputs/agent_ca
169. `README.md:218` | run3 | 5 | populated included | 180 | completed, 16 turns / 52 calls | 2 | 0 | 2 | — |
170. `README.md:219` | run4 | 5 | populated suppressed | 180 | completed, 16 turns / 50 calls | 3 | 0 | 3 | — |
171. `README.md:220` | run5 | 5 | populated included | 181 | completed, 6 turns / 13 calls | 1 | 1 | 0 | **caught** |
172. `README.md:221` | run6 | 8 | populated included, all scopes | 181 | completed, 6 turns / 17 calls | 1 | 1 | 0 | **caught** |
173. `README.md:222` | run7 | 8 | populated included, all scopes | 180 | completed, 14 turns / 33 calls | 1 | 0 | 1 | — |
174. `README.md:223` | run8 | 8 | populated included, split only | 181 | completed, 13 turns / 31 calls | 3 | 1 | 2 | **caught** |
175. `README.md:224` | run9 | 8 | populated suppressed, all scopes | 180 | turn limit at 20, unusable | none | n/a | n/a | — |
176. `README.md:225` | run10 | 8 | populated suppressed, all scopes | 180 | completed, 12 turns / 29 calls | 3 | 0 | 3 | — |
177. `README.md:226` | run11 | 8 | populated included, all scopes, prompt caching on | 180 | completed, 11 turns / 33 calls | 3 | 0
178. `README.md:228` Three earlier runs terminated as truncated or limit-hit and are not results.
179. `README.md:228` They are listed in `EVAL_NOTES.md` with their reasons.
180. `README.md:228` Six MOCK directories are also committed as verification evidence for the config_id fix and the two ablation-sw
181. `README.md:230` Recall is not comparable across matrices: the denominator is 39 true positives in every row, but none is prese
182. `README.md:234` **The agent cannot read the answer.** No file-read tool, no shell, no directory listing, no code execution.
183. `README.md:234` Eight tools, each bound to one known artefact, with every filename a fixed constant joined to a cache director
184. `README.md:234` `outputs/leakage_drop_log.txt` holds the ground truth and is unreachable.
185. `README.md:234` A runtime audit hook re-run over all eight tools and every error path confirms that a tool call opens the six 
186. `README.md:236` **The ground truth was written before the agent existed.** Deliberately.
187. `README.md:236` If the agent had come first, I would have read its output and then written a key that happened to match it.
188. `README.md:238` **Not every stop is a finish.** A turn cut off at the token limit and a turn that ends normally both carry zer
189. `README.md:238` The loop distinguishes them, and anything that is not a clean `end_turn` is marked unusable and refused by the
190. `README.md:238` That guard caught a real truncated run that would otherwise have scored as an answer.
191. `README.md:240` **Reasons are not graded automatically.** Whether a correct flag came from sound reasoning cannot be settled m
192. `README.md:242` **Mock and real runs cannot be confused.** Mode is stamped in the directory name, the manifest, and the first 
193. `README.md:242` The scorer refuses to score a mock run even when it parses cleanly.
194. `README.md:246` Every run directory is committed, transcripts and thinking summaries included.
195. `README.md:246` The scorer runs on a fresh clone with no regeneration and no API key:
196. `README.md:253` Every number in `EVAL_NOTES.md` can be re-derived from what is in the repository.
197. `README.md:259` Each script writes a plain-text notes file to `outputs/`, so the reasoning trail exists on disk rather than on
198. `README.md:265` | `01_data_exploration.py` | First look; flags leakage suspects |
199. `README.md:266` | `02_build_dataset.py` | Filters to 2014–2017 resolved loans, drops the 41 columns |
200. `README.md:267` | `03_split.py` | Temporal train/test split by issue year |
201. `README.md:268` | `04_features.py` | Feature prep, all transforms fit on train only |
202. `README.md:269` | `05_baseline.py` | Logistic Regression + untuned XGBoost, to set the bar |
203. `README.md:270` | `06_tune.py` | Optuna tuning against a 2016 validation year |
204. `README.md:271` | `07_audit.py` | SHAP explanations + rule-based honesty checks |
205. `README.md:272` | `08_fairness_ablation.py` | Cost of dropping a fairness-sensitive feature |
206. `README.md:278` | `precompute.py` | Caches SHAP and drop-one ablations so the agent never recomputes at runtime |
207. `README.md:279` | `data_dictionary.py` | 224 documented columns, and the two-tier search over them |
208. `README.md:280` | `retrieval.py` | pgvector client for the semantic tier; connection and model from the environment only |
209. `README.md:281` | `tools.py` | The eight tools, both ablation switches, and the call log |
210. `README.md:282` | `prompts.py` | System prompt and answer format, with the steering-term self-check |
211. `README.md:283` | `agent.py` | The ReAct loop, budgets, and termination classification |
212. `README.md:284` | `run_audit.py` | Runner, mode stamping, and run artefacts |
213. `README.md:285` | `answer_key.py` | Ground truth and scorer, written before the agent existed |
214. `README.md:286` | `eval_canary.py` | Parsing, scoring, and run comparison |
215. `README.md:287` | `plant_canary.py` | Builds the 181-feature canary matrix and model |
216. `README.md:293` - **Resolution bias in the 2017 test set.** The data ends Dec 2018, so a 36-month loan issued in mid-2017 coul
217. `README.md:293` The 2017 resolved subset over-represents both, and its 23.12% default rate is not the true vintage rate. 2014–
218. `README.md:293` The agent independently raised a version of this in run4 without being pointed at it.
219. `README.md:294` - **Probabilities are not calibrated.** Class weighting shifts predicted probabilities upward to favour recall
220. `README.md:294` Ranking metrics are unaffected.
221. `README.md:294` Calibration is not addressed anywhere in this repository.
222. `README.md:295` - **The canary establishes a floor, not a ceiling.** Tier A detection only.
223. `README.md:295` Nothing here shows the agent would catch a leak without a descriptive giveaway.
224. `README.md:296` - **The timing ablation cannot answer its own question** on this dictionary, for the reason given above.
225. `README.md:297` - **Three answer-key columns reach the site without a description.** `last_credit_pull_d`, `last_fico_range_hi
226. `README.md:297` The key holds their descriptions in `CLEAN_UNDER_SUPPRESSION`, but `scripts/export_site_bundle.py` only copies
227. `README.md:297` The scan page says they have no tier and quotes nothing for them.
228. `README.md:297` Fixing it means changing the export and re-exporting the bundle, which changes its provenance hashes.
229. `README.md:297` That hasn't been worth doing for this alone.
230. `README.md:298` - **Nothing checks that the data files match the code.** GitHub Pages lets a browser keep each file for up to 
231. `README.md:298` The scan page checks that its JavaScript modules all come from one build, and refuses to run if they don't (`s
232. `README.md:298` The data files under `docs/data/` aren't part of that check.
233. `README.md:298` The pages fetch them with `cache: 'no-cache'`, so a browser's own copy is revalidated on every load and can't 
234. `README.md:298` If a stale data file reached a visitor some other way, for example from Pages' CDN just after a re-export, not
235. `README.md:298` That path hasn't been tested.
236. `README.md:299` - **A stale data file would be shown as if it were current.** Usually nothing on the page would look wrong.
237. `README.md:299` The scan page's refusal only looks at its modules, so it won't fire for a stale data file.
238. `README.md:299` The page would run on the old file.
239. `README.md:299` Depending on which file it is, the agent could get tool results from the earlier export, or Screen 3 could sco
240. `README.md:299` Where the old key fails one of the checks the page makes before it scores anything, the visitor sees "This run
241. `README.md:300` - **Ten minutes is a stated maximum, not a measured one.** The scan page's refusal says copies of its files ca
242. `README.md:300` That figure comes from the `max-age=600` header GitHub Pages sends on every file.
243. `README.md:300` How long Pages' CDN actually keeps an old copy hasn't been measured.
244. `README.md:301` - **The first deploy of the build stamps is unprotected.** That deploy went out on 19 September 2026.
245. `README.md:301` A visitor whose browser still holds the `scan.js` from before it has no loader, so nothing checks their module
246. `README.md:301` They run the same code as before: apart from the stamp line and four comments, every module under `docs/agent/
247. `README.md:301` That was checked on the diff.
248. `README.md:301` By the header's stated maximum, no browser uses that old `scan.js` more than ten minutes after the deploy, and
249. `README.md:301` How long a copy held by Pages' CDN lasts hasn't been measured, as the entry above says.
250. `README.md:302` - **Nothing tests Screen 3 for that visitor.** The verdict harness ran the old `scan.js` over the new modules 
251. `README.md:302` That Screen 3 was unchanged rests on the diff: `docs/agent/screen3.js` changed only in its stamp and comments.
252. `README.md:303` - **Nothing enforces the pre-push checks.** The hook in `.githooks/` is an opt-in local guard (see Reproducing
253. `README.md:303` What would enforce them is branch protection on `main` requiring them to pass, run by GitHub Actions, with byp
254. `README.md:303` It would mean pushing each change to another branch and merging it once the checks pass, so the site would dep
255. `README.md:304` - **This is a research pipeline, not a service.** Single scripts and no packaging.
256. `README.md:304` Beyond each module's self-check, the tests are three scripts under `scripts/`: for the trajectory metrics, for
257. `README.md:308` Layer 3 is partly built.
258. `README.md:308` Layer 2 audits a model with a fixed tool surface; Layer 3 asks what happens when the tools themselves are not 
259. `README.md:310` Each phase was preregistered before it ran and reported with what it does not establish.
260. `README.md:310` The specifications are `PREREGISTRATION_PHASE2.md` to `PREREGISTRATION_PHASE5.md`, and the results are in `out
261. `README.md:314` - **Prompt caching and a spend ledger with a hard cap** (Phase 2).
262. `README.md:314` On one measured audit run, input cost came out 71.1% below the base rate.
263. `README.md:315` - **A sandbox and a known-answer validator** (Phase 3).
264. `README.md:315` Six hand-written correct tools pass, and fourteen hand-written broken tools are each rejected with the predict
265. `README.md:316` - **A gap detector and a tool-spec generator** (Phase 4 and 4b), run over 26 fixed questions.
266. `README.md:316` The detector was not accepted under its frozen rules in either version.
267. `README.md:316` Its failures were of three kinds:
268. `README.md:317` - **format:** 20 of 52 replies did not parse, then 11 of 52 after the instruction was rewritten;
269. `README.md:318` - **judgement:** a null answer read as no answer;
270. `README.md:319` - **grounding:** a right label with the wrong evidence cited.
271. `README.md:320` - **One generated tool, taken from code generation to a registry decision** (Phase 5).
272. `README.md:320` `get_top_shap_rows`, from one Phase 4 spec, passed its three test cases on 9 of 9 sandbox runs, and was admitt
273. `README.md:324` - **Validation is self-consistency only.** The tool's expected answers were read from the same file its data w
274. `README.md:324` No independent answer exists, and the tool is recorded as admitted, never as validated.
275. `README.md:325` - **The chain did not run end to end.** Detection and the spec were read from a Phase 4 record.
276. `README.md:325` Only code generation, the sandbox, validation and the registry decision ran live.
277. `README.md:326` - **The detector was not accepted.**
278. `README.md:327` - **Nothing reads the registry.** Admission exposes the tool to no agent.
279. `README.md:329` Four planned parts were cut, each because it had no real target or no independent reference to judge it agains
280. `README.md:331` - **a human-in-the-loop checkpoint,** because nothing is waiting to be gated;
281. `README.md:332` - **an Agent-as-a-Judge with a separate verifier,** because what it would judge either already has a mechanica
282. `README.md:333` - **a fix for the detector's format failure,** because no request-level mechanism fits its frozen output forma
283. `README.md:334` - **an adversarial test,** because no Layer 3 component has both a live target and an independent reference, a
284. `README.md:336` The reasons are recorded in amendments A6 to A8 of `PREREGISTRATION_PHASE5.md` and in `outputs/layer3/LAYER3_P
285. `README.md:348` The dataset is gitignored.
286. `README.md:348` Download `accepted_2007_to_2018Q4.csv.gz` from the [Lending Club dataset on Kaggle](https://www.kaggle.com/dat
287. `README.md:353` python src/02_build_dataset.py        # ~1 min
288. `README.md:354` python src/03_split.py                # seconds
289. `README.md:355` python src/04_features.py             # ~1 min
290. `README.md:356` python src/06_tune.py                 # ~18 min
291. `README.md:357` python -m agent.precompute            # ~13 min
292. `README.md:358` python -m agent.plant_canary          # ~2 min
293. `README.md:359` python -m agent.precompute --canary   # ~13 min
294. `README.md:362` Roughly 50 minutes after the download, dominated by the tuning study and the two SHAP passes.
295. `README.md:362` Tuning is seeded, so the 0.7296 baseline should reproduce exactly.
296. `README.md:364` A live agent run additionally needs `ANTHROPIC_API_KEY` in `.env`.
297. `README.md:364` Scoring the committed runs does not.
298. `README.md:366` Pushes to `main` deploy the site.
299. `README.md:366` A pre-push hook checks the commit being pushed: the module stamps, the stale test copies, and that every impor
300. `README.md:366` It is off until you turn it on in your clone:
301. `README.md:372` A fresh clone has it off, `git push --no-verify` and commits made in GitHub's web editor skip it, and nothing 
302. `README.md:374` The hook checks the commit being pushed, never the working tree.
303. `README.md:374` Uncommitted changes are neither checked nor pushed, so a push from a working tree with uncommitted edits can p
304. `README.md:376` Built with Python 3.11, pandas, scikit-learn, XGBoost, SHAP, Optuna, and the Anthropic API.

### docs/README.md

305. `docs/README.md:3-5` This folder is the static site published at <https://sidharthjatt.github.io/honest-mistake/>.
306. `docs/README.md:3-5` `index.html` is the landing page; it and the other two pages read the exported JSON under `data/` at load.
307. `docs/README.md:7-8` It is named `docs/` rather than `site/` because GitHub Pages deploying from a branch will serve the repository
308. `docs/README.md:10-12` `.nojekyll` keeps Jekyll away from what is served.
309. `docs/README.md:10-12` Nothing here starts with an underscore, so nothing was being dropped; the file removes the possibility rather 

### Released prose (not claims, no check 7 entry needed)

P1. `README.md:3` A credit-default model built the honest way, and an agent that tries to catch it cheating.
P2. `README.md:5` This project does the opposite.
P3. `README.md:5` That lower number is the point.
P4. `README.md:7` Then it goes a step further.
P5. `README.md:9` The name is deliberate.
P6. `README.md:9` *Mistake* is the hidden leakage a model carries.
P7. `README.md:35` A feature leaks if it would not exist at the moment you make the prediction.
P8. `README.md:35` Train on it and you get a beautiful, useless model.
P9. `README.md:49` That is the same drift a deployed model faces.
P10. `README.md:89` Flagged, benign.
P11. `README.md:89` Renters defaulting more often is real borrower economics, not an artifact.
P12. `README.md:99` It paid off.
P13. `README.md:105` The audit above is mine.
P14. `README.md:105` I knew where the leaks were, because I removed them.
P15. `README.md:105` That makes it a demonstration, not a test.
P16. `README.md:111` That result belongs to whoever wrote the prompt.
P17. `README.md:115` Where it goes from there is its own.
P18. `README.md:157` That is not the agent failing.
P19. `README.md:159` That is the correct call.
P20. `README.md:159` A column the model cannot see is not a route by which it sees the answer.
P21. `README.md:161` Those are real concerns about whether the held-out number means what it appears to mean.
P22. `README.md:176` The choice was measured, not assumed.
P23. `README.md:192` I could have reworded the dictionary to make the ablation look clean.
P24. `README.md:192` A description of `hardship_amount` that omits the hardship plan would be false, not neutral.
P25. `README.md:192` So the dictionary stayed accurate and the ablation ran knowing what it would show.

309 claim sentences and 25 released prose sentences. This pass may rewrite the prose, and check 7 does not apply to it.

## Check 7 entries

Each rewritten claim sentence gets one: the sentence as it now reads, the file and line that establishes it, and what was checked.

**E1. 2026-09-20. Punctuation only, thirteen claim sentences in `README.md`.** Each em-dash in a claim sentence in the lead and in Layers 1 and 2 was replaced by a comma or a colon. No word was added, removed or reordered, so no re-verification was needed. The six em-dashes in the run register table are the "no canary" marker rather than punctuation and were left alone, as were the three in image alt text. The sentences, at their new lines:

- `README.md:13` "behind a flattering metric, including when the honest result is a zero."
- `README.md:17` "replayable there turn by turn:" (was an em-dash pair; now a colon and a comma)
- `README.md:33` "chosen deliberately: earlier vintages"
- `README.md:43` "settlement family: anything matching"
- `README.md:45` "already on a hardship plan, a leak"
- `README.md:71` "*Baseline models only: Logistic Regression"
- `README.md:101` "dead weight at test time: Lending Club"
- `README.md:115` "not wrong to call that risky: grade G loans"
- `README.md:191` "about outcome maturity, that 60-month loans"
- `README.md:201` "into the feature matrix, a column whose value" (was an em-dash pair; now two commas)
- `README.md:208` "with probability 1.0, genuinely leaking"
- `README.md:214` "`int_rate`, rank 5 in the honest model, falls" (was an em-dash pair; now two commas)
- `README.md:224` "one-directional: it could only ever undercount" (was an em-dash pair; now a colon and a comma)

The line numbers above are those of the commit that adds this entry. Seven of them, from `README.md:101` on, were first written as the lines of an earlier draft, four to eight lines too low, and were corrected before commit by finding each quoted fragment in the file.

**E2. 2026-09-22. `README.md:149`, the sentence that opens the retrieval section's case for semantic search.** Manifest entry 96 (`README.md:131` at 62f8d3e) read "Asking it about utilisation returned nothing, because no description contains that word." It was false at every version checked from 97a339c, where it was written, to HEAD: `revol_util`'s description is "Revolving line utilisation: percent of available revolving credit the borrower is using.", and the old substring tier returns `revol_util` for the query `utilisation`. It now reads:

> Asking it how much of their available credit a borrower is using returned nothing, because a substring match needs the whole question to appear inside a description, and none contains it.

The example is the `par-utilisation` probe in `scripts/retrieval_probes.py`, whose query is "how much of their available credit is the borrower using". What was checked: `RETRIEVAL_EVAL.md` records the keyword backend as empty on all 7 paraphrase probes, this one included; `_substring_description_hits` in `agent/data_dictionary.py` tests `q_lower in entry["description"].lower()`, so the whole query has to appear; and on 2026-09-22 that tier, run on the probe's query, returned no name hits and no description hits. A first rewrite gave the reason as "no description uses those words". That was also false, since `revol_util`'s description uses most of them, and it was replaced before this entry was written.

**E3. 2026-09-22. `RETRIEVAL_EVAL.md` is loose on the same probe, and is not edited.** Its summary says substring matching returns nothing on the paraphrase probes "because the question does not reuse the dictionary's vocabulary". For `par-utilisation` that is loose: `revol_util`'s description shares most of the question's words, and the empty result comes from matching the whole query as one substring. The file is a frozen record and is out of this pass's scope, so it stays as it is. This entry is the note.

**E4. 2026-09-22. `README.md:155`, the latency sentence, recorded rather than rewritten.** "A sequential scan over 224 vectors of 384 dimensions runs in well under a millisecond and returns the true nearest neighbours every time." The plan for the query `search_descriptions` sends is Limit, Sort, Seq Scan, so the neighbours are exact, and the table holds 224 rows at dimension 384. Over 50 warm executions of that query (five questions, ten times each, via `EXPLAIN ANALYZE`), the median was 0.10 ms. Two cold first queries on a fresh connection measured 1.06 ms and 1.76 ms. The sentence holds for warm queries and not for a cold first one. It is left unchanged, and the cold figures are recorded here.

**E5. 2026-09-22. Where the retrieval section was verified.** Every sentence of the two retrieval sections (`README.md` "Dictionary search is semantic now" and "The semantic tier of the dictionary search") was checked against the main working copy's existing index, not against a clean clone. The clone made for this on 2026-09-20 was lost with its session scratchpad. A second clone could not have used the README's commands unaltered on this machine either: `docker/docker-compose.yml` hardcodes the container name `honest-mistake-pgvector`, the project name `honest-mistake` and the volume `honest-mistake-pgdata`, and those collide with the instance already running for this working copy. A reader cloning fresh has no such instance and does not meet the collision. On the existing index, `retrieval.index_stats()` reported 224 rows, 224 embeddings, dimension 384, and a mock run stamped `toolsv2.0-populated-included-scopes-all-retrieval-pgvector-bge-small-en-v1.5-layer1`, against `retrieval-keyword-fallback` on the clone with no database on 2026-09-20.

**E6. 2026-09-22. What the retrieval check did not cover.**
- That `scripts/build_dict_index.py` embeds the description field alone. The claim was checked on the query side, where no `WHERE` clause and no index touches `populated`, but the build script was not read.
- `docker compose up -d --wait`, `down` and `down -v`. None was run, because each would have acted on the existing container.
- The 28-probe results in `RETRIEVAL_EVAL.md`. They were not re-run on 2026-09-22.

**E7. 2026-09-22. `README.md:234`, one word: "below" became "above".** Manifest entry 167 (`README.md:210` at 62f8d3e) said the result was what "I predicted from the description scan below". The scan ("Before running it, I scanned every true positive's description") comes before that sentence, at line 190 against 210 at HEAD, and at line 175 against 234 now, so the pointer was false at HEAD and not made false by this pass. What was checked: the two line positions, by reading, in both versions. No other word changed. The README's four other above/below pointers, at lines 143, 159, 445 and 501, were read and point the right way.

**E8. 2026-09-23. `docs/README.md`, the opening rewritten and D22's sentence corrected.** The first sentence, "This folder is the static site published at <https://sidharthjatt.github.io/honest-mistake/>.", is unchanged except that its line break was removed. Three sentences are new. Each one was checked:

- "Run that from the repository root and open the address it prints." The fenced command above it, `python3 -m http.server -d docs 8000`, run from the repository root on 2026-09-23, printed "Serving HTTP on :: port 8391 (http://[::]:8391/) ..." on a spare port.
- "There is no build step." `docs/` holds the four pages, their scripts, `style.css`, `data/` and `.nojekyll`, with no package manifest or build configuration, and Pages serves the folder as committed.
- D22's sentence now reads: "`index.html` is the landing page; it and the other three pages, `runs.html`, `replay.html` and `scan.html`, read the exported JSON under `data/` at load." `index.html:87` and `runs.html:72` fetch `runs/index.json` and `scoring.json` at load. `replay.html:41` fetches `bundle.json`, and `:65` fetches the run and `scoring.json`. `scan-page.js` `boot()` (lines 128 to 133) fetches `data/tools/` and `data/runs/index.json`, and `startPage()` (line 1041) calls it once `scan.js:153` has checked the build. D22 gets a dated resolution line.

**E9. 2026-09-23. `README.md:5`, the scoring command moved into a fence.** "Scoring the committed agent runs takes one command and no API key: `python -m agent.eval_canary …`" became the same command as a fenced block, followed by "Scoring the committed agent runs takes that one command and no API key." The words changed from "one command" to "that one command" and the colon went, and nothing else changed. The claim is the one D25's fix made true: on 2026-09-20 `eval_canary --run` and `--compare` ran on a clone with no `data/` directory and no key. The fence adds four lines, so the `README.md` line numbers in E2, E4 and E7 are those at eebc26d, and each is now four higher.

## Deadline

2026-09-23. Anything not done by then is recorded at the bottom of this file as not done, and the pass closes.
