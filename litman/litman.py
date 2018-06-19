import os
import re
from logging import getLogger
from subprocess import call, Popen
from collections import Counter, defaultdict
from signal import signal, SIGPIPE, SIG_DFL

import simplejson
from configparser import ConfigParser

from pybtex.database import parse_file as parse_bib_file
from pybtex.database import BibliographyData

logger = getLogger('litman')


def load_config():
    litmanrc_fn = os.path.join(os.path.expandvars('$HOME'), '.litmanrc')
    if os.path.exists(litmanrc_fn):
        config = ConfigParser()
        with open(litmanrc_fn, 'r') as f:
            config.read_file(f)
        return litmanrc_fn, config['litman']
    else:
        return None, None


def _scan_dirs(start_dir, ext):
    fns = []
    for root, dirs, files in os.walk(start_dir):
        for fn in files:
            if fn.endswith(ext):
                fns.append(os.path.join(root, fn))
                logger.debug(os.path.join(root, fn))
    return fns


def _extract_text(pdf_fn, output_fn):
    pdf_basename = os.path.basename(pdf_fn)
    text_basename = 'extracted_text.txt'
    logger.debug(f'extract text: {pdf_fn} -> {output_fn}')
    call(['pdftotext', pdf_fn, output_fn])


def _get_cites_from_tex(tex_fn):
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
    logger.debug(tex_fn)
    logger.debug(all_cites)
    return cites, parencites, all_cites


def _read_tags(tags_fn):
    with open(tags_fn, 'r') as f:
        tags = list(map(str.strip, f.read().split(',')))
    return tags


def _append_tag(tags_fn, tag):
    if os.path.exists(tags_fn):
        tags = _read_tags(tags_fn)
        tags.append(tag)
    else:
        tags = [tag]

    tags = list(set(tags))
    logger.debug(f'appending tags {tags}')
    with open(tags_fn, 'w') as f:
        f.write(','.join(tags) + '\n')


def _remove_periods(path):
    return os.path.join('/', os.path.relpath(path, '/'))


class ItemNotFound(Exception):
    pass


class LitItem:
    def __init__(self, litman, name):
        self.litman = litman
        if not os.path.exists(os.path.join(self.litman.lit_dir, name)):
            raise ItemNotFound(f'item {name} not found')

        self.name = name

        self.level_fn = os.path.join(self.litman.lit_dir, name, f'level.txt')
        self.pdf_fn = os.path.join(self.litman.lit_dir, name, f'{name}.pdf')
        self.bib_fn = os.path.join(self.litman.lit_dir, name, 'ref.bib')
        self.extracted_text_fn = os.path.join(self.litman.lit_dir, name, 'extracted_text.txt')
        self.mag_entry_fn = os.path.join(self.litman.lit_dir, name, 'mag_entry.json')
        self.cites_fn = os.path.join(self.litman.lit_dir, name, 'cites.json')
        self.cited_by_fn = os.path.join(self.litman.lit_dir, name, 'cited_by.json')

        self.tags_fn = os.path.join(self.litman.lit_dir, name, 'tags.txt')

        self.level = int(open(self.level_fn, 'r').read())

        self.has_pdf = os.path.exists(self.pdf_fn)
        self.has_bib = os.path.exists(self.bib_fn)
        self.has_extracted_text = os.path.exists(self.extracted_text_fn)
        self.has_tags = os.path.exists(self.tags_fn)
        self.has_mag = os.path.exists(self.mag_entry_fn)
        self.has_cites = os.path.exists(self.cites_fn)
        self.has_cited_by = os.path.exists(self.cited_by_fn)

        if self.has_bib:
            self.bib_data = parse_bib_file(self.bib_fn)
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

        if self.has_cites:
            with open(self.cites_fn, 'r') as f:
                self.cites = simplejson.load(f)
        else:
            self.cites = []

        if self.has_cited_by:
            with open(self.cited_by_fn, 'r') as f:
                self.cited_by = simplejson.load(f)
        else:
            self.cited_by = []

        if self.has_tags:
            self.tags = _read_tags(self.tags_fn)
        else:
            self.tags = []

        self._mag_loaded = False

    def title(self):
        if self.has_bib:
            return self.bib_entry.fields['title']
        elif self.has_mag:
            return self.mag_entry()['Ti']
        else:
            return ''

    def year(self):
        years = []

        if self.has_bib:
            bib_year = int(self.bib_entry.fields['year'])
            years.append(bib_year)
        if self.has_mag:
            mag_year = self.mag_entry()['Y']
            years.append(mag_year)
        if 'import_pdf' in self.tags or 'import_bib' in self.tags:
            name_year = re.match('\D*(?P<year>\d*)\D*', self.name).group('year')
            if len(name_year) != 4:
                logger.warn(f'{self.name}: Year {name_year} in wrong format')
            else:
                name_year = int(name_year)
                years.append(name_year)

        if years[1:] != years[:-1]:
            logger.warn(f'{self.name}: Elements not all equal: {years}')

        if years:
            return years[0]
        else:
            return -999


    def _format_bib_authors(self):
        authors = self.bib_entry.persons['author']
        # returns last names of authors.
        return ', '.join([a.last()[0] for a in authors])

    def _format_mag_authors(self):
        if 'E' not in self.mag_entry():
            return ''
        authors = self.mag_entry()['E']['ANF']
        # returns last names of authors.
        return ', '.join([a['LN'] for a in authors])

    def authors(self):
        if self.has_bib:
            return self._format_bib_authors()
        elif self.has_mag:
            return self._format_mag_authors()
        else:
            return ''

    def mag_entry(self):
        if not self._mag_loaded:
            self._load_mag()
        return self._mag_entry

    def append_tag(self, tag):
        _append_tag(self.tags_fn, tag)

    def add_pdf(self, pdf_fn):
        _extract_text(pdf_fn, self.extracted_text_fn)

        pdf_symlink = self.pdf_fn
        if not os.path.exists(self.pdf_fn):
            os.symlink(pdf_fn, self.pdf_fn)

    def add_bib_data(self, bib_name, bib_entry):
        single_bib_data = BibliographyData({bib_name: bib_entry})
        single_bib_data.to_file(self.bib_fn)

    def add_mag_data(self, mag_entry):
        with open(self.mag_entry_fn, 'w') as f:
            simplejson.dump(mag_entry, f)

    def add_cites(self, ref_item_name):
        self.cites = list(set(self.cites + [ref_item_name]))
        logger.debug(self.cites)
        with open(self.cites_fn, 'w') as f:
            simplejson.dump(self.cites, f)

    def add_cited_by(self, item_name):
        self.cited_by = list(set(self.cited_by + [item_name]))
        logger.debug(self.cited_by)
        with open(self.cited_by_fn, 'w') as f:
            simplejson.dump(self.cited_by, f)

    def _load_mag(self):
        with open(self.mag_entry_fn, 'r') as f:
            self._mag_entry = simplejson.load(f)
        self._mag_loaded = True

    def display(self):
        if self.has_pdf:
            Popen(['evince', self.pdf_fn])
        else:
            logger.info(f'item {self.name} has no PDF')

    def __repr__(self):
        return f"LitItem('{self.name}')"


class LitMan:
    BIB_COUNTER_FIELDS = ['year', 'publisher', 'journal']

    def __init__(self, lit_dir):
        self.lit_dir = lit_dir
        self.items = []
        self._tags = []
        self._scanned = False

    def import_pdf(self, import_dir):
        import_dir = os.path.join(os.getcwd(), import_dir)
        import_dir = _remove_periods(import_dir)
        pdf_fns = _scan_dirs(import_dir, ext='.pdf')

        for pdf_fn in pdf_fns:
            logger.info(f'Importing: {pdf_fn}')
            pdf_basename = os.path.basename(pdf_fn)
            item_name = os.path.splitext(pdf_basename)[0]

            try:
                item = self.get_item(item_name)
                logger.info(f'Item {item_name} already exists')
            except ItemNotFound:
                logger.info(f'Creating item {item_name}')
                item = self.create_item(item_name, level=0)
                tag = os.path.basename(os.path.dirname(pdf_fn))
                item.append_tag(tag)
                item.append_tag('import_pdf')

            if not item.has_pdf:
                item.add_pdf(pdf_fn)

    def import_bib(self, import_dir):
        import_dir = os.path.join(os.getcwd(), import_dir)
        import_dir = _remove_periods(import_dir)
        bib_fns = _scan_dirs(import_dir, ext='.bib')
        for bib_fn in bib_fns:
            logger.info(f'Importing: {bib_fn}')
            bib_data = parse_bib_file(bib_fn)
            tag = os.path.basename(os.path.dirname(bib_fn))
            for bib_name, bib_entry in bib_data.entries.items():
                item_name = bib_name

                try:
                    item = self.get_item(item_name)
                    logger.info(f'Item {item_name} already exists')
                except ItemNotFound:
                    logger.info(f'Creating item {item_name}')
                    item = self.create_item(item_name, level=0)
                    item.append_tag(tag)
                    item.append_tag('import_bib')

                if not item.has_bib:
                    item.add_bib_data(bib_name, bib_entry)

    def build_refs(self, level=None, create_items=True):
        mag_items = self.get_items(has_mag=True, level=level)
        mag_id_dict = dict([(item.mag_entry()['Id'], item) for item in mag_items])
        for item in mag_items:
            if 'RId' not in item.mag_entry():
                logger.warn(f'No RId for {item.name}')
                continue
            for ref_mag_id in set(item.mag_entry()['RId']):
                if ref_mag_id in mag_id_dict:
                    ref_item = mag_id_dict[ref_mag_id]
                    logger.info(f'{item.name} -> {ref_item.name}')
                else:
                    try:
                        ref_item = self.get_item(str(ref_mag_id))
                        logger.info(f'Item already exists {ref_mag_id}')
                    except:
                        if create_items:
                            logger.info(f'Creating ref for {ref_mag_id}')
                            ref_item = self.create_item(str(ref_mag_id), item.level - 1)
                    if create_items:
                        ref_item.append_tag('mag_ref')

                item.add_cites(ref_item.name)
                if create_items:
                    ref_item.add_cited_by(item.name)


    def create_item(self, name, level):
        if not self._scanned:
            self._scan()
        if os.path.exists(os.path.join(self.lit_dir, name)):
            raise Exception(f'Item {name} already exists')

        os.makedirs(os.path.join(self.lit_dir, name))
        open(os.path.join(self.lit_dir, name, 'level.txt'), 'w').write(str(level))

        item = LitItem(self, name)
        self.items.append(item)
        return item

    def get_item(self, item_name):
        item = LitItem(self, item_name)
        return item

    def get_items(self, tag_filter=None, 
                  has_pdf=None, has_bib=None, has_extracted_text=None, has_mag=None,
                  level=None):
        self._scan()
        items = [item for item in self.items]
        if tag_filter:
            items = [item for item in items if tag_filter in item.tags]
        if has_pdf is not None:
            items = [item for item in items if item.has_pdf == has_pdf]
        if has_bib is not None:
            items = [item for item in items if item.has_bib == has_bib]
        if has_extracted_text is not None:
            items = [item for item in items if item.has_extracted_text == has_extracted_text ]
        if has_mag is not None:
            items = [item for item in items if item.has_mag == has_mag]
        if level is not None:
            items = [item for item in items if item.level == level]
        return items

    def get_tags(self):
        self._scan()
        return self._tags.most_common()

    def list_items(self, tag_filter=None, sort_on=['name'], reverse=False, level=0):
        self._scan()
        items = self.get_items(tag_filter, level=level)

        for sort in sort_on:
            if sort == 'cites':
                items = sorted(items, key=lambda item: len(item.cites))
            elif sort == 'cited-by':
                items = sorted(items, key=lambda item: len(item.cited_by))
            elif sort == 'year':
                items = sorted(items, key=lambda item: item.year())
            else:
                items = sorted(items, key=lambda item: getattr(item, sort))

        if reverse:
            items = items[::-1]

        # Handle a broken pipe:
        signal(SIGPIPE, SIG_DFL) 

        fmt = f'{{0:<{self.max_itemname_len + 1}}}: {{1:<20}} {{2:>4}} {{3}}/{{4}}/{{5}} {{6:>5}} {{7:>5}} {{8:<50}} {{9}}'
        print(fmt.format(*['item_name', 'authors', 'year', 'P', 'B', 'M', 'cites', 'cited', 'title', 'tags']))
        print('=' * len(fmt.format(*['item_name', 'authors', 'year', 'P', 'B', 'M', 'cites', 'cited', 'title', 'tags'])))

        def bstr(b):
            return 'T' if b else 'F'

        for item in items:
            if not tag_filter or tag_filter in item.tags:
                print(fmt.format(item.name, item.authors()[:20], item.year(),
                                 bstr(item.has_pdf), bstr(item.has_bib), bstr(item.has_mag), 
                                 len(item.cites), len(item.cited_by), item.title()[:50], item.tags))

    def rescan(self):
        self._scanned = False
        self.items = []
        self._scan()

    def search(self, text, ignore_case=False):
        self._scan()
        flags = re.MULTILINE | re.DOTALL
        if ignore_case:
            flags |= re.IGNORECASE
        all_matches = []
        m = re.compile(text, flags=flags)
        for item in [item for item in self.items if item.has_extracted_text]:
            matches = list(re.finditer(m, item.extracted_text))
            if matches:
                all_matches.append((item, matches))
                logger.debug(f'found matches for {item.name}')
                for match in matches:
                    logger.debug(f'matches: {matches}')
        return all_matches

    def gen_bib_for_tex_dir(self, tex_dir, outfile, dry_run):
        tex_fns = _scan_dirs(tex_dir, '.tex')
        all_cites = []
        for tex_fn in tex_fns:
            _, _, all_cites_for_file = _get_cites_from_tex(tex_fn)
            all_cites.extend(all_cites_for_file)
        all_cites = list(set(all_cites))
        bib_data = self._create_bib(all_cites)
        if dry_run:
            print(bib_data.to_string('bibtex'))
        else:
            bib_data.to_file(outfile)
        return bib_data

    def gen_bib_for_tex(self, tex_fn, outfile, dry_run):
        _, _, all_cites = _get_cites_from_tex(tex_fn)
        bib_data = self._create_bib(all_cites)
        if dry_run:
            print(bib_data.to_string('bibtex'))
        else:
            bib_data.to_file(outfile)
        return bib_data

    def _create_bib(self, cites):
        items = []
        for cite in cites:
            try:
                item = self.get_item(cite)
                items.append(item)
            except ItemNotFound:
                logger.error(f'Cannot find {cite}')

        items = sorted(items, key=lambda item: item.name)
        bib_data_dict = {}
        for item in items:
            if not item.has_bib:
                logger.error(f'No bib for {item.name}')
            else:
                logger.info(f'Creating bib entry: {item.bib_name}')
                bib_data_dict[item.bib_name] = item.bib_entry
        return BibliographyData(bib_data_dict) 

    def _scan(self):
        if self._scanned:
            return
        self._scanned = True
        self.max_itemname_len = 0

        tags = Counter()
        bib_counters = defaultdict(Counter)

        for item_dir in os.listdir(self.lit_dir):
            if item_dir[0] == '.':
                continue
            if not os.path.isdir(os.path.join(self.lit_dir, item_dir)):
                continue
            logger.debug(f'  adding item_dir {item_dir}')
            item = LitItem(self, item_dir)
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
