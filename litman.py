import os
import sys
import logging
from subprocess import call, Popen
from glob import glob
import re
from collections import Counter, defaultdict

from pybtex.database import parse_file
from pybtex.database import BibliographyData, Entry

logging.basicConfig(level=logging.DEBUG)

LIT_BASEDIR = '/home/markmuetz/Dropbox/PhD/LitMan/literature'


def scan_dirs(start_dir, ext):
    fns = []
    for root, dirs, files in os.walk(start_dir):
        for fn in files:
            if fn.endswith(ext):
                fns.append(os.path.join(root, fn))
                logging.debug(os.path.join(root, fn))
    return fns


def extract_text(pdf_fn, output_dir=os.getcwd()):
    pdf_basename = os.path.basename(pdf_fn)
    text_basename = 'extracted_text.txt'
    text_fn = os.path.join(output_dir, text_basename)
    logging.debug(f'extract text: {pdf_fn} -> {text_fn}')
    call(['pdftotext', pdf_fn, text_fn])


def get_cites_from_tex(tex_fn):
    with open(tex_fn, 'r') as f:
        lines = f.readlines()
    cites = []
    parencites = []
        
    for l in lines:
        cites.extend([m.group('cite') for m in re.finditer('\\\\cite\{(?P<cite>\w*)\}', l)])

    for l in lines:
        parencites.extend([m.group('parencite') for m in re.finditer('\\\\parencite\{(?P<parencite>\w*)\}', l)])

    cites = list(set(cites))
    parencites = list(set(parencites))
    all_cites = list(set(cites + parencites))
    logging.debug(tex_fn)
    logging.debug(all_cites)
    return cites, parencites, all_cites


class ItemNotFound(Exception):
    pass


class LitItem:
    def __init__(self, name):
        if not os.path.exists(os.path.join(LIT_BASEDIR, name)):
            raise ItemNotFound(f'item {name} not found')

        self.name = name

        self.pdf_fn = os.path.join(LIT_BASEDIR, name, f'{name}.pdf')
        self.bib_fn = os.path.join(LIT_BASEDIR, name, 'ref.bib')
        self.extracted_text_fn = os.path.join(LIT_BASEDIR, name, 'extracted_text.txt')
        self.tags_fn = os.path.join(LIT_BASEDIR, name, 'tags.txt')

        self.has_pdf = os.path.exists(self.pdf_fn)
        self.has_bib = os.path.exists(self.bib_fn)
        self.has_extracted_text = os.path.exists(self.extracted_text_fn)
        self.has_tags = os.path.exists(self.tags_fn)

        if self.has_bib:
            self.bib_data = parse_file(self.bib_fn)
            assert len(self.bib_data.entries.keys()) == 1
            self.bib_name = self.bib_data.entries.keys()[0]
            self.bib_entry = self.bib_data.entries.values()[0]
        else:
            self.bib_data = None

        if self.has_extracted_text:
            with open(self.extracted_text_fn, 'r') as f:
                self.extracted_text = f.read()
        else:
            self.extracted_text = None

        if self.has_tags:
            with open(self.tags_fn, 'r') as f:
                self.tags = list(map(str.strip, f.read().split(',')))
        else:
            self.tags = []

    def display(self):
        if self.has_pdf:
            Popen(['evince', self.pdf_fn])

    def __repr__(self):
        return f"LitItem('{self.name}')"


class LitMan:
    BIB_COUNTER_FIELDS = ['year', 'publisher', 'journal']

    def __init__(self, lit_dir):
        self.lit_dir = lit_dir
        self.items = []
        self._tags = []
        self.scanned = False

    def import_pdf(self, import_dir):
        import_dir = os.path.join(os.getcwd(), import_dir)
        pdf_fns = scan_dirs(import_dir, ext='.pdf')
        for pdf_fn in pdf_fns:
            pdf_basename = os.path.basename(pdf_fn)
            paper_name = os.path.splitext(pdf_basename)[0]
            paper_dir = os.path.join(LIT_BASEDIR, paper_name)
            tag = os.path.basename(os.path.dirname(pdf_fn))

            if not os.path.exists(paper_dir):
                os.makedirs(paper_dir)
                extract_text(pdf_fn, paper_dir)

            pdf_symlink = os.path.join(paper_dir, pdf_basename)
            if not os.path.exists(pdf_symlink):
                os.symlink(pdf_fn, pdf_symlink)
            with open(os.path.join(paper_dir, 'tags.txt'), 'w') as f:
                f.write(tag + '\n')

    def import_bib(self, import_dir):
        import_dir = os.path.join(os.getcwd(), import_dir)
        bib_fns = scan_dirs(import_dir, ext='.bib')
        for bib_fn in bib_fns:
            logging.debug(f'bib_fn: {bib_fn}')
            bib_data = parse_file(bib_fn)
            for bib_name, bib_entry in bib_data.entries.items():
                logging.debug(bib_name)
                logging.debug(bib_entry)
                paper_dir = os.path.join(LIT_BASEDIR, bib_name)
                if not os.path.exists(paper_dir):
                    os.makedirs(paper_dir)
                single_bib_data = BibliographyData({bib_name: bib_entry})
                single_bib_data.to_file(os.path.join(paper_dir, 'ref.bib'))

    def get_item(self, item_name):
        item = LitItem(item_name)
        return item

    def get_items(self, tags_filter=None, has_pdf=None, has_bib=None, has_extracted_text=None):
        self._scan()
        items = [item for item in self.items]
        if tags_filter:
            items = [item for item in self.items if tags_filter in item.tags]
        if has_pdf:
            items = [item for item in self.items if item.has_pdf]
        if has_bib:
            items = [item for item in self.items if item.has_bib]
        if has_extracted_text:
            items = [item for item in self.items if item.has_extracted_text]
        return items

    def get_tags(self):
        self._scan()
        return self._tags.most_common()

    def list_items(self, tags_filter=None, sort_on=['name'], reverse=False):
        self._scan()
        items = self.get_items(tags_filter)
        for sort in sort_on:
            items = sorted(items, key=lambda item: getattr(item, sort))
            if reverse:
                items = items[::-1]

        fstring = f'{{0:<{self.max_itemname_len + 1}}}: {{1:>5}} {{2:>5}} {{3}}'
        print(fstring.format(*['paper_name', 'pdf', 'bib', 'tags']))
        print('=' * len(fstring.format(*['paper_name', 'pdf', 'bib', 'tags'])))
        for item in items:
            if not tags_filter or tags_filter in item.tags:
                print(fstring.format(item.name, item.has_pdf, item.has_bib, item.tags))

    def rescan(self):
        self.scanned = False
        self._scan()

    def search(self, text, ignore_case=False):
        self._scan()
        flags = re.MULTILINE | re.DOTALL
        if ignore_case:
            flags |= re.IGNORECASE
        m = re.compile(text, flags=flags)
        for item in [item for item in self.items if item.has_extracted_text]:
            matches = list(re.finditer(m, item.extracted_text))
            if matches:
                print(item.name)
                for match in matches:
                    print(match)

    def gen_bib_for_tex_dir(self, tex_dir, outfile):
        tex_fns = scan_dirs(tex_dir, '.tex')
        all_cites = []
        for tex_fn in tex_fns:
            _, _, all_cites_for_file = get_cites_from_tex(tex_fn)
            all_cites.extend(all_cites_for_file)
        all_cites = list(set(all_cites))
        bib_data = self._create_bib(all_cites)
        bib_data.to_file(outfile)
        return bib_data

    def gen_bib_for_tex(self, tex_fn, outfile):
        _, _, all_cites = get_cites_from_tex(tex_fn)
        bib_data = self._create_bib(all_cites)
        bib_data.to_file(outfile)
        return bib_data

    def _create_bib(self, cites):
        items = []
        for cite in cites:
            try:
                item = self.get_item(cite)
                items.append(item)
            except ItemNotFound:
                logging.error(f'Cannot find {cite}')

        items = sorted(items, key=lambda item: item.name)
        bib_data_dict = {}
        for item in items:
            if not item.has_bib:
                logging.error(f'No bib for {item.name}')
            else:
                logging.debug(f'creating bib entry for {item.bib_name}')
                bib_data_dict[item.bib_name] = item.bib_entry
        return BibliographyData(bib_data_dict) 

    def _scan(self):
        if self.scanned:
            return
        self.scanned = True
        self.max_itemname_len = 0

        tags = Counter()
        bib_counters = defaultdict(Counter)

        for lit_item_dir in os.listdir(self.lit_dir):
            logging.debug(f'  adding lit_item_dir {lit_item_dir}')
            item = LitItem(lit_item_dir)
            self.max_itemname_len = max(self.max_itemname_len, len(item.name))
            self.items.append(item)
            for tag in item.tags:
                tags[tag] += 1

            if item.has_bib:
                for field in item.bib_entry.fields.keys():
                    if field.lower() not in self.BIB_COUNTER_FIELDS:
                        continue
                    bib_counters[field.lower()][item.bib_entry.fields[field].lower()] += 1
        self._bib_counters = bib_counters
        self._tags = tags


def main(dirname=LIT_BASEDIR):
    litman = LitMan(dirname)
    if len(sys.argv) > 1:
        func = getattr(litman, sys.argv[1])
        func(*sys.argv[2:])
    return litman


if __name__ == '__main__':
    litman = main()
