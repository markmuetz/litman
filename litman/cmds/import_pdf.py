"""Import items from PDF filenames"""
ARGS = [(['dir'], {'nargs': 1, 'help': 'Directory to import from'}),
        (['--tags', '-t'], {'help': 'comma separated tags', 'default': ''}),
        (['--project', '-p'], {'help': 'project to add to', 'default': None})]


def main(litman, args):
    tags = args.tags.split(',')
    litman.import_pdf(args.dir[0], tags, args.project)

