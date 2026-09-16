"""Export the artefacts the eight tools read, as static JSON for the browser.

Writes JSON under docs/data/tools/ and nothing else. It makes no network
request and needs no API key.

The eight tools are read-only lookups over precomputed tables. Seven files
carry everything they read:

- dictionary.json: all 224 documented columns. Serves lookup_feature and
  tier 1 of search_data_dictionary.
- shap_global.json: the ranking. Serves get_shap_ranking.
- shap_detail.json: the per-feature SHAP distribution summary. Serves
  get_feature_shap_detail.
- ablation.json, coverage.json, univariate.json, correlations.json: the
  four remaining tables, one tool each.

shap_detail.json is the one file that is not a table copy. In Python the
tool computes twenty summary statistics per feature over 30,000 sampled
rows of shap_values.parquet, which is 30 MB and has no business in a
browser. Those statistics are a pure function of the column, so they are
computed once here by calling the tool itself and storing what it
returned. The numbers are the tool's own output, never re-derived.

Both variants are exported. The recorded runs used two caches: the clean
180-feature model, and the 181-feature one with `recoveries` planted. The
canary is the thing the benchmark is about, so a browser that can only
serve the clean variant could never reproduce the finding.

Nothing is filtered here. The two ablation switches, include_populated and
include_vintage_scopes, drop the dictionary's `populated` field and the
per-vintage coverage scopes at serve time. Applying them during export
would bake one configuration into the data and make the other
unreachable, so the full tables ship and the switches stay where they are.

    .venv/bin/python -m scripts.export_tool_artefacts
"""

from __future__ import annotations

import gzip
import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent.data_dictionary import FEATURE_DOCS  # noqa: E402
from agent.prompts import build_system_prompt  # noqa: E402
from agent.tools import TOOL_SCHEMAS, ToolLayer  # noqa: E402

OUT = ROOT / "docs" / "data" / "tools"

VARIANTS = {
    "layer1": ROOT / "outputs" / "agent_cache",
    "canary": ROOT / "outputs" / "agent_cache_canary",
}

# One table per tool, read exactly as the Python tool reads it.
TABLES = {
    "shap_global": ("shap_global.csv", "get_shap_ranking"),
    "ablation": ("ablation_cache.csv", "get_ablation_result"),
    "coverage": ("coverage_profile.csv", "get_feature_coverage"),
    "univariate": ("univariate_assoc.csv", "get_feature_target_association"),
    "correlations": ("correlation_topk.csv", "get_correlated_features"),
}

SOURCE_PATHS = ["agent/data_dictionary.py", "agent/tools.py",
                "outputs/agent_cache", "outputs/agent_cache_canary"]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()


def _write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, indent=1, ensure_ascii=False, allow_nan=False) + "\n"
    path.write_text(text)


def _records(csv_path: Path) -> list[dict]:
    """A CSV as JSON records, with pandas' NaN turned into a real null.

    json.dumps writes NaN as the bare token NaN, which no JSON parser
    accepts. allow_nan=False in _write turns a missed one into an error
    rather than a file the browser cannot read.
    """
    df = pd.read_csv(csv_path)
    return [
        {k: (None if pd.isna(v) else v.item() if hasattr(v, "item") else v)
         for k, v in row.items()}
        for row in df.to_dict(orient="records")
    ]


def _shap_detail(cache_dir: Path) -> dict:
    """Every feature's SHAP summary, as the tool itself returns it."""
    tools = ToolLayer(cache_dir=cache_dir)
    ranking = tools.get_shap_ranking(top_n=10 ** 6)
    if "ranking" not in ranking:
        raise SystemExit(f"No SHAP ranking under {cache_dir}; nothing to export.")

    detail = {}
    for row in ranking["ranking"]:
        feature = row["feature"]
        result = tools.get_feature_shap_detail(feature)
        if not result.get("found"):
            raise SystemExit(
                f"{feature} is in the ranking but has no SHAP detail. "
                f"The two artefacts disagree; stopping rather than "
                f"exporting a gap.")
        result.pop("found", None)
        result.pop("feature", None)
        detail[feature] = result
    return detail


def _prompt_template() -> dict:
    """The system prompt as a template, not as one rendered instance.

    prompts.py takes the ceilings as arguments so the prompt can never
    state a limit different from the one being enforced. Exporting a
    rendered prompt would throw that away and pin one pair of ceilings
    into the data. So it is rendered once with sentinel values, each of
    which is checked to appear exactly once, and they are swapped for
    placeholders the caller fills at run time.
    """
    sentinels = {
        "max_turns": (424241, "{max_turns}"),
        "max_tool_calls": (424242, "{max_tool_calls}"),
        "n_features": (424243, "{n_features}"),
    }
    # The two AUCs are read from a tuning record and rendered to four
    # places, so they need a sentinel record rather than a sentinel
    # argument.
    sentinel_record = {"test_roc_auc": 0.4241, "val_roc_auc": 0.4242}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(sentinel_record, fh)
        record = Path(fh.name)
    try:
        text = build_system_prompt(
            max_turns=sentinels["max_turns"][0],
            max_tool_calls=sentinels["max_tool_calls"][0],
            n_features=sentinels["n_features"][0],
            tuning_record=record,
        )
    finally:
        record.unlink()

    sentinels["test_roc_auc"] = ("0.4241", "{test_roc_auc}")
    sentinels["val_roc_auc"] = ("0.4242", "{val_roc_auc}")

    for field, (value, placeholder) in sentinels.items():
        found = text.count(str(value))
        if found != 1:
            raise SystemExit(
                f"Sentinel for {field} appears {found} times in the rendered "
                f"prompt; expected exactly once. The prompt has changed shape "
                f"and the template cannot be built safely.")
        text = text.replace(str(value), placeholder)

    figures = {}
    for variant, name in (("layer1", "best_params.json"),
                          ("canary", "best_params_canary.json")):
        path = ROOT / "outputs" / "models" / name
        if not path.is_file():
            raise SystemExit(f"Missing tuning record: {path}")
        rec = json.loads(path.read_text())
        figures[variant] = {
            "test_roc_auc": float(rec["test_roc_auc"]),
            "val_roc_auc": float(rec["val_roc_auc"]),
        }

    # The figures are rendered to four places in the prompt, so the
    # already-formatted strings ship alongside the raw values and the
    # caller never has to reimplement the formatting.
    for variant in figures:
        figures[variant]["test_roc_auc_text"] = f"{figures[variant]['test_roc_auc']:.4f}"
        figures[variant]["val_roc_auc_text"] = f"{figures[variant]['val_roc_auc']:.4f}"

    return {
        "template": text,
        "placeholders": ["{max_turns}", "{max_tool_calls}", "{n_features}",
                         "{test_roc_auc}", "{val_roc_auc}"],
        "figures_by_variant": figures,
        "note": "Rendered from agent/prompts.py with sentinel ceilings, then "
                "the sentinels swapped for placeholders. Fill all five before "
                "sending; the ceilings in the prompt must match the ones the "
                "loop enforces.",
    }


def main() -> None:
    if not FEATURE_DOCS:
        raise SystemExit("The data dictionary is empty; nothing to export.")

    for name, path in VARIANTS.items():
        if not path.is_dir():
            raise SystemExit(f"Cache for variant '{name}' is missing: {path}")

    _write(OUT / "dictionary.json",
           [{"feature": f, **entry} for f, entry in FEATURE_DOCS.items()])
    _write(OUT / "system_prompt.json", _prompt_template())
    # Exported rather than transcribed: the descriptions interpolate
    # constants from tools.py, and a hand-copy would drift from them
    # silently the first time one changed.
    _write(OUT / "tool_schemas.json", TOOL_SCHEMAS)

    per_variant = {}
    for variant, cache_dir in VARIANTS.items():
        for stem, (filename, _tool) in TABLES.items():
            csv_path = cache_dir / filename
            if not csv_path.is_file():
                raise SystemExit(f"Missing artefact: {csv_path}")
            _write(OUT / variant / f"{stem}.json", _records(csv_path))

        detail = _shap_detail(cache_dir)
        _write(OUT / variant / "shap_detail.json", detail)
        per_variant[variant] = len(detail)

    files = sorted(p for p in OUT.rglob("*.json") if p.name != "manifest.json")
    manifest = {
        "exported_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "exported_from_commit": _git("rev-parse", "HEAD"),
        "uncommitted_changes_in_source_paths": [
            line for line in _git("status", "--porcelain", "--", *SOURCE_PATHS).splitlines()
            if line
        ],
        "export_script_sha256": _sha256(Path(__file__)),
        "source_sha256": {
            p: _sha256(ROOT / p) for p in SOURCE_PATHS if (ROOT / p).is_file()
        } | {
            f"{v}/{fn}": _sha256(d / fn)
            for v, d in VARIANTS.items() for fn, _ in TABLES.values()
        },
        "variants": {
            "layer1": {"cache": "outputs/agent_cache",
                       "features": per_variant["layer1"],
                       "canary": None},
            "canary": {"cache": "outputs/agent_cache_canary",
                       "features": per_variant["canary"],
                       "canary": "recoveries"},
        },
        "dictionary_entries": len(FEATURE_DOCS),
        "tool_schemas_note":
            "tool_schemas.json is agent.tools.TOOL_SCHEMAS exported verbatim, "
            "so the definitions the browser sends are the ones the recorded "
            "runs sent.",
        "system_prompt_note":
            "system_prompt.json carries the prompt as a template with five "
            "placeholders, not as a rendered instance, so the ceilings it "
            "states are always the ceilings the caller is enforcing.",
        "tool_sources": {tool: f"<variant>/{stem}.json"
                         for stem, (_f, tool) in TABLES.items()}
                        | {"get_feature_shap_detail": "<variant>/shap_detail.json",
                           "lookup_feature": "dictionary.json",
                           "search_data_dictionary": "dictionary.json"},
        "shap_detail_note":
            "Computed once by calling ToolLayer.get_feature_shap_detail over "
            "shap_values.parquet (30 MB, not shipped). The values are the "
            "tool's own output, unchanged.",
        "retrieval_note":
            "search_data_dictionary has two tiers. Tier 1, substring over "
            "column names, is carried in full. Tier 2 is semantic retrieval "
            "over description embeddings (pgvector, bge-small-en-v1.5) and is "
            "not carried: no embeddings and no model are exported. A browser "
            "port serves the substring-over-descriptions fallback that "
            "agent/data_dictionary.py already defines, so its retrieval "
            "differs from the recorded runs.",
        "switches_note":
            "include_populated and include_vintage_scopes are not applied "
            "here. The dictionary ships with its `populated` field and "
            "coverage ships all six scopes; a caller drops them at serve time.",
        "files": [str(p.relative_to(OUT)) for p in files],
    }
    _write(OUT / "manifest.json", manifest)

    print(f"{'file':44} {'bytes':>10} {'gzipped':>9}")
    print("-" * 65)
    raw = gz = 0
    for path in sorted(OUT.rglob("*.json")):
        data = path.read_bytes()
        z = len(gzip.compress(data, 9))
        raw += len(data)
        gz += z
        print(f"{str(path.relative_to(OUT)):44} {len(data):>10,} {z:>9,}")
    print("-" * 65)
    print(f"{'TOTAL':44} {raw:>10,} {gz:>9,}")


if __name__ == "__main__":
    main()
