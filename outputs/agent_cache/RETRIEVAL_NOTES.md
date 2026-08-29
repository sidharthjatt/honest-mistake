# Dictionary retrieval index

The second tier of `search_data_dictionary` is a semantic lookup over the
data dictionary, held in a local Postgres with pgvector. This file records
how the index was built, so a rebuild produces the same thing.

## Model

`BAAI/bge-small-en-v1.5`, pinned to revision
`5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`. 384-dimensional, embeddings L2-normalised
at encode time, queried by cosine distance. The revision is a commit
rather than a branch on purpose: stored vectors and query vectors have to
come from the same model, and an upstream change to the tag would break
that without raising anything — retrieval would just get quietly worse.

Queries carry the prefix bge expects
("Represent this sentence for searching relevant passages: ");
descriptions are embedded bare. That asymmetry is what the model was
trained for.

## What is embedded

The `description` field of each of the 224 dictionary entries, and
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

`source` has four distinct values across 224 entries. Embedding it
would pull entries toward four cluster centroids and tell you nothing you
could not get from the returned field.

## Why there is no ANN index

There are 224 rows. An HNSW or IVFFlat index trades exactness for
sublinear search, and at this size there is nothing to buy: a sequential
scan over 224 vectors of 384 dimensions runs in well under a
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
