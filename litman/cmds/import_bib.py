ARGS = [(['dir'], {'nargs': 1, 'help': 'Directory to import from'})]


def main(litman, args):
    litman.import_bib(args.dir[0])

