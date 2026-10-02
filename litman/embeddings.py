"""Semantic search with local text embeddings.

Two indexes in <data>/embeddings/, both from a small local model
(BAAI/bge-small-en-v1.5, 384 dimensions, via fastembed/ONNX). Nothing leaves the
machine apart from the one-off model download.

  summaries  one vector per paper: title + summary.json (topic + summary)
  chunks     ~220-word overlapping passages of extracted_text.txt, with the
             reference list and publisher boilerplate stripped

Updates are incremental: only items missing from an index are embedded, and
rows for items that no longer exist (renamed, deleted, made confidential) are
dropped. Confidential items are never read (get_items(shareable=True)).

Requires `fastembed` and `numpy` (``uv tool install ... --with fastembed``).
They are imported lazily, so the rest of litman works without them.

Embeddings retrieve by topic and are blind to direction and negation ("X
strengthens Y" and "X weakens Y" embed alike): results are passages to read,
not answers. Hybrid search adds exact-term matching for names, acronyms and
case studies, which embeddings handle poorly.
"""
import json
import math
import os
import re
import time
from logging import getLogger

logger = getLogger('litman.embeddings')

MODEL = 'BAAI/bge-small-en-v1.5'
CHUNK, STRIDE = 220, 180          # words per passage, step between passages
DEFAULT_THREADS = 4               # one process; more saturated a 10-core laptop

_embedder = None


def available():
    try:
        import fastembed  # noqa: F401
        import numpy  # noqa: F401
        return True
    except ImportError:
        return False


def _np():
    import numpy as np
    return np


class Embedder:
    """Wraps the model. Tests replace embed_docs/embed_query with fakes."""
    def __init__(self, threads=DEFAULT_THREADS):
        from fastembed import TextEmbedding
        cache = os.path.expanduser('~/.cache/fastembed')
        self.model = TextEmbedding(MODEL, cache_dir=cache, threads=threads)

    def embed_docs(self, texts):
        return _unit(list(self.model.embed(texts, batch_size=64)))

    def embed_query(self, q):
        # bge expects an instruction prefix on queries, which query_embed adds
        return _unit(list(self.model.query_embed(q)))[0]


def embedder(threads=DEFAULT_THREADS):
    global _embedder
    if _embedder is None:
        _embedder = Embedder(threads)
    return _embedder


def _unit(m):
    np = _np()
    m = np.asarray(m, dtype=np.float32)
    return m / np.linalg.norm(m, axis=-1, keepdims=True)


# --- text --------------------------------------------------------------------

REF_HEAD = re.compile(r'^\s*(?:\d+\.?\s*)?(references|references and notes|bibliography|'
                      r'literature cited|references cited)\s*$', re.I | re.M)
NOISE = re.compile(r'^.*(downloaded from|terms of use|all rights reserved|creative commons|'
                   r'https?://doi\.org|©|copyright).*$', re.I | re.M)


def item_title(item):
    """The bib title; for an item with no ref.bib, its summary's topic line."""
    t = ''
    if item.has_bib:
        try:
            t = item.bib_entry().fields.get('title', '')
        except Exception:
            pass
    if not t and item.has_summary:
        t = '[no bib] ' + item.read_summary().get('topic', '')
    return re.sub(r'[{}]', '', t)


def summary_text(item):
    s = item.read_summary()
    return f"{item_title(item)}. {s.get('topic', '')} {s.get('summary', '')}"


def body_text(text):
    """Extracted text minus the reference list and publisher boilerplate."""
    heads = [m.start() for m in REF_HEAD.finditer(text) if m.start() > 0.4 * len(text)]
    if heads:
        text = text[:heads[-1]]
    text = NOISE.sub(' ', text)
    text = re.sub(r'-\n(?=[a-z])', '', text)       # rejoin hyphenated line breaks
    return re.sub(r'\s+', ' ', text).strip()


def chunks(text):
    w = text.split()
    for i in range(0, max(len(w) - CHUNK + STRIDE, 1), STRIDE):
        piece = w[i:i + CHUNK]
        if len(piece) >= 40:
            yield ' '.join(piece)


# --- storage -----------------------------------------------------------------

def _dir(litman):
    d = litman.data_path('embeddings')
    os.makedirs(d, exist_ok=True)
    return d


def load(litman, name):
    """(keys, vectors, texts or None); empty if the index does not exist."""
    np = _np()
    d = _dir(litman)
    meta_fn = os.path.join(d, f'{name}.json')
    if not os.path.exists(meta_fn):
        return [], np.zeros((0, 384), np.float32), [] if name == 'chunks' else None
    meta = json.load(open(meta_fn))
    if meta.get('model') != MODEL:
        logger.warning(f'{name} index built with {meta.get("model")}: rebuilding')
        return [], np.zeros((0, 384), np.float32), [] if name == 'chunks' else None
    vecs = np.load(os.path.join(d, f'{name}.npy')).astype(np.float32)
    texts = None
    if name == 'chunks':
        texts = json.load(open(os.path.join(d, 'chunks.txt.json')))
    return meta['keys'], vecs, texts


def save(litman, name, keys, vecs, texts=None):
    np = _np()
    d = _dir(litman)
    np.save(os.path.join(d, f'{name}.npy'), np.asarray(vecs).astype(np.float16))
    json.dump({'model': MODEL, 'built': time.strftime('%Y-%m-%d %H:%M'), 'keys': keys},
              open(os.path.join(d, f'{name}.json'), 'w'))
    if texts is not None:
        json.dump(texts, open(os.path.join(d, 'chunks.txt.json'), 'w'))


# --- building ------------------------------------------------------------------

def update(litman, chunks_too=False, names=None, threads=DEFAULT_THREADS, log=print):
    """Bring the indexes up to date. names: only consider these items (still
    drops rows for items that no longer exist or are confidential)."""
    np = _np()
    shareable = {it.name: it for it in litman.get_items(shareable=True)}
    wanted = shareable if names is None else {n: shareable[n] for n in names if n in shareable}

    keys, vecs, _ = load(litman, 'summaries')
    keep = [i for i, k in enumerate(keys) if k in shareable]
    keys, vecs = [keys[i] for i in keep], vecs[keep]
    new = [it for n, it in wanted.items() if it.has_summary and n not in set(keys)]
    if new:
        log(f'embeddings: {len(new)} new summaries')
        vecs = np.vstack([vecs, embedder(threads).embed_docs([summary_text(it) for it in new])])
        keys += [it.name for it in new]
    if new or len(keep) != len(load(litman, 'summaries')[0]):
        save(litman, 'summaries', keys, vecs)

    if not chunks_too:
        return
    ckeys, cvecs, ctexts = load(litman, 'chunks')
    keep = [i for i, k in enumerate(ckeys) if k in shareable]
    dropped = len(ckeys) - len(keep)
    ckeys, cvecs, ctexts = [ckeys[i] for i in keep], cvecs[keep], [ctexts[i] for i in keep]
    have = set(ckeys)
    new = [it for n, it in wanted.items() if it.has_extracted_text and n not in have]
    t0 = time.time()
    for n, it in enumerate(new, 1):
        pieces = list(chunks(body_text(it.extracted_text() or '')))
        if pieces:
            cvecs = np.vstack([cvecs, embedder(threads).embed_docs(pieces)])
            ckeys += [it.name] * len(pieces)
            ctexts += pieces
        if n % 25 == 0 or n == len(new):
            log(f'  passages: {n}/{len(new)} papers, {time.time() - t0:.0f} s')
    if new or dropped:
        save(litman, 'chunks', ckeys, cvecs, ctexts)
        log(f'embeddings: passages for {len(new)} new papers; {dropped} stale rows dropped')


# --- searching -----------------------------------------------------------------

STOP = set('the a an of in on and or for to with by from at as is are was were be this that '
           'these those it its into than then their between which what how why when'.split())


def _terms(query):
    """(required phrases in quotes, other words)."""
    phrases = [p.lower() for p in re.findall(r'"([^"]+)"', query)]
    rest = re.sub(r'"[^"]+"', ' ', query.lower())
    words = [w for w in re.findall(r"[a-z0-9][a-z0-9\-]+", rest) if w not in STOP]
    return phrases, words


def lexical_scores(texts, query):
    """BM25-like score per text; texts lacking a quoted phrase score -inf."""
    np = _np()
    phrases, words = _terms(query)
    low = [t.lower() for t in texts]
    n = len(low)
    s = np.zeros(n, np.float32)
    for w in set(words) | set(phrases):
        pat = re.compile(r'(?<![a-z0-9])' + re.escape(w) + r'(?![a-z0-9])')
        tf = np.array([len(pat.findall(t)) for t in low], np.float32)
        df = int((tf > 0).sum())
        if df:
            s += math.log(1 + n / df) * tf / (tf + 1.2)
    for p in phrases:
        s[np.array([p not in t for t in low])] = -np.inf
    return s


def rrf(*scores, k=60):
    """Reciprocal-rank fusion of several score arrays (higher is better)."""
    np = _np()
    out = np.zeros(len(scores[0]), np.float32)
    for sc in scores:
        ranks = np.empty(len(sc), np.int64)
        ranks[np.argsort(-sc)] = np.arange(len(sc))
        out += 1.0 / (k + ranks + 1)
        out[~np.isfinite(sc)] = -np.inf
    return out


def search_summaries(litman, query, k=10):
    keys, vecs, _ = load(litman, 'summaries')
    if not keys:
        return []
    s = vecs @ embedder().embed_query(query)
    return [(keys[i], float(s[i])) for i in _np().argsort(-s)[:k]]


def search_passages(litman, query, k=10, hybrid=False):
    """Best passage per paper: [(key, score, passage)]."""
    np = _np()
    keys, vecs, texts = load(litman, 'chunks')
    if not keys:
        return []
    s = vecs @ embedder().embed_query(query)
    if hybrid or '"' in query:
        s = rrf(s, lexical_scores(texts, query))
    best = {}
    for i in np.argsort(-s):
        if not np.isfinite(s[i]) or len(best) >= k:
            break
        best.setdefault(keys[i], i)
    return [(key, float(s[i]), texts[i]) for key, i in best.items()]


def similar(litman, name, k=10):
    keys, vecs, _ = load(litman, 'summaries')
    if name not in keys:
        return None
    i0 = keys.index(name)
    s = vecs @ vecs[i0]
    s[i0] = -1
    return [(keys[i], float(s[i])) for i in _np().argsort(-s)[:k]]
