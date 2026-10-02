"""Build or update the local embedding indexes (summaries; --passages for full text)"""
from litman import embeddings

ARGS = [
    (['--passages', '-p'], {'action': 'store_true',
                            'help': 'Also embed full-text passages (slow the first time: ~2 h for 1000 papers)'}),
    (['--threads'], {'type': int, 'default': embeddings.DEFAULT_THREADS,
                     'help': 'CPU threads (default %(default)s); run big builds under `nice`'}),
]


def main(litman, args):
    if not embeddings.available():
        print('embed needs fastembed and numpy: `uv tool install --editable <litman> --with fastembed`')
        return
    embeddings.update(litman, chunks_too=args.passages, threads=args.threads)
    print('Embeddings up to date.')
