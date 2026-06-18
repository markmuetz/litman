"""Import items from PDF filenames (and fetch their BibTeX from CrossRef)"""
from litman.litman import load_config

ARGS = [(['dir'], {'nargs': 1, 'help': 'Directory to import from'}),
        (['--tags', '-t'], {'help': 'comma separated tags', 'default': ''}),
        (['--project', '-p'], {'help': 'project to add to', 'default': None}),
        (['--no-fetch-bib'], {'action': 'store_true',
                              'help': "Don't look up a BibTeX entry from CrossRef on import"}),
        (['--mailto', '-m'], {'help': 'Email for CrossRef polite pool', 'default': None})]


def main(litman, args):
    tags = args.tags.split(',')

    mailto = args.mailto
    if not mailto:
        _, conf = load_config()
        if conf and 'crossref_mailto' in conf:
            mailto = conf['crossref_mailto']

    litman.import_pdf(args.dir[0], tags, args.project,
                      fetch_bib=not args.no_fetch_bib, mailto=mailto)
