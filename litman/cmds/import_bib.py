"""Import items from parsing bibtex .bib files"""
ARGS = [(['dir'], {'nargs': 1, 'help': 'Directory to import from'}),
        (['--tag', '-t'], {'help': 'tag to add to citations', 'default': None})]


def main(litman, args):
    litman.import_bib(args.dir[0], args.tag)

