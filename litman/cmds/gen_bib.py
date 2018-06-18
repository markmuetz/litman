"""Generate .bib bibtex file from citations in .tex files"""
import os

ARGS = [(['--outfile', '-o'], {'help': 'Name of output file'}),
        (['--dry-run', '-d'], {'help': 'Dry run only', 'action': 'store_true'}),
        (['infile'], {'nargs': 1, 'help': 'Name of input file'})]


def main(litman, args):
    if os.path.isfile(args.infile[0]):
        litman.gen_bib_for_tex(args.infile[0], args.outfile, args.dry_run)
    elif os.path.isdir(args.infile[0]):
        litman.gen_bib_for_tex_dir(args.infile[0], args.outfile, args.dry_run)
    else:
        print(f'{args.infile[0]} not a file or dir')

