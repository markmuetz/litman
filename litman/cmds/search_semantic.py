"""Search by meaning: papers (summaries) or passages (full text)

Results are ranked candidates to read, not answers: embeddings match topic, not
claims, so "X strengthens Y" also finds "X weakens Y". Put exact terms in double
quotes to require them (e.g. '"TWP-ICE" convective downdrafts'); --hybrid also
ranks by exact-term matches, which helps with names, acronyms and case studies.
"""
from litman import embeddings

ARGS = [
    (['query'], {'help': 'What you are looking for, in your own words'}),
    (['-k'], {'type': int, 'default': 10, 'help': 'How many'}),
    (['--passages', '-p'], {'action': 'store_true', 'help': 'Search full-text passages, best per paper'}),
    (['--hybrid'], {'action': 'store_true', 'help': 'Combine meaning with exact-term matching (passages)'}),
]


def main(litman, args):
    if not embeddings.available():
        print('search-semantic needs fastembed and numpy: `uv tool install --editable <litman> --with fastembed`')
        return
    title = lambda k: embeddings.item_title(litman.get_item(k))[:80]
    if args.passages or args.hybrid or '"' in args.query:
        hits = embeddings.search_passages(litman, args.query, args.k, hybrid=args.hybrid)
        if not hits:
            print('No passage index: run `litman embed --passages` (slow the first time).')
        for key, score, text in hits:
            print(f'{score:.3f}  {key:30s}  {title(key)}\n       "{text[:320]}..."\n')
    else:
        hits = embeddings.search_summaries(litman, args.query, args.k)
        if not hits:
            print('No summary index: run `litman embed`.')
        for key, score in hits:
            print(f'{score:.3f}  {key:30s}  {title(key)}')
