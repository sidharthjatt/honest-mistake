"""plot_layer2_eval.py — the two figures in LAYER2_EVAL.md.

Every number is read from the run records under outputs/agent_runs/ and
scored through agent.eval_canary.evaluate(). Nothing is typed in here. If
a record is missing or unscoreable the script says so and stops rather
than filling the gap.

Run:
    .venv/bin/python scripts/plot_layer2_eval.py
"""

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agent.eval_canary import evaluate  # noqa: E402

RUNS = PROJECT_ROOT / "outputs" / "agent_runs"
FIGS = PROJECT_ROOT / "outputs" / "figures"

INK = "#1a1a1a"
GREY = "#8c8c8c"
GREYS = ["#d9d9d9", "#c4c4c4", "#afafaf", "#9a9a9a", "#858585", "#707070"]
ACCENT = "#c1440e"

plt.rcParams.update({
    "font.size": 9,
    "axes.edgecolor": INK,
    "axes.labelcolor": INK,
    "text.color": INK,
    "xtick.color": INK,
    "ytick.color": INK,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
})


def load_scored_v2_runs() -> list[dict]:
    """Every REAL, usable, v2.0 run, in a stable order."""
    out = []
    for man in sorted(RUNS.glob("*/manifest.json")):
        m = json.loads(man.read_text())
        if m.get("mode") != "REAL" or m.get("tool_layer_version") != "2.0":
            continue
        if not m.get("is_usable"):
            continue
        res = evaluate(man.parent, quiet=True)
        if res is None:
            raise SystemExit(
                f"Cannot plot: {man.parent.name} is a usable REAL run but "
                f"eval_canary refused to score it. Nothing written.")
        calls = json.loads((man.parent / "tool_call_log.json").read_text())["calls"]
        tools = {}
        for c in calls:
            tools[c["tool"]] = tools.get(c["tool"], 0) + 1
        cache = "canary" if m["cache_dir"].endswith("canary") else "honest"
        out.append({
            "dir": man.parent.name,
            "cache": cache,
            "populated": m["dictionary_populated_field"],
            "scopes": m["coverage_scopes"],
            "tp": res["score"]["true_positive_count"],
            "fp": res["score"]["false_positive_count"],
            "tools": tools,
            "calls": m["tool_calls"],
        })
    # canary first, then honest; within each, populated on before off,
    # full scopes before split-only.
    order = {"canary": 0, "honest": 1}
    out.sort(key=lambda r: (order[r["cache"]],
                            r["populated"] != "included",
                            r["scopes"] != "all"))
    return out


def label(r: dict) -> str:
    pop = "populated on" if r["populated"] == "included" else "populated off"
    sc = "all scopes" if r["scopes"] == "all" else "split only"
    return f"{r['cache']}\n{pop}\n{sc}"


def figure_one(runs: list[dict]) -> Path:
    fig, ax = plt.subplots(figsize=(6.4, 3.4), dpi=150)
    x = range(len(runs))
    w = 0.36
    tp = [r["tp"] for r in runs]
    fp = [r["fp"] for r in runs]

    ax.bar([i - w / 2 for i in x], tp, w, color=GREY,
           edgecolor=INK, linewidth=0.6, label="caught (true positive)")
    ax.bar([i + w / 2 for i in x], fp, w, color=ACCENT,
           edgecolor=INK, linewidth=0.6, label="false positive")

    for i, (a, b) in enumerate(zip(tp, fp)):
        ax.text(i - w / 2, a + 0.06, str(a), ha="center", va="bottom", fontsize=9)
        ax.text(i + w / 2, b + 0.06, str(b), ha="center", va="bottom", fontsize=9)

    ax.set_xticks(list(x))
    ax.set_xticklabels([label(r) for r in runs], fontsize=8)
    ax.set_ylabel("columns flagged")
    ax.set_ylim(0, max(max(tp), max(fp)) + 0.8)
    ax.set_yticks(range(0, max(max(tp), max(fp)) + 1))
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    ax.set_title("Caught, and wrongly flagged, by configuration",
                 fontsize=10, loc="left", pad=10)
    # The honest cache has nothing planted, so zero caught is the correct
    # reading there, not a miss. Say so on the figure.
    honest = [i for i, r in enumerate(runs) if r["cache"] == "honest"]
    if honest:
        ax.annotate("nothing planted in the honest cache",
                    xy=(sum(honest) / len(honest), -0.44),
                    xycoords=("data", "axes fraction"),
                    ha="center", fontsize=7.5, color=GREY, annotation_clip=False)
    fig.tight_layout(rect=(0, 0.09, 1, 1))
    p = FIGS / "layer2_false_positives.png"
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return p


def figure_two(runs: list[dict]) -> Path:
    names = sorted({t for r in runs for t in r["tools"]})
    # the two the figure is about go on the ends, in their own colours
    highlight = {"get_feature_coverage": ACCENT, "lookup_feature": INK}
    rest = [n for n in names if n not in highlight]
    order = ["get_feature_coverage"] + rest + ["lookup_feature"]
    colour = {n: highlight.get(n, GREYS[i % len(GREYS)])
              for i, n in enumerate(order)}

    fig, ax = plt.subplots(figsize=(7.2, 4.2), dpi=150)
    y = range(len(runs))
    left = [0] * len(runs)
    for n in order:
        vals = [r["tools"].get(n, 0) for r in runs]
        ax.barh(list(y), vals, left=left, height=0.6, color=colour[n],
                edgecolor="white", linewidth=0.7, label=n)
        for i, v in enumerate(vals):
            if n in highlight and v > 0:
                ax.text(left[i] + v / 2, i, str(v), ha="center", va="center",
                        fontsize=8, color="white")
        left = [a + b for a, b in zip(left, vals)]

    for i, r in enumerate(runs):
        if r["tools"].get("lookup_feature", 0) == 0:
            ax.text(left[i] + 0.8, i, "0 lookup_feature", va="center",
                    fontsize=7.5, color=INK)

    ax.set_yticks(list(y))
    ax.set_yticklabels([label(r).replace("\n", " / ") for r in runs], fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("tool calls")
    ax.set_xlim(0, max(left) + 8)
    ax.legend(frameon=False, fontsize=7, ncol=3,
              loc="upper center", bbox_to_anchor=(0.42, -0.20),
              handlelength=1.3, columnspacing=1.2)
    ax.set_title("Where the calls went", fontsize=10, loc="left", pad=10)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    p = FIGS / "layer2_tool_calls.png"
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return p


def main() -> int:
    runs = load_scored_v2_runs()
    if len(runs) != 4:
        raise SystemExit(
            f"Expected 4 scored v2.0 runs on disk, found {len(runs)}: "
            f"{[r['dir'] for r in runs]}. Nothing written.")
    FIGS.mkdir(parents=True, exist_ok=True)
    print("scored v2.0 runs, in figure order:")
    for r in runs:
        print(f"  {r['cache']:<7} populated={r['populated']:<11} "
              f"scopes={r['scopes']:<10} TP={r['tp']} FP={r['fp']} "
              f"calls={r['calls']}")
    p1 = figure_one(runs)
    p2 = figure_two(runs)
    print(f"\nwrote {p1.relative_to(PROJECT_ROOT)}")
    print(f"wrote {p2.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
