"""Generate .bib bibtex file from citations in .tex files"""
import os

ARGS = [(['--tag-filter', '-t'], {'help': 'tag to filter on', 'default': None}),
        (['--outfile', '-o'], {'help': 'Name of output file'}),
        (['--dry-run', '-d'], {'help': 'Dry run only', 'action': 'store_true'}),
        (['--no-rename-title', '-n'], {'help': 'Do not rename titles of entries', 'action': 'store_true'}),
        (['infiles'], {'nargs': '*', 'help': 'Name of input files or dir'})]


def main(litman, args):
    if args.tag_filter:
        litman.gen_bib_for_tag(args.tag_filter, args.outfile, args.dry_run, args.no_rename_title)
    elif args.infiles[0] == '.':
        litman.gen_bib_for_tex_dir(args.infiles[0], args.outfile, args.dry_run, args.no_rename_title)
    else:
        litman.gen_bib_for_tex_fns(args.infiles, args.outfile, args.dry_run, args.no_rename_title)
