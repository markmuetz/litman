"""Build references between items"""
ARGS = [(['--create-items', '-c'], {'help': 'Create new items', 'action': 'store_true'}),
        (['--level', '-l'], {'help': 'level to build refs for', 'default': None, 'type': int})]


def main(litman, args):
    litman.build_refs(level=args.level, create_items=args.create_items)
