"""Build the internal citation network (Semantic Scholar + OpenAlex)"""

ARGS = [
    (['--refresh'], {'action': 'store_true',
                     'help': 'Ignore the API cache and redo all lookups'}),
    (['--mailto'], {'default': None,
                    'help': 'Email for the OpenAlex polite pool (faster, more reliable)'}),
]


def main(litman, args):
    from litman import citations
    citations.build(litman, refresh=args.refresh, mailto=args.mailto)
