"""Papers whose summaries are closest in meaning to a given paper"""
from litman import embeddings

ARGS = [
    (['item_name'], {'help': 'Citation key'}),
    (['-k'], {'type': int, 'default': 10, 'help': 'How many'}),
]


def main(litman, args):
    if not embeddings.available():
        print('similar needs fastembed and numpy: `uv tool install --editable <litman> --with fastembed`')
        return
    hits = embeddings.similar(litman, args.item_name, args.k)
    if hits is None:
        print(f'{args.item_name}: no summary embedding (no summary.json, confidential, or run `litman embed`)')
        return
    for key, score in hits:
        print(f'{score:.3f}  {key:30s}  {embeddings.item_title(litman.get_item(key))[:80]}')
