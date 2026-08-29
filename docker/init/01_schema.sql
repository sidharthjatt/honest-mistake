-- Schema for the Layer 2 data-dictionary retrieval index.
-- Runs once, when the data directory is first created.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS dict_entries (
    feature      text PRIMARY KEY,
    description  text NOT NULL,

    -- INVARIANT — populated is stored so it can be returned alongside a
    -- hit, and for no other purpose. It must never be indexed, never be
    -- turned into a tsvector, never appear in a WHERE clause, and never
    -- contribute to retrieval scoring in any form.
    --
    -- The reason is an evaluation one, not a performance one. The tool
    -- layer's include_populated=False switch drops this field from the
    -- results after retrieval. That is only honest if populated played no
    -- part in producing those results: if it had shaped which rows came
    -- back, or their order, then suppressing the text afterwards would
    -- leave its influence in the ranking and the ablation would measure
    -- something other than what it claims to.
    --
    -- Enforced structurally by there being no index on this column, and
    -- by the embedding being built from description alone. Adding an
    -- index here, or a filter, breaks the ablation silently.
    populated    text NOT NULL,

    source       text NOT NULL,

    -- BAAI/bge-small-en-v1.5, L2-normalised, queried by cosine distance.
    embedding    vector(384) NOT NULL
);

-- No HNSW or IVFFlat index on embedding. That is deliberate.
--
-- The table holds 224 rows. An approximate-nearest-neighbour index is a
-- trade: it buys sublinear search and pays for it in recall. At this size
-- there is nothing to buy — a sequential scan over 224 vectors of 384
-- dimensions is well under a millisecond, and it is exact. An ANN index
-- would be slower to build, no faster to query, and would introduce a
-- recall parameter that could quietly change which entries the agent
-- sees between runs.
--
-- Revisit only if the dictionary grows by two orders of magnitude.
