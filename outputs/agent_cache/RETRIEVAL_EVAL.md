# Retrieval evaluation — keyword vs semantic

## Method

28 probes, written as questions an auditor would ask rather than as rearranged descriptions, are run through three backends. **keyword** is the substring matching `search()` used before the vector index existed. **sem-band** is the first semantic configuration: name matching, then every neighbour within 0.05 cosine distance of the closest hit, under an absolute ceiling of 0.45. **sem-topk** is the current configuration: name matching, then the nearest 10 neighbours under the same ceiling, with no relative band. All three see the same query and are scored against the same expected sets, which have not been touched since before either semantic configuration was measured. Expected sets are my judgement about what answers each question, with a one-line reason in `scripts/retrieval_probes.py`; 7 probes are marked uncertain there and are included rather than quietly dropped. recall@k is the share of the expected set in the first k results, MRR the reciprocal rank of the first correct hit. The four `none` probes have empty expected sets, so only the empty count carries information for them. Run in 7.6s.

## Results by family

```
| family      |  n | keyword r@5 | sem-band r@5 | sem-topk r@5 | keyword r@10 | sem-band r@10 | sem-topk r@10 | keyword MRR | sem-band MRR | sem-topk MRR | keyword empty | sem-band empty | sem-topk empty |
|-------------|----|-------------|--------------|--------------|--------------|---------------|---------------|-------------|--------------|--------------|---------------|----------------|----------------|
| lexical     |  5 |       0.671 |        0.721 |        0.821 |        0.743 |         0.843 |         0.943 |       0.800 |        0.900 |        0.900 |             1 |              0 |              0 |
| paraphrase  |  7 |       0.000 |        0.374 |        0.374 |        0.000 |         0.412 |         0.412 |       0.000 |        0.775 |        0.762 |             7 |              0 |              0 |
| conceptual  |  7 |       0.000 |        0.137 |        0.205 |        0.000 |         0.198 |         0.287 |       0.000 |        0.434 |        0.476 |             7 |              0 |              0 |
| identifier  |  5 |       0.585 |        0.585 |        0.585 |        0.723 |         0.723 |         0.723 |       1.000 |        1.000 |        1.000 |             0 |              0 |              0 |
| none        |  4 |        --   |         --   |         --   |         --   |          --   |          --   |        --   |         --   |         --   |             4 |              0 |              0 |
| ALL         | 28 |       0.262 |        0.421 |        0.462 |        0.305 |         0.504 |         0.551 |       0.375 |        0.748 |        0.757 |            19 |              0 |              0 |
```

## What changed, and that it was changed after seeing the numbers

The relative band was replaced with a fixed cap of 10 after reading the first eval. That is tuning, and it should be read as tuning: the constant was not chosen from a held-out set, it was chosen after looking at these exact probes. The probe set was frozen before the change and not touched since, which limits the damage but does not undo it. Anything in the sem-topk column is a fit to 28 probes I wrote myself.

What changed, precisely: tier 2 was `everything within 0.05 of the closest hit, under a 0.45 ceiling`, and is now `the nearest 10, under the same 0.45 ceiling`. The band is gone; the ceiling is unchanged. The reason is not that the band scored badly on average but that it failed in two opposite directions at once — closing at 0.285 on `lex-fico` and letting 87 entries through on `con-derived` — so no value of the constant fixed both. A fixed cap is a different kind of statement: that in a corpus of 224 one-sentence entries a useful answer is never 87 items long, whatever the distances happen to be.

**Probes that improved (5):**

- `lex-fico` (lexical) — r@10 0.500 to 1.000, MRR 1.000 to 1.000; 2 results became 10.
- `con-after-outcome` (conceptual) — r@10 0.000 to 0.286, MRR 0.000 to 0.333; 2 results became 10.
- `con-identifies-person` (conceptual) — r@10 0.333 to 0.667, MRR 1.000 to 1.000; 1 results became 10.
- `none-branch-staff` (none) — 14 results became 10; expected none.
- `none-social` (none) — 13 results became 10; expected none.

**Probes that got worse (5):**

- `par-job-tenure` (paraphrase) — r@10 0.000 to 0.000, MRR 0.091 to 0.000; 14 results became 10.
- `con-derived` (conceptual) — r@10 0.000 to 0.000, MRR 0.018 to 0.000; 87 results became 10.
- `con-time-anchor` (conceptual) — r@10 0.000 to 0.000, MRR 0.017 to 0.000; 78 results became 10.
- `none-weather` (none) — 4 results became 10; expected none.
- `none-vehicle` (none) — 3 results became 10; expected none.

## Where sem-topk did worse than keyword

4 of 28 probes, quoted in full with both result lists, marked `*` where a result is in the expected set.

### `none-weather` — none

> what was the weather like on the day the loan was issued

Expected (0): nothing

Why: The dictionary holds no environmental data of any kind.

Scores — keyword r@10   --   MRR   --   | sem-band r@10   --   MRR   --   | sem-topk r@10   --   MRR   --  

Keyword returned:
```
    (empty)
```
sem-topk returned:
```
     1.   issue_d
     2.   last_pymnt_d
     3.   total_rec_int
     4.   hardship_loan_status
     5.   hardship_dpd
     6.   total_pymnt
     7.   total_rec_late_fee
     8.   loan_status
     9.   hardship_payoff_balance_amount
    10.   last_pymnt_amnt
```
Diagnosis: not applicable (this probe expects an empty result)

### `none-branch-staff` — none

> which loan officer approved this application

Expected (0): nothing

Why: Nothing records who at the lender handled a loan.

Scores — keyword r@10   --   MRR   --   | sem-band r@10   --   MRR   --   | sem-topk r@10   --   MRR   --  

Keyword returned:
```
    (empty)
```
sem-topk returned:
```
     1.   member_id
     2.   issue_d
     3.   application_type_Individual
     4.   application_type_Joint App
     5.   debt_settlement_flag
     6.   out_prncp
     7.   total_rec_int
     8.   total_rec_prncp
     9.   hardship_type
    10.   funded_amnt
```
Diagnosis: not applicable (this probe expects an empty result)

### `none-vehicle` — none

> what make and model of car does the borrower drive

Expected (0): nothing

Why: purpose_car records a loan purpose, not a vehicle; no column describes a car.

Scores — keyword r@10   --   MRR   --   | sem-band r@10   --   MRR   --   | sem-topk r@10   --   MRR   --  

Keyword returned:
```
    (empty)
```
sem-topk returned:
```
     1.   member_id
     2.   purpose_car
     3.   mort_acc
     4.   annual_inc
     5.   home_ownership_MORTGAGE
     6.   total_cu_tl
     7.   debt_settlement_flag
     8.   home_ownership_OWN
     9.   home_ownership_RENT
    10.   loan_amnt
```
Diagnosis: not applicable (this probe expects an empty result)

### `none-social` — none

> how many children does the applicant have

Expected (0): nothing

Why: No household or dependant information exists anywhere in the dictionary.

Scores — keyword r@10   --   MRR   --   | sem-band r@10   --   MRR   --   | sem-topk r@10   --   MRR   --  

Keyword returned:
```
    (empty)
```
sem-topk returned:
```
     1.   num_il_tl
     2.   hardship_length
     3.   inq_last_12m
     4.   num_sats
     5.   inq_fi
     6.   num_op_rev_tl
     7.   num_bc_tl
     8.   num_rev_accts
     9.   num_actv_bc_tl
    10.   num_bc_sats
```
Diagnosis: not applicable (this probe expects an empty result)

## The ceiling

`_MAX_DISTANCE` is still 0.45 and I did not change it. Its job has narrowed: with the cap bounding result size, the ceiling is now the only thing that can make tier 2 return nothing at all.

**The `none` family still fails: 0 of 4 returned empty.** This is not a tuning artefact and no value of either constant fixes it. Nearest neighbours always exist. A fluent English question about something the dictionary does not hold still lands close to something — `issue_d` at 0.240 for a question about the weather, `member_id` at 0.312 for a question about which loan officer approved the application — because those distances measure how alike two pieces of English are, not whether one answers the other. Setting the ceiling low enough to empty those results would also empty legitimate paraphrase queries that sit at comparable distances, which trades a cosmetic failure for a real one.

The numbers say the ceiling cannot be made to do this job at any value. Across the probe set the closest hit for a `none` query falls between 0.240 and 0.352; for every other probe it falls between 0.183 and 0.436. The two ranges are interleaved, not separated. A ceiling tight enough to empty the closest `none` query — 0.240 — would also empty 15 of the 24 probes that do have an answer. There is no threshold that keeps the second group and drops the first, which is why 0.45 stays: it still cuts genuine gibberish, which sits past 0.47, and with the cap bounding size it costs nothing to leave it loose.

So the retriever no longer pretends to solve it. The published schema for `search_data_dictionary` now tells the agent that beyond literal name matching the results are the entries closest by meaning, that a result may be unrelated to what was asked, and that presence in the list is not on its own evidence that the dictionary holds an answer. That is the honest description of what the tool does, and it puts the judgement where it can actually be made.

## What this says, and what it does not

Overall recall@10 runs 0.305 for keyword, 0.504 for the band, 0.551 for the cap; MRR 0.375, 0.748, 0.757. The averages are carried almost entirely by the two families where substring matching scores zero, and the two semantic configurations are much closer to each other than either is to keyword — which is the point. Changing the cutoff moved a handful of probes; changing from substring to embeddings moved two whole families.

Where it helps, clearly: paraphrase. Substring matching returns an empty list for all 7 probes, because the question does not reuse the dictionary's vocabulary. The current configuration reaches recall@10 0.412 with MRR 0.762, so the first hit is usually right. That is the case the change was made for and it is the one result here that is not hedged.

Where it stays weak: conceptual, recall@10 0.287, MRR 0.476. The cap tidied the symptom — `con-derived` and `con-time-anchor` no longer return 87 and 78 entries — without touching the cause. Questions with a concrete anchor still do well: how absence is recorded finds the missingness flags, whether anything is left to pay finds the outstanding-principal columns. Questions about where a value comes from or when it is set still do badly, because a one-sentence definition does not encode provenance and an embedding of it cannot recover what the sentence never said. That is the honest ceiling of description-only embeddings, and it is not a cutoff question. Provenance lives in the `populated` and `source` fields, which are deliberately not embedded — for `populated`, because embedding it would break the include_populated ablation. This gap is the price of that decision, and worth stating in those terms rather than as a shortfall to be tuned away.

Where it does not help: identifier, where all three backends score identically because tier 1 is unchanged and does the work. That row is a check that nothing regressed, not a discovery.

What this eval does not measure. The probes and the expected sets are mine, and the current cutoff was chosen after seeing how these probes scored, so the sem-topk column is not an out-of-sample result; 7 probes are marked uncertain, 5 of them in the conceptual family, which is also the weakest row and so deserves the least confidence. It measures retrieval in isolation, not whether an agent asks better questions or reaches better conclusions with it, which is what actually matters and needs a full run. It says nothing about the canary variant, since one index serves both. It does not test the fallback under the conditions that trigger it. And with 28 probes a single probe is worth three to four points of a family average, so none of these numbers should be read past one decimal place.

