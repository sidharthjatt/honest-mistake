"""eval_retrieval.py — keyword vs semantic retrieval over the dictionary.

Offline. No Anthropic API, no model training, nothing written outside
outputs/agent_cache/RETRIEVAL_EVAL.md.

Runs every probe in scripts/retrieval_probes.py through two backends:

    keyword    the substring implementation search() used before the
               index existed: case-insensitive substring over feature
               names, then over descriptions, in dictionary order.
    semantic   the current two-tier path: the same name matching, then
               pgvector nearest neighbours over description embeddings,
               subject to the relevance cutoffs in data_dictionary.

Both are scored the same way, on the same expected sets, with the same
metrics. The cutoffs are read, never adjusted.

Run:
    .venv/bin/python scripts/eval_retrieval.py
"""

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agent import data_dictionary as DD  # noqa: E402
from scripts.retrieval_probes import FAMILIES, PROBES  # noqa: E402

BACKENDS = ("keyword", "band", "topk")
LABEL = {"keyword": "keyword", "band": "sem-band", "topk": "sem-topk"}

OUT_MD = PROJECT_ROOT / "outputs" / "agent_cache" / "RETRIEVAL_EVAL.md"


# ----------------------------------------------------------------------
# Backends
# ----------------------------------------------------------------------
def keyword_search(query: str) -> list[str]:
    """The pre-index implementation, reproduced exactly."""
    q = query.strip().lower()
    if not q:
        return []
    name_hits, desc_hits = [], []
    for feature, entry in DD.FEATURE_DOCS.items():
        if q in feature.lower():
            name_hits.append(feature)
        elif q in entry["description"].lower():
            desc_hits.append(feature)
    return name_hits + desc_hits


def semantic_topk_search(query: str) -> list[str]:
    """The current two-tier path, through the real search()."""
    return [h["feature"] for h in DD.search(query)]


# The relative band that tier 2 used before it was replaced by a fixed
# cap. Reproduced here rather than kept as a frozen table of numbers, for
# the same reason keyword_search is reproduced rather than remembered: a
# comparison column that cannot be recomputed stops being checkable.
BAND_MARGIN = 0.05


def semantic_band_search(query: str) -> list[str]:
    """Tier 1 unchanged, then the old band: everything within BAND_MARGIN
    of the closest hit, subject to the same absolute ceiling."""
    from agent import retrieval

    q = query.strip()
    if not q:
        return []
    names = [f for f in DD.FEATURE_DOCS if q.lower() in f.lower()]
    seen = set(names)
    hits = retrieval.search_descriptions(q, len(DD.FEATURE_DOCS))
    if not hits:
        return names
    best = hits[0]["distance"]
    if best > DD._MAX_DISTANCE:
        return names
    cutoff = min(best + BAND_MARGIN, DD._MAX_DISTANCE)
    band = [h["feature"] for h in hits
            if h["distance"] <= cutoff and h["feature"] not in seen]
    return names + band


# ----------------------------------------------------------------------
# Metrics
# ----------------------------------------------------------------------
def recall_at(hits: list[str], expected: set[str], k: int) -> float | None:
    if not expected:
        return None
    top = hits[:k]
    return len(expected & set(top)) / len(expected)


def reciprocal_rank(hits: list[str], expected: set[str]) -> float | None:
    if not expected:
        return None
    for i, h in enumerate(hits, start=1):
        if h in expected:
            return 1.0 / i
    return 0.0


def mean(values: list[float]) -> float | None:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def fmt(v) -> str:
    return "  --  " if v is None else f"{v:.3f}"


# ----------------------------------------------------------------------
# Run
# ----------------------------------------------------------------------
def run() -> tuple[list[dict], dict]:
    results = []
    for p in PROBES:
        kw = keyword_search(p["query"])
        band = semantic_band_search(p["query"])
        topk = semantic_topk_search(p["query"])
        row = {
            "probe": p,
            "keyword": kw,
            "band": band,
            "topk": topk,
        }
        for name, hits in (("keyword", kw), ("band", band), ("topk", topk)):
            row[f"{name}_r5"] = recall_at(hits, p["expected"], 5)
            row[f"{name}_r10"] = recall_at(hits, p["expected"], 10)
            row[f"{name}_mrr"] = reciprocal_rank(hits, p["expected"])
            row[f"{name}_empty"] = len(hits) == 0
        results.append(row)
    return results, summarise(results)


def summarise(results: list[dict]) -> dict:
    out = {}
    for fam in FAMILIES + ["ALL"]:
        rows = [r for r in results
                if fam == "ALL" or r["probe"]["family"] == fam]
        entry = {"n": len(rows)}
        for b in BACKENDS:
            entry[b] = {
                "r5": mean([r[f"{b}_r5"] for r in rows]),
                "r10": mean([r[f"{b}_r10"] for r in rows]),
                "mrr": mean([r[f"{b}_mrr"] for r in rows]),
                "empty": sum(1 for r in rows if r[f"{b}_empty"]),
            }
        out[fam] = entry
    return out


def regressions(results: list[dict]) -> list[dict]:
    """Probes where semantic scored below keyword on recall@10 or MRR."""
    out = []
    for r in results:
        if not r["probe"]["expected"]:
            # a `none` probe regresses if semantic returned something and
            # keyword did not
            if r["topk"] and not r["keyword"]:
                out.append(r)
            continue
        worse_r10 = (r["topk_r10"] or 0) < (r["keyword_r10"] or 0)
        worse_mrr = (r["topk_mrr"] or 0) < (r["keyword_mrr"] or 0)
        if worse_r10 or worse_mrr:
            out.append(r)
    return out


def cutoff_diagnosis(r: dict) -> str:
    """Distinguish a ceiling failure from a rank-cap or ranking failure."""
    from agent import retrieval

    expected = r["probe"]["expected"]
    if not expected:
        return "not applicable (this probe expects an empty result)"
    try:
        raw = retrieval.search_descriptions(r["probe"]["query"],
                                            len(DD.FEATURE_DOCS))
    except Exception:
        return "could not be diagnosed (the index was unreachable)"
    if not raw:
        return "could not be diagnosed (the index returned nothing)"
    dist = {h["feature"]: h["distance"] for h in raw}
    best = raw[0]["distance"]
    returned = set(r["topk"])
    missed = [f for f in expected if f not in returned]
    if not missed:
        return ("ranking: every expected entry was returned, but below the "
                "rank the metric counts")
    if best > DD._MAX_DISTANCE:
        return (f"ceiling: the closest entry in the whole index sat at "
                f"{best:.3f}, beyond the ceiling of {DD._MAX_DISTANCE}, so "
                f"tier 2 returned nothing")
    under = [f for f in missed if dist.get(f, 9) <= DD._MAX_DISTANCE]
    if under:
        nearest = min(dist.get(f, 9) for f in under)
        return (f"rank cap: {len(under)} expected entries sat inside the "
                f"{DD._MAX_DISTANCE} ceiling (nearest at {nearest:.3f}) but "
                f"outside the nearest {DD._TOP_K}")
    nearest_missed = min((dist.get(f, 9) for f in missed), default=9)
    return (f"ceiling: the nearest missed entry sat at {nearest_missed:.3f}, "
            f"beyond the ceiling of {DD._MAX_DISTANCE}")


# ----------------------------------------------------------------------
# Report
# ----------------------------------------------------------------------
def table(summary: dict) -> str:
    cols = ["family", "n"]
    for m in ("r@5", "r@10", "MRR", "empty"):
        for b in BACKENDS:
            cols.append(f"{LABEL[b]} {m}")
    widths = [11, 2] + [max(len(c), 6) for c in cols[2:]]
    head = "| " + " | ".join(c.ljust(w) if i == 0 else c.rjust(w)
                             for i, (c, w) in enumerate(zip(cols, widths))) + " |"
    sep = "|" + "|".join("-" * (w + 2) for w in widths) + "|"
    lines = [head, sep]
    for fam in FAMILIES + ["ALL"]:
        e = summary[fam]
        cells = [fam.ljust(widths[0]), str(e["n"]).rjust(widths[1])]
        i = 2
        for m in ("r5", "r10", "mrr"):
            for b in BACKENDS:
                cells.append(fmt(e[b][m]).rjust(widths[i])); i += 1
        for b in BACKENDS:
            cells.append(str(e[b]["empty"]).rjust(widths[i])); i += 1
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def hit_list(hits: list[str], expected: set[str], n: int = 10) -> str:
    if not hits:
        return "    (empty)"
    out = []
    for i, h in enumerate(hits[:n], start=1):
        mark = "*" if h in expected else " "
        out.append(f"    {i:>2}. {mark} {h}")
    if len(hits) > n:
        out.append(f"    ... {len(hits) - n} more")
    return "\n".join(out)


def moved(results: list[dict]) -> tuple[list, list]:
    """Probes whose score changed between the band and the cap."""
    up, down = [], []
    for r in results:
        if not r["probe"]["expected"]:
            if len(r["topk"]) != len(r["band"]):
                (up if len(r["topk"]) < len(r["band"]) else down).append(r)
            continue
        db = (r["topk_r10"] or 0) - (r["band_r10"] or 0)
        dm = (r["topk_mrr"] or 0) - (r["band_mrr"] or 0)
        if db > 0 or (db == 0 and dm > 0):
            up.append(r)
        elif db < 0 or dm < 0:
            down.append(r)
    return up, down


def write_report(results: list[dict], summary: dict, regs: list[dict],
                 seconds: float) -> None:
    n_unc = sum(1 for p in PROBES if p["uncertain"])
    n_unc_con = sum(1 for p in PROBES
                    if p["uncertain"] and p["family"] == "conceptual")
    lines = []
    A = lines.append

    A("# Retrieval evaluation — keyword vs semantic")
    A("")
    A("## Method")
    A("")
    A(f"{len(PROBES)} probes, written as questions an auditor would ask "
      f"rather than as rearranged descriptions, are run through three "
      f"backends. **keyword** is the substring matching `search()` used "
      f"before the vector index existed. **sem-band** is the first "
      f"semantic configuration: name matching, then every neighbour within "
      f"{BAND_MARGIN} cosine distance of the closest hit, under an absolute "
      f"ceiling of {DD._MAX_DISTANCE}. **sem-topk** is the current "
      f"configuration: name matching, then the nearest {DD._TOP_K} "
      f"neighbours under the same ceiling, with no relative band. All three "
      f"see the same query and are scored against the same expected sets, "
      f"which have not been touched since before either semantic "
      f"configuration was measured. Expected sets are my judgement about "
      f"what answers each question, with a one-line reason in "
      f"`scripts/retrieval_probes.py`; {n_unc} probes are marked uncertain "
      f"there and are included rather than quietly dropped. recall@k is the "
      f"share of the expected set in the first k results, MRR the "
      f"reciprocal rank of the first correct hit. The four `none` probes "
      f"have empty expected sets, so only the empty count carries "
      f"information for them. Run in {seconds:.1f}s.")
    A("")
    A("## Results by family")
    A("")
    A("```")
    A(table(summary))
    A("```")
    A("")

    A("## What changed, and that it was changed after seeing the numbers")
    A("")
    A("The relative band was replaced with a fixed cap of "
      f"{DD._TOP_K} after reading the first eval. That is tuning, and it "
      f"should be read as tuning: the constant was not chosen from a "
      f"held-out set, it was chosen after looking at these exact probes. "
      f"The probe set was frozen before the change and not touched since, "
      f"which limits the damage but does not undo it. Anything in the "
      f"sem-topk column is a fit to 28 probes I wrote myself.")
    A("")
    A(f"What changed, precisely: tier 2 was `everything within "
      f"{BAND_MARGIN} of the closest hit, under a {DD._MAX_DISTANCE} "
      f"ceiling`, and is now `the nearest {DD._TOP_K}, under the same "
      f"{DD._MAX_DISTANCE} ceiling`. The band is gone; the ceiling is "
      f"unchanged. The reason is not that the band scored badly on average "
      f"but that it failed in two opposite directions at once — closing at "
      f"0.285 on `lex-fico` and letting 87 entries through on "
      f"`con-derived` — so no value of the constant fixed both. A fixed cap "
      f"is a different kind of statement: that in a corpus of "
      f"{len(DD.FEATURE_DOCS)} one-sentence entries a useful answer is "
      f"never 87 items long, whatever the distances happen to be.")
    A("")
    up, down = moved(results)
    A(f"**Probes that improved ({len(up)}):**")
    A("")
    if not up:
        A("None.")
    else:
        for r in up:
            pr = r["probe"]
            if pr["expected"]:
                A(f"- `{pr['id']}` ({pr['family']}) — r@10 "
                  f"{fmt(r['band_r10'])} to {fmt(r['topk_r10'])}, MRR "
                  f"{fmt(r['band_mrr'])} to {fmt(r['topk_mrr'])}; "
                  f"{len(r['band'])} results became {len(r['topk'])}.")
            else:
                A(f"- `{pr['id']}` ({pr['family']}) — {len(r['band'])} "
                  f"results became {len(r['topk'])}; expected none.")
    A("")
    A(f"**Probes that got worse ({len(down)}):**")
    A("")
    if not down:
        A("None.")
    else:
        for r in down:
            pr = r["probe"]
            if pr["expected"]:
                A(f"- `{pr['id']}` ({pr['family']}) — r@10 "
                  f"{fmt(r['band_r10'])} to {fmt(r['topk_r10'])}, MRR "
                  f"{fmt(r['band_mrr'])} to {fmt(r['topk_mrr'])}; "
                  f"{len(r['band'])} results became {len(r['topk'])}.")
            else:
                A(f"- `{pr['id']}` ({pr['family']}) — {len(r['band'])} "
                  f"results became {len(r['topk'])}; expected none.")
    A("")

    A("## Where sem-topk did worse than keyword")
    A("")
    if not regs:
        A("No probe scored lower under the current configuration than under "
          "substring matching on either recall@10 or MRR.")
    else:
        A(f"{len(regs)} of {len(PROBES)} probes, quoted in full with both "
          f"result lists, marked `*` where a result is in the expected set.")
        A("")
        for r in regs:
            pr = r["probe"]
            A(f"### `{pr['id']}` — {pr['family']}"
              + ("  (marked uncertain)" if pr["uncertain"] else ""))
            A("")
            A(f"> {pr['query']}")
            A("")
            A(f"Expected ({len(pr['expected'])}): "
              + (", ".join(f"`{f}`" for f in sorted(pr['expected'])[:12])
                 + (" ..." if len(pr['expected']) > 12 else "")
                 if pr["expected"] else "nothing"))
            A("")
            A(f"Why: {pr['why']}")
            A("")
            A(f"Scores — keyword r@10 {fmt(r['keyword_r10'])} MRR "
              f"{fmt(r['keyword_mrr'])} | sem-band r@10 {fmt(r['band_r10'])} "
              f"MRR {fmt(r['band_mrr'])} | sem-topk r@10 "
              f"{fmt(r['topk_r10'])} MRR {fmt(r['topk_mrr'])}")
            A("")
            A("Keyword returned:")
            A("```")
            A(hit_list(r["keyword"], pr["expected"]))
            A("```")
            A("sem-topk returned:")
            A("```")
            A(hit_list(r["topk"], pr["expected"]))
            A("```")
            A(f"Diagnosis: {cutoff_diagnosis(r)}")
            A("")

    A("## The ceiling")
    A("")
    none_rows = [r for r in results if r["probe"]["family"] == "none"]
    empty_none = [r for r in none_rows if not r["topk"]]
    A(f"`_MAX_DISTANCE` is still {DD._MAX_DISTANCE} and I did not change "
      f"it. Its job has narrowed: with the cap bounding result size, the "
      f"ceiling is now the only thing that can make tier 2 return nothing "
      f"at all.")
    A("")
    A(f"**The `none` family still fails: {len(empty_none)} of "
      f"{len(none_rows)} returned empty.** This is not a tuning artefact "
      f"and no value of either constant fixes it. Nearest neighbours always "
      f"exist. A fluent English question about something the dictionary "
      f"does not hold still lands close to something — `issue_d` at 0.240 "
      f"for a question about the weather, `member_id` at 0.312 for a "
      f"question about which loan officer approved the application — "
      f"because those distances measure how alike two pieces of English "
      f"are, not whether one answers the other. Setting the ceiling low "
      f"enough to empty those results would also empty legitimate "
      f"paraphrase queries that sit at comparable distances, which trades a "
      f"cosmetic failure for a real one.")
    A("")
    from agent import retrieval as _R
    bests = {}
    for pr in PROBES:
        try:
            bests[pr["id"]] = (pr["family"],
                               _R.search_descriptions(pr["query"], 1)[0]["distance"])
        except Exception:
            pass
    if bests:
        nb = [d for f, d in bests.values() if f == "none"]
        rb = [d for f, d in bests.values() if f != "none"]
        if nb and rb:
            killed = sum(1 for d in rb if d >= min(nb))
            A(f"The numbers say the ceiling cannot be made to do this job at "
              f"any value. Across the probe set the closest hit for a `none` "
              f"query falls between {min(nb):.3f} and {max(nb):.3f}; for "
              f"every other probe it falls between {min(rb):.3f} and "
              f"{max(rb):.3f}. The two ranges are interleaved, not "
              f"separated. A ceiling tight enough to empty the closest "
              f"`none` query — {min(nb):.3f} — would also empty "
              f"{killed} of the {len(rb)} probes that do have an answer. "
              f"There is no threshold that keeps the second group and drops "
              f"the first, which is why {DD._MAX_DISTANCE} stays: it still "
              f"cuts genuine gibberish, which sits past 0.47, and with the "
              f"cap bounding size it costs nothing to leave it loose.")
            A("")
    A("So the retriever no longer pretends to solve it. The published "
      "schema for `search_data_dictionary` now tells the agent that beyond "
      "literal name matching the results are the entries closest by "
      "meaning, that a result may be unrelated to what was asked, and that "
      "presence in the list is not on its own evidence that the dictionary "
      "holds an answer. That is the honest description of what the tool "
      "does, and it puts the judgement where it can actually be made.")
    A("")

    A("## What this says, and what it does not")
    A("")
    t, b, k = (summary["ALL"]["topk"], summary["ALL"]["band"],
               summary["ALL"]["keyword"])
    A(f"Overall recall@10 runs {fmt(k['r10'])} for keyword, "
      f"{fmt(b['r10'])} for the band, {fmt(t['r10'])} for the cap; MRR "
      f"{fmt(k['mrr'])}, {fmt(b['mrr'])}, {fmt(t['mrr'])}. The averages are "
      f"carried almost entirely by the two families where substring "
      f"matching scores zero, and the two semantic configurations are much "
      f"closer to each other than either is to keyword — which is the "
      f"point. Changing the cutoff moved a handful of probes; changing from "
      f"substring to embeddings moved two whole families.")
    A("")
    ps = summary["paraphrase"]
    A(f"Where it helps, clearly: paraphrase. Substring matching returns an "
      f"empty list for all {ps['n']} probes, because the question does not "
      f"reuse the dictionary's vocabulary. The current configuration "
      f"reaches recall@10 {fmt(ps['topk']['r10'])} with MRR "
      f"{fmt(ps['topk']['mrr'])}, so the first hit is usually right. That "
      f"is the case the change was made for and it is the one result here "
      f"that is not hedged.")
    A("")
    cs = summary["conceptual"]
    A(f"Where it stays weak: conceptual, recall@10 "
      f"{fmt(cs['topk']['r10'])}, MRR {fmt(cs['topk']['mrr'])}. The cap "
      f"tidied the symptom — `con-derived` and `con-time-anchor` no longer "
      f"return 87 and 78 entries — without touching the cause. Questions "
      f"with a concrete anchor still do well: how absence is recorded finds "
      f"the missingness flags, whether anything is left to pay finds the "
      f"outstanding-principal columns. Questions about where a value comes "
      f"from or when it is set still do badly, because a one-sentence "
      f"definition does not encode provenance and an embedding of it "
      f"cannot recover what the sentence never said. That is the honest "
      f"ceiling of description-only embeddings, and it is not a cutoff "
      f"question. Provenance lives in the `populated` and `source` fields, "
      f"which are deliberately not embedded — for `populated`, because "
      f"embedding it would break the include_populated ablation. This gap "
      f"is the price of that decision, and worth stating in those terms "
      f"rather than as a shortfall to be tuned away.")
    A("")
    A(f"Where it does not help: identifier, where all three backends score "
      f"identically because tier 1 is unchanged and does the work. That row "
      f"is a check that nothing regressed, not a discovery.")
    A("")
    A(f"What this eval does not measure. The probes and the expected sets "
      f"are mine, and the current cutoff was chosen after seeing how these "
      f"probes scored, so the sem-topk column is not an out-of-sample "
      f"result; {n_unc} probes are marked uncertain, {n_unc_con} of them in "
      f"the conceptual family, which is also the weakest row and so "
      f"deserves the least confidence. It measures retrieval in isolation, "
      f"not whether an agent asks better questions or reaches better "
      f"conclusions with it, which is what actually matters and needs a "
      f"full run. It says nothing about the canary variant, since one index "
      f"serves both. It does not test the fallback under the conditions "
      f"that trigger it. And with {len(PROBES)} probes a single probe is "
      f"worth three to four points of a family average, so none of these "
      f"numbers should be read past one decimal place.")
    A("")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    t0 = time.perf_counter()
    print("=" * 74)
    print("eval_retrieval — keyword vs sem-band vs sem-topk")
    print("=" * 74)
    print(f"  probes: {len(PROBES)}  "
          f"(uncertain: {sum(1 for p in PROBES if p['uncertain'])})")
    print(f"  tier 2 now: nearest {DD._TOP_K} under a "
          f"{DD._MAX_DISTANCE} ceiling, no relative band")

    results, summary = run()

    served = DD.retrieval_paths_used()
    print(f"  semantic backends served by: {sorted(served)}")
    if "pgvector" not in served:
        print("  FAILED: the vector index did not serve the semantic "
              "columns. Nothing written.")
        return 1

    print()
    print(table(summary))
    print()

    up, down = moved(results)
    print(f"  probes that improved band -> topk: {len(up)}")
    for r in up:
        print(f"    {r['probe']['id']:<24} {r['probe']['family']:<11} "
              f"r@10 {fmt(r['band_r10'])} -> {fmt(r['topk_r10'])}   "
              f"n {len(r['band']):>3} -> {len(r['topk']):>3}")
    print(f"  probes that got worse band -> topk: {len(down)}")
    for r in down:
        print(f"    {r['probe']['id']:<24} {r['probe']['family']:<11} "
              f"r@10 {fmt(r['band_r10'])} -> {fmt(r['topk_r10'])}   "
              f"n {len(r['band']):>3} -> {len(r['topk']):>3}")

    regs = regressions(results)
    print()
    print(f"  probes where sem-topk scored below keyword: {len(regs)}")
    for r in regs:
        print(f"    {r['probe']['id']:<24} {r['probe']['family']}")

    print()
    print("  per-probe detail (r@10 / MRR / n):")
    for r in results:
        p = r["probe"]
        print(f"    {p['id']:<24} {p['family']:<11} "
              f"kw {fmt(r['keyword_r10'])}/{fmt(r['keyword_mrr'])}/"
              f"{len(r['keyword']):<3}  "
              f"band {fmt(r['band_r10'])}/{fmt(r['band_mrr'])}/"
              f"{len(r['band']):<3}  "
              f"topk {fmt(r['topk_r10'])}/{fmt(r['topk_mrr'])}/"
              f"{len(r['topk']):<3}"
              + ("  (uncertain)" if p["uncertain"] else ""))

    secs = time.perf_counter() - t0
    write_report(results, summary, regs, secs)
    print()
    print("  report written: outputs/agent_cache/RETRIEVAL_EVAL.md")
    print(f"  wall time: {secs:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
