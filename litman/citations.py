"""Build the internal citation network of the corpus.

Each item is resolved on two services:
  - Semantic Scholar for citation counts (citationCount, influentialCitationCount);
  - OpenAlex for reference lists (`referenced_works`). S2 cannot be used for
    these: some publishers (e.g. AMS) elide reference lists from S2, but they
    deposit them in Crossref, which OpenAlex ingests.

Internal edges (item A cites item B, both in the corpus) are the union of what
the two sources report. Communities are detected with Louvain and labelled from
the members' summary.json keywords. Outputs (in the litman data dir):

  citation_graph.json    - nodes + edges, with in-degree and PageRank per node
  citation_report.md     - rankings: internal in-degree, PageRank, global counts
  citation_network.html  - self-contained interactive graph (canvas, no deps)

API responses are cached in .citation_cache.json in the data dir, so reruns
cost no API calls. Set S2_API_KEY for a higher Semantic Scholar rate limit.
"""
import json
import os
import random
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import date
from logging import getLogger

import requests

logger = getLogger('litman.citations')

S2_API = 'https://api.semanticscholar.org/graph/v1'
S2_FIELDS = 'paperId,title,year,citationCount,influentialCitationCount'
S2_INTERVAL = 1.1  # unauthenticated S2 shares a pool; stay polite, back off on 429
OA_API = 'https://api.openalex.org'
OA_FIELDS = 'id,doi,title,referenced_works,cited_by_count'
OA_INTERVAL = 0.15  # polite pool allows ~10 req/s

CACHE_BASENAME = '.citation_cache.json'
TEMPLATE_FN = os.path.join(os.path.dirname(__file__), 'templates',
                           'citation_network.html')

_session = requests.Session()
if os.environ.get('S2_API_KEY'):
    _session.headers['x-api-key'] = os.environ['S2_API_KEY']
_last_request = {}


def _api_call(method, url, interval=S2_INTERVAL, **kwargs):
    """Rate-limited request (per API host) with backoff on 429/5xx."""
    host = url.split('/')[2]
    for attempt in range(6):
        wait = interval - (time.time() - _last_request.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        _last_request[host] = time.time()
        try:
            r = _session.request(method, url, timeout=60, **kwargs)
        except requests.RequestException as e:
            print(f'  transient error ({e}), retrying...', file=sys.stderr)
            time.sleep(2 ** attempt)
            continue
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(2 ** attempt * 2)
            continue
        return r
    raise RuntimeError(f'giving up on {url} after retries')


def _bib_fields(item):
    """(doi, title) from the item's ref.bib, or (None, None)."""
    entry = item.bib_entry()
    if entry is None:
        return None, None
    doi = entry.fields.get('doi') or None
    title = entry.fields.get('title') or None
    if title:
        title = re.sub(r'[{}]', '', title).strip()
    return doi, title


def scan_corpus(litman):
    """{name: {'doi', 'title'}} for every item in the collection."""
    return {item.name: dict(zip(('doi', 'title'), _bib_fields(item)))
            for item in litman.get_items()}


# --- Semantic Scholar: citation counts ---

def s2_batch_lookup(ids):
    """POST /paper/batch for up to 500 ids; returns list aligned with ids (None = miss)."""
    out = []
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        r = _api_call('POST', f'{S2_API}/paper/batch',
                      params={'fields': S2_FIELDS}, json={'ids': chunk})
        r.raise_for_status()
        out.extend(r.json())
    return out


def s2_title_match(title):
    r = _api_call('GET', f'{S2_API}/paper/search/match',
                  params={'query': title, 'fields': S2_FIELDS})
    if r.status_code == 404:
        return None
    r.raise_for_status()
    data = r.json().get('data') or []
    return data[0] if data else None


def _s2_record(paper, via):
    return {
        'paperId': paper['paperId'],
        's2_title': paper.get('title'),
        'year': paper.get('year'),
        'citationCount': paper.get('citationCount'),
        'influentialCitationCount': paper.get('influentialCitationCount'),
        'via': via,
    }


def resolve_s2(papers, cache, save):
    resolved = cache.setdefault('resolved', {})
    unresolved = cache.setdefault('unresolved', {})
    todo = {k: v for k, v in papers.items() if k not in resolved and k not in unresolved}

    doi_keys = [k for k, v in todo.items() if v['doi']]
    if doi_keys:
        print(f'S2: resolving {len(doi_keys)} items by DOI (batch)...')
        results = s2_batch_lookup([f'DOI:{papers[k]["doi"]}' for k in doi_keys])
        for key, paper in zip(doi_keys, results):
            if paper and paper.get('paperId'):
                resolved[key] = _s2_record(paper, 'doi')
            # misses fall through to title match

    title_keys = [k for k, v in todo.items() if k not in resolved and v['title']]
    if title_keys:
        print(f'S2: resolving {len(title_keys)} items by title match '
              f'(~{len(title_keys) * S2_INTERVAL / 60:.0f} min)...')
    for n, key in enumerate(title_keys, 1):
        paper = s2_title_match(papers[key]['title'])
        if paper and paper.get('paperId'):
            resolved[key] = _s2_record(paper, 'title')
        else:
            unresolved[key] = 'no title match'
        if n % 25 == 0:
            print(f'  {n}/{len(title_keys)}', flush=True)
            save()

    for key in todo:
        if key not in resolved and key not in unresolved:
            reason = 'doi lookup miss' if papers[key]['doi'] else 'no doi or title in ref.bib'
            unresolved[key] = reason
    save()


# --- OpenAlex: reference lists ---

def _norm_title(t):
    return re.sub(r'[^a-z0-9]+', '', t.lower())


def _same_title(a, b):
    na, nb = _norm_title(a), _norm_title(b)
    return na == nb or (min(len(na), len(nb)) > 20 and (na in nb or nb in na))


def _oa_record(work):
    return {
        'id': work['id'].rsplit('/', 1)[-1],
        'referenced_works': [w.rsplit('/', 1)[-1]
                             for w in (work.get('referenced_works') or [])],
        'cited_by_count': work.get('cited_by_count'),
    }


def resolve_openalex(papers, cache, save, mailto=None):
    oa = cache.setdefault('openalex', {})
    oa_un = cache.setdefault('openalex_unresolved', {})
    todo = {k: v for k, v in papers.items() if k not in oa and k not in oa_un}
    base_params = {'select': OA_FIELDS}
    if mailto:
        base_params['mailto'] = mailto

    doi_keys = [k for k, v in todo.items() if v['doi']]
    if doi_keys:
        print(f'OpenAlex: resolving {len(doi_keys)} items by DOI '
              f'({(len(doi_keys) + 49) // 50} batch requests)...')
    for i in range(0, len(doi_keys), 50):
        chunk = doi_keys[i:i + 50]
        by_doi = {papers[k]['doi'].lower(): k for k in chunk}
        r = _api_call('GET', f'{OA_API}/works', interval=OA_INTERVAL,
                      params=dict(base_params, **{'filter': 'doi:' + '|'.join(by_doi),
                                                  'per-page': 50}))
        r.raise_for_status()
        for work in r.json().get('results', []):
            doi = (work.get('doi') or '').replace('https://doi.org/', '').lower()
            key = by_doi.get(doi)
            if key:
                oa[key] = _oa_record(work)
        save()

    title_keys = [k for k, v in todo.items() if k not in oa and v['title']]
    if title_keys:
        print(f'OpenAlex: resolving {len(title_keys)} items by title search...')
    for n, key in enumerate(title_keys, 1):
        # commas and pipes are filter syntax; the search tokenizer ignores them anyway
        query = re.sub(r'[,|]', ' ', papers[key]['title'])
        r = _api_call('GET', f'{OA_API}/works', interval=OA_INTERVAL,
                      params=dict(base_params, **{'filter': f'title.search:{query}',
                                                  'per-page': 1}))
        r.raise_for_status()
        results = r.json().get('results') or []
        if results and _same_title(papers[key]['title'], results[0].get('title') or ''):
            oa[key] = _oa_record(results[0])
        else:
            oa_un[key] = 'no openalex match'
        if n % 25 == 0:
            print(f'  {n}/{len(title_keys)}', flush=True)
            save()

    for key in todo:
        if key not in oa and key not in oa_un:
            reason = 'doi lookup miss' if papers[key]['doi'] else 'no doi or title in ref.bib'
            oa_un[key] = reason
    save()


# --- Graph ---

def build_graph(cache):
    """Nodes: items resolved on either source. Edges: union of both sources."""
    resolved = cache.get('resolved', {})
    oa = cache.get('openalex', {})
    nodes = sorted(set(resolved) | set(oa))
    edges = set()

    s2_refs = cache.get('references', {})  # optional per-paper S2 reference lists
    s2_id_to_key = {v['paperId']: k for k, v in resolved.items()}
    for key, rec in resolved.items():
        for ref_id in s2_refs.get(rec['paperId'], rec.get('referenceIds', [])):
            cited = s2_id_to_key.get(ref_id)
            if cited and cited != key:
                edges.add((key, cited))

    oa_id_to_key = {v['id']: k for k, v in oa.items()}
    for key, rec in oa.items():
        for ref_id in rec['referenced_works']:
            cited = oa_id_to_key.get(ref_id)
            if cited and cited != key:
                edges.add((key, cited))

    return nodes, sorted(edges)


def pagerank(nodes, edges, damping=0.85, iterations=100):
    """Standard PageRank on the citation graph (edge A->B: A cites B)."""
    out_edges = {n: [] for n in nodes}
    for a, b in edges:
        out_edges[a].append(b)
    rank = {n: 1.0 / len(nodes) for n in nodes}
    for _ in range(iterations):
        new = {n: (1 - damping) / len(nodes) for n in nodes}
        for a, targets in out_edges.items():
            if targets:
                share = damping * rank[a] / len(targets)
                for b in targets:
                    new[b] += share
            else:  # dangling node: spread evenly
                share = damping * rank[a] / len(nodes)
                for n in new:
                    new[n] += share
        rank = new
    return rank


# --- Louvain communities ---

def _louvain_level(node_list, adjacency, rng):
    """One Louvain phase: greedy local moves maximizing modularity gain."""
    m2 = sum(len(adjacency[n]) for n in node_list)  # 2m
    comm = {n: n for n in node_list}
    comm_deg = {n: len(adjacency[n]) for n in node_list}
    improved = True
    while improved:
        improved = False
        order = node_list[:]
        rng.shuffle(order)
        for n in order:
            deg = len(adjacency[n])
            if not deg:
                continue
            old = comm[n]
            comm_deg[old] -= deg
            links = Counter(comm[x] for x in adjacency[n])
            best, best_gain = old, links.get(old, 0) - comm_deg[old] * deg / m2
            for c, l in links.items():
                gain = l - comm_deg[c] * deg / m2
                if gain > best_gain + 1e-12:
                    best, best_gain = c, gain
            comm[n] = best
            comm_deg[best] += deg
            if best != old:
                improved = True
    return comm


def communities(nodes, edges, max_communities=8, min_size=8):
    """{node: community_index}; indices 0..k-1 by size, k = 'other'."""
    adj = defaultdict(set)
    for a, b in edges:
        adj[a].add(b)
        adj[b].add(a)
    rng = random.Random(42)
    connected = [n for n in nodes if adj[n]]
    comm = _louvain_level(connected, adj, rng)
    # Aggregate and run a second level for stability.
    super_adj = defaultdict(list)
    for a, b in edges:
        ca, cb = comm[a], comm[b]
        if ca != cb:
            super_adj[ca].append(cb)
            super_adj[cb].append(ca)
        else:
            super_adj[ca].extend([ca, ca])
    super_comm = _louvain_level(sorted(set(comm.values())), super_adj, rng)
    label = {n: super_comm[comm[n]] for n in connected}

    sizes = Counter(label.values())
    top = [c for c, n in sizes.most_common(max_communities) if n >= min_size]
    comm_idx = {c: i for i, c in enumerate(top)}
    other = len(top)
    return {n: comm_idx.get(label.get(n), other) for n in nodes}, len(top)


def community_labels(litman, nodes, comm, n_comm):
    """Label each community from its members' most common summary keywords."""
    kw = defaultdict(Counter)
    for name in nodes:
        try:
            item = litman.get_item(name)
        except Exception:
            continue
        summary = item.read_summary() if item.has_summary else None
        if summary:
            kw[comm[name]].update(summary.get('keywords', []))
    labels = []
    for c in range(n_comm):
        top = [w for w, _ in kw[c].most_common(2)]
        labels.append(' · '.join(top).capitalize() if top else f'community {c + 1}')
    labels.append('Other / unlinked')
    return labels


# --- Outputs ---

def _topic_of(litman, name):
    try:
        item = litman.get_item(name)
    except Exception:
        return ''
    summary = item.read_summary() if item.has_summary else None
    return (summary or {}).get('topic', '')


def _merge_meta(cache, nodes):
    """Per-node metadata, preferring S2 counts, falling back to OpenAlex."""
    resolved = cache.get('resolved', {})
    oa = cache.get('openalex', {})
    meta = {}
    for key in nodes:
        s2 = resolved.get(key, {})
        o = oa.get(key, {})
        cites = s2.get('citationCount')
        if cites is None:
            cites = o.get('cited_by_count')
        meta[key] = {
            's2_paperId': s2.get('paperId'),
            'openalex_id': o.get('id'),
            'year': s2.get('year'),
            'citationCount': cites,
            'influentialCitationCount': s2.get('influentialCitationCount'),
        }
    return meta


def write_report(litman, outfile, cache, nodes, edges, meta, in_degree, ranks):
    unresolved = sorted(set(cache.get('unresolved', {}))
                        & set(cache.get('openalex_unresolved', {})))

    def row(rank_n, key):
        m = meta[key]
        topic = _topic_of(litman, key)
        if len(topic) > 90:
            topic = topic[:87] + '...'
        return (f'| {rank_n} | {key} | {in_degree.get(key, 0)} | {ranks[key]*1000:.2f} '
                f'| {m["citationCount"] if m["citationCount"] is not None else "?"} '
                f'| {m["influentialCitationCount"] if m["influentialCitationCount"] is not None else "?"} '
                f'| {topic} |')

    header = ('| # | paper | cited by (in-library) | PageRank ×1000 '
              '| global citations | influential | topic |\n'
              '|---|---|---|---|---|---|---|')

    def table(keys):
        return '\n'.join([header] + [row(i, k) for i, k in enumerate(keys, 1)])

    by_internal = sorted(nodes, key=lambda k: (-in_degree.get(k, 0), -ranks[k]))[:30]
    by_pagerank = sorted(nodes, key=lambda k: -ranks[k])[:30]
    by_global = sorted(nodes, key=lambda k: -(meta[k]['citationCount'] or 0))[:30]

    lines = [
        '# Citation network report',
        '',
        f'Generated {date.today()} by `litman citation-graph`. Reference lists '
        'from OpenAlex (S2 elides them for some publishers); citation counts from '
        'Semantic Scholar, falling back to OpenAlex.',
        '',
        f'- Items in corpus: {len(cache.get("resolved", {})) + len(cache.get("unresolved", {}))}; '
        f'resolved (either source): {len(nodes)}; unresolved on both: {len(unresolved)}.',
        f'- Internal citation edges (paper A cites paper B, both in library): {len(edges)}.',
        f'- Papers cited by at least one other library paper: '
        f'{sum(1 for k in nodes if in_degree.get(k, 0) > 0)}.',
        '',
        '## Most cited within the library (internal in-degree)',
        '',
        'How many *of my own papers* cite it — the foundational papers for this corpus.',
        '',
        table(by_internal),
        '',
        '## PageRank on the internal graph',
        '',
        'Rewards papers cited by other well-cited papers, not just raw counts.',
        '',
        table(by_pagerank),
        '',
        '## Most cited globally',
        '',
        'Field-wide influence; "influential" is S2\'s estimate of citations that build on the work.',
        '',
        table(by_global),
        '',
        '## Unresolved papers',
        '',
        f'{len(unresolved)} papers could not be matched on either source:',
        '',
    ]
    for key in unresolved:
        lines.append(f'- {key}')
    lines.append('')
    with open(outfile, 'w') as f:
        f.write('\n'.join(lines))


def write_html(litman, outfile, total, nodes, edges, meta, in_degree, ranks,
               comm, labels):
    """Inject the graph into the self-contained interactive template."""
    idx = {k: i for i, k in enumerate(nodes)}
    out_nodes = []
    for k in nodes:
        m = meta[k]
        topic = _topic_of(litman, k)
        if len(topic) > 140:
            topic = topic[:140] + '…'
        out_nodes.append({
            'k': k,
            'y': m['year'],
            'c': m['citationCount'],
            'd': in_degree.get(k, 0),
            'p': round(ranks[k] * 1000, 2),
            't': topic,
            'g': comm[k],
        })
    data = {
        'generated': str(date.today()),
        'total': total,
        'clusters': labels,
        'nodes': out_nodes,
        'edges': [[idx[a], idx[b]] for a, b in edges],
    }
    with open(TEMPLATE_FN) as f:
        html = f.read()
    html = html.replace('const DATA = /*__DATA__*/;',
                        'const DATA = ' + json.dumps(data, separators=(',', ':')) + ';')
    with open(outfile, 'w') as f:
        f.write(html)


def build(litman, refresh=False, mailto=None):
    papers = scan_corpus(litman)
    print(f'{len(papers)} items in corpus.')

    cache_fn = litman.data_path(CACHE_BASENAME)
    cache = {}
    if not refresh and os.path.exists(cache_fn):
        with open(cache_fn) as f:
            cache = json.load(f)

    def save():
        with open(cache_fn, 'w') as f:
            json.dump(cache, f, indent=1)

    resolve_s2(papers, cache, save)
    resolve_openalex(papers, cache, save, mailto=mailto)

    nodes, edges = build_graph(cache)
    meta = _merge_meta(cache, nodes)
    in_degree = {}
    for _, cited in edges:
        in_degree[cited] = in_degree.get(cited, 0) + 1
    ranks = pagerank(nodes, edges)
    comm, n_comm = communities(nodes, edges)
    labels = community_labels(litman, nodes, comm, n_comm)

    graph_fn = litman.data_path('citation_graph.json')
    with open(graph_fn, 'w') as f:
        json.dump({
            'generated': str(date.today()),
            'nodes': {k: dict(meta[k], in_degree=in_degree.get(k, 0),
                              pagerank=ranks[k], community=comm[k],
                              community_label=labels[comm[k]])
                      for k in nodes},
            'communities': labels,
            'edges': [list(e) for e in edges],
        }, f, indent=1)

    report_fn = litman.data_path('citation_report.md')
    write_report(litman, report_fn, cache, nodes, edges, meta, in_degree, ranks)
    html_fn = litman.data_path('citation_network.html')
    write_html(litman, html_fn, len(papers), nodes, edges, meta, in_degree,
               ranks, comm, labels)

    print(f'{len(nodes)} nodes, {len(edges)} internal edges, '
          f'{sum(1 for k in nodes if in_degree.get(k, 0) > 0)} papers cited in-library.')
    for fn in (graph_fn, report_fn, html_fn):
        print(f'Wrote {fn}')
