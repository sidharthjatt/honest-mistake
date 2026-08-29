"""build_dict_index.py — Honest Mistake, Layer 2.

Embed the data dictionary and load it into the pgvector table that backs
data_dictionary.search()'s semantic tier.

WHAT IS EMBEDDED
----------------
The `description` field, and nothing else. Not the feature name, not
`populated`, not `source`.

The reason is `populated`. The tool layer can run with
include_populated=False, which drops that field from results after
retrieval, and the point of that ablation is to remove lifecycle-timing
information from what the agent can use. Folding `populated` into the
embedded text would leave its influence inside the ranking after the text
itself was suppressed — the agent would still be steered by it while no
longer being able to read it, and the experiment would quietly stop
measuring what it claims to. Feature names are held out for a different
reason: they are matched exactly in search()'s first tier, and embedding
identifier-shaped tokens alongside prose mostly adds noise.

One table serves both the honest and canary variants. The dictionary is
the same text in both; only the model artefacts differ.

Idempotent — upserts on the feature primary key, so re-running replaces
vectors in place and never duplicates a row.

Run:
    .venv/bin/python scripts/build_dict_index.py
"""

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agent import retrieval  # noqa: E402
from agent.data_dictionary import FEATURE_DOCS  # noqa: E402

NOTES_MD = PROJECT_ROOT / "outputs" / "agent_cache" / "RETRIEVAL_NOTES.md"


def write_notes(n_entries: int, dim: int) -> None:
    text = f"""# Dictionary retrieval index

The second tier of `search_data_dictionary` is a semantic lookup over the
data dictionary, held in a local Postgres with pgvector. This file records
how the index was built, so a rebuild produces the same thing.

## Model

`{retrieval._MODEL_NAME}`, pinned to revision
`{retrieval._MODEL_REVISION}`. {dim}-dimensional, embeddings L2-normalised
at encode time, queried by cosine distance. The revision is a commit
rather than a branch on purpose: stored vectors and query vectors have to
come from the same model, and an upstream change to the tag would break
that without raising anything — retrieval would just get quietly worse.

Queries carry the prefix bge expects
("Represent this sentence for searching relevant passages: ");
descriptions are embedded bare. That asymmetry is what the model was
trained for.

## What is embedded

The `description` field of each of the {n_entries} dictionary entries, and
nothing else.

`populated` is stored in the table and returned alongside a hit, but it is
not embedded, not indexed, and never appears in a filter or an ordering.
The tool layer can be run with include_populated=False, which drops that
field from the results after retrieval; that ablation only means anything
if `populated` had no hand in choosing or ordering those results. If it
were part of the embedded text, suppressing it afterwards would leave its
influence in the ranking and the experiment would be measuring something
other than what it says on the label. The schema keeps that honest
structurally — there is no index on the column and no code path that reads
it before results are chosen.

Feature names are held out for a plainer reason. They are matched exactly
in the first tier of `search()`, which still does case-insensitive
substring matching over names in dictionary order, so a query like
`mths_since` returns the whole family the way it always did. Mixing
identifier tokens into prose embeddings would blur the descriptions
without improving that.

`source` has four distinct values across {n_entries} entries. Embedding it
would pull entries toward four cluster centroids and tell you nothing you
could not get from the returned field.

## Why there is no ANN index

There are {n_entries} rows. An HNSW or IVFFlat index trades exactness for
sublinear search, and at this size there is nothing to buy: a sequential
scan over {n_entries} vectors of {dim} dimensions runs in well under a
millisecond and returns the true nearest neighbours every time. An
approximate index would be slower to build, no faster to query, and would
add a recall parameter capable of changing which entries the agent sees
from one run to the next. Worth revisiting if the dictionary ever grows a
hundredfold.

## Rebuilding

Bring the database up, then run the builder:

    docker compose -f docker/docker-compose.yml --env-file .env up -d --wait
    .venv/bin/python scripts/build_dict_index.py

The builder upserts on the feature primary key, so running it twice is
harmless. Connection settings come from `.env` — `PG_HOST`, `PG_PORT`,
`PG_DB`, `PG_USER`, `PG_PASSWORD`. The host port is 5433, deliberately not
5432, because another Postgres runs on the default port on this machine
and the two must not be confused.

If the database is unreachable, `search()` falls back to the substring
matching it used before this index existed. The fallback is recorded in
the run's configuration stamp, so a run served by it is never mistaken for
a run served by the index.
"""
    NOTES_MD.parent.mkdir(parents=True, exist_ok=True)
    NOTES_MD.write_text(text, encoding="utf-8")


def main() -> int:
    t0 = time.perf_counter()
    print("=" * 70)
    print("build_dict_index — data dictionary -> pgvector")
    print("=" * 70)

    features = list(FEATURE_DOCS)
    descriptions = [FEATURE_DOCS[f]["description"] for f in features]
    print(f"  entries in FEATURE_DOCS : {len(features)}")

    print(f"  loading {retrieval._MODEL_NAME} @ {retrieval._MODEL_REVISION[:12]} ...")
    t_model = time.perf_counter()
    retrieval.get_model()
    print(f"  model ready             : {time.perf_counter() - t_model:.1f}s")

    t_embed = time.perf_counter()
    vectors = retrieval.embed_documents(descriptions)
    dim = int(vectors.shape[1])
    print(f"  embedded                : {vectors.shape[0]} descriptions, "
          f"dim {dim} ({time.perf_counter() - t_embed:.1f}s)")

    if dim != retrieval._EMBED_DIM:
        print(f"  FAILED: model returned dimension {dim}, the table expects "
              f"{retrieval._EMBED_DIM}. Nothing written.")
        return 1

    try:
        conn = retrieval.get_connection()
    except retrieval.RetrievalUnavailable as exc:
        print(f"  FAILED: {exc}")
        return 1

    rows = [
        (f, FEATURE_DOCS[f]["description"], FEATURE_DOCS[f]["populated"],
         FEATURE_DOCS[f]["source"], v)
        for f, v in zip(features, vectors)
    ]
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO dict_entries "
            "(feature, description, populated, source, embedding) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (feature) DO UPDATE SET "
            "description = EXCLUDED.description, "
            "populated = EXCLUDED.populated, "
            "source = EXCLUDED.source, "
            "embedding = EXCLUDED.embedding",
            rows)

    stats = retrieval.index_stats()
    write_notes(len(features), dim)

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  entries embedded  : {len(features)}")
    print(f"  rows in table     : {stats['rows']}")
    print(f"  non-null vectors  : {stats['non_null_embeddings']}")
    print(f"  dimension         : {stats['dimension']}")
    print(f"  model             : {stats['model']}")
    print(f"  revision          : {stats['revision']}")
    print(f"  notes             : outputs/agent_cache/RETRIEVAL_NOTES.md")
    print(f"  wall time         : {time.perf_counter() - t0:.1f}s")
    retrieval.close_connection()
    return 0


if __name__ == "__main__":
    sys.exit(main())
