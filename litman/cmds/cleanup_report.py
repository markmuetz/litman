"""Report bibliographic inconsistencies across the whole database"""

ARGS = [(['--tag-filter', '-t'], {'help': 'Only items carrying this tag', 'default': None})]


def main(litman, args):
    litman.cleanup_report(args.tag_filter)
