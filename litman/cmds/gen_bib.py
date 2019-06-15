"""Generate .bib bibtex file from citations in .tex files"""
import os

ARGS = [(['--tag-filter', '-t'], {'help': 'tag to filter on', 'default': None}),
        (['--outfile', '-o'], {'help': 'Name of output file'}),
        (['--dry-run', '-d'], {'help': 'Dry run only', 'action': 'store_true'}),
        (['infile'], {'nargs': '?', 'help': 'Name of input file'})]


def main(litman, args):
    if args.tag_filter:
        litman.gen_bib_for_tag(args.tag_filter, args.outfile, args.dry_run)
    elif os.path.isfile(args.infile):
        litman.gen_bib_for_tex(args.infile, args.outfile, args.dry_run)
    elif os.path.isdir(args.infile):
        litman.gen_bib_for_tex_dir(args.infile, args.outfile, args.dry_run)
    else:
        print(f'{args.infile} not a file or dir')

