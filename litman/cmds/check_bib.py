"""Check .bib bibtex file"""
import os

ARGS = [(['infile'], {'nargs': '?', 'help': 'Name of bib file'})]


def main(litman, args):
    litman.check_bib(args.infile)

