"""Normalize DOI formats and journal-name capitalization (dry run by default)"""

ARGS = [
    (['--apply', '-a'], {'help': 'Write changes to ref.bib (default: dry run)', 'action': 'store_true'}),
    (['--tag-filter', '-t'], {'help': 'Only items carrying this tag', 'default': None}),
]


def main(litman, args):
    litman.normalize(apply=args.apply, tag_filter=args.tag_filter)
