"""retrieval.py — Honest Mistake, Layer 2 semantic retrieval.

The pgvector client behind data_dictionary.search()'s second tier. Given a
query string it returns dictionary entries ranked by cosine distance
between the query embedding and the entry's *description* embedding.

WHAT IS EMBEDDED, AND WHAT IS NOT
---------------------------------
Only `description`. Not the feature name, not `populated`, not `source`.

`populated` is the one that matters. The tool layer can be run with
include_populated=False, which drops that field from every result after
retrieval. That ablation is only honest if `populated` played no part in
producing the results in the first place — if it had shaped which entries
came back, or their order, then removing the text afterwards would leave
its influence sitting in the ranking, and the experiment would measure
something other than what it claims to. So `populated` is stored, returned,
and otherwise untouched: it is not embedded, not indexed, and never
appears in a WHERE clause or an ORDER BY.

CONNECTION DETAILS
------------------
Read from the environment only: PG_HOST, PG_PORT, PG_DB, PG_USER,
PG_PASSWORD. No function here accepts a host, a port, a DSN, a table
name, or any SQL fragment as an argument, so nothing a caller passes —
and therefore nothing the agent passes — can influence where the query
goes or what it says. The query itself is a bound parameter, never
interpolated.

The connection and the embedding model are both process-wide singletons.
A run makes many small queries; opening a connection or reloading a
110 MB model per query would dominate the cost of the retrieval.
"""

import os
import threading

_MODEL_NAME = "BAAI/bge-small-en-v1.5"
# Pinned to a commit, not a branch. The index on disk was built with this
# revision; a silent upstream change would leave stored vectors and query
# vectors in different spaces, which shows up as quietly worse retrieval
# rather than as an error.
_MODEL_REVISION = "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
_EMBED_DIM = 384

# bge asks for this prefix on the query side only; documents are embedded
# bare. Retrieval quality drops measurably without it.
_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

_TABLE = "dict_entries"

RETRIEVAL_BACKEND = "pgvector-bge-small-en-v1.5"

_conn = None
_model = None
_lock = threading.Lock()



class RetrievalUnavailable(RuntimeError):
    """Postgres could not be reached, or the index could not be queried.

    Raised instead of returning partial results, so a caller can decide to
    fall back deliberately rather than silently serving a short list.
    """


def _dsn() -> str:
    """Build the connection string from the environment. Never from an
    argument — see the module docstring."""
    from dotenv import load_dotenv

    load_dotenv()
    missing = [k for k in ("PG_HOST", "PG_PORT", "PG_DB", "PG_USER",
                           "PG_PASSWORD") if not os.environ.get(k)]
    if missing:
        raise RetrievalUnavailable(
            f"database settings are not configured: {', '.join(missing)}")
    return (f"host={os.environ['PG_HOST']} port={os.environ['PG_PORT']} "
            f"dbname={os.environ['PG_DB']} user={os.environ['PG_USER']} "
            f"password={os.environ['PG_PASSWORD']} connect_timeout=5")


def get_model():
    """Load the embedding model once per process and keep it."""
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer

                _model = SentenceTransformer(
                    _MODEL_NAME, revision=_MODEL_REVISION)
    return _model


def get_connection():
    """One connection per process, reopened if it has been closed."""
    global _conn
    with _lock:
        if _conn is not None and not _conn.closed:
            return _conn
        try:
            import psycopg
            from pgvector.psycopg import register_vector

            conn = psycopg.connect(_dsn(), autocommit=True)
            register_vector(conn)
        except RetrievalUnavailable:
            raise
        except Exception as exc:
            raise RetrievalUnavailable(
                f"could not connect to the retrieval database: "
                f"{type(exc).__name__}") from None
        _conn = conn
        return _conn


def close_connection() -> None:
    """Drop the cached connection. Used by tests and by the build script."""
    global _conn
    with _lock:
        if _conn is not None and not _conn.closed:
            try:
                _conn.close()
            except Exception:
                pass
        _conn = None


def embed_query(text: str):
    """Embed one query string, L2-normalised, with the bge query prefix."""
    model = get_model()
    return model.encode([_QUERY_PREFIX + text],
                        normalize_embeddings=True,
                        show_progress_bar=False)[0]


def embed_documents(texts: list[str]):
    """Embed description texts, L2-normalised, with no prefix."""
    model = get_model()
    return model.encode(list(texts), normalize_embeddings=True,
                        batch_size=64, show_progress_bar=False)


def search_descriptions(query: str, limit: int) -> list[dict]:
    """Top `limit` entries by cosine distance over description embeddings.

    Returns dicts with feature, description, populated, source, and the
    distance, nearest first. Raises RetrievalUnavailable if the database
    cannot serve the query; never returns a partial list.
    """
    if not isinstance(query, str) or not query.strip():
        return []
    try:
        n = int(limit)
    except (TypeError, ValueError):
        n = 0
    if n < 1:
        return []

    conn = get_connection()
    vec = embed_query(query.strip())
    # Every value is bound. No identifier, no operator, and no fragment of
    # this statement comes from a caller.
    sql = (f"SELECT feature, description, populated, source, "
           f"embedding <=> %s AS distance "
           f"FROM {_TABLE} ORDER BY distance ASC LIMIT %s")
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (vec, n))
            rows = cur.fetchall()
    except Exception as exc:
        close_connection()
        raise RetrievalUnavailable(
            f"the retrieval query could not be completed: "
            f"{type(exc).__name__}") from None

    if not rows:
        # A populated table always returns min(limit, table size) rows
        # before any relevance cutoff is applied, so an empty result means
        # an empty index. Returning [] here would let tier 2 silently
        # contribute nothing while the run stamped itself as pgvector-served.
        raise RetrievalUnavailable("the retrieval index is empty")

    return [
        {"feature": r[0], "description": r[1], "populated": r[2],
         "source": r[3], "distance": float(r[4])}
        for r in rows
    ]


def index_stats() -> dict:
    """Row count and vector dimension. For preflight checks, not for tools."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT count(*), count(embedding) FROM {_TABLE}")
            total, non_null = cur.fetchone()
            cur.execute(
                f"SELECT vector_dims(embedding) FROM {_TABLE} LIMIT 1")
            row = cur.fetchone()
    except Exception as exc:
        close_connection()
        raise RetrievalUnavailable(
            f"the index could not be inspected: {type(exc).__name__}") from None
    return {
        "rows": int(total),
        "non_null_embeddings": int(non_null),
        "dimension": int(row[0]) if row else None,
        "model": _MODEL_NAME,
        "revision": _MODEL_REVISION,
        "expected_dimension": _EMBED_DIM,
    }
