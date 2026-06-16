import os
import re
import itertools
from logging import getLogger
from subprocess import call, Popen
from collections import Counter, defaultdict
from signal import signal, SIGPIPE, SIG_DFL
import webbrowser
import markdown

from configparser import ConfigParser

from pybtex.database import parse_file as parse_bib_file
from pybtex.database import BibliographyData

from litman.find_dups import check_for_duplicates
from litman.html_template import html_tpl
from litman.gen_journal_abbr_name import load_journal_abbr_name_map
from litman.doi_lookup import normalize_doi

logger = getLogger('litman')


def _check_person(entry_key, person):
    for name in person.first_names + person.middle_names:
        if len(name) >= 2 and name == name.upper() and '-' not in name:
            print(f'{entry_key} All CAPS: {person}')
        if name.endswith('.') or name.endswith(','):
            print(f'{entry_key} Final punctuation: {person}')
    if person.last_names[0].startswith('others'):
        print(f'{entry_key} contains "others"')


def _check_people(bib_data):
    people = defaultdict(list)
    people_to_entry = {}
    for k, entry in bib_data.entries.items():
        for person in entry.persons['author']:
            people[' '.join(person.last_names)].append(person)
            people_to_entry[' '.join(person.last_names)] = entry
            _check_person(k, person)

    mismatches = []
    for lastname, persons in people.items():
        if len(persons) > 1:
            for p1, p2 in itertools.combinations(persons, 2):
                if p1.last_names[0] == 'others' or p2.last_names[0] == 'others':
                    continue
                if p1.first_names[0][0] != p2.first_names[0][0]:
                    # Different first letter of first name; unlikely to be same person.
                    continue
                if p1.first_names + p1.middle_names != p2.first_names + p2.middle_names:
                    # Converting to string here means set(...) will work.
                    mismatches.append(f'NAME MISMATCH: {p1} <-> {p2}')
    for mismatch in sorted(set(mismatches)):
        print(mismatch)

    return people, people_to_entry


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
    cites_dict = {}

    for citestring in ['cite', 'citet', 'citep', 'citeaffixed', 'citeasnoun']:
        pattern = '\\\\' + citestring + '.*?\{(?P<cite>.*?)\}'
        new_cites = []
        for l in lines:
            citestring_cites = [m.group('cite') for m in re.finditer(pattern, l)]
            # Flatten list: https://stackoverflow.com/a/953097/54557
            citestring_cites = list(itertools.chain.from_iterable([c.split(',') for c in citestring_cites]))
            citestring_cites = [c.strip() for c in citestring_cites]
            new_cites.extend(citestring_cites)

        cites_dict[citestring] = list(set(new_cites))
        cites.extend(new_cites)

    cites = list(set(cites))

    logger.debug(tex_fn)
    logger.debug(cites)
    return cites, cites_dict

def _read_tags(tags_fn):
    with open(tags_fn, 'r') as f:
        tags = list(map(str.strip, f.read().split(',')))
    return tags


def _add_tag(tags_fn, tag):
    if os.path.exists(tags_fn):
        tags = _read_tags(tags_fn)
        tags.append(tag)
    else:
        tags = [tag]

    tags = sorted(list(set(tags)))
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

        self.pdf_fn = os.path.join(self.litman.lit_dir, name, f'{name}.pdf')
        self.bib_fn = os.path.join(self.litman.lit_dir, name, 'ref.bib')
        self.extracted_text_fn = os.path.join(self.litman.lit_dir, name, 'extracted_text.txt')
        self.title_fn = os.path.join(self.litman.lit_dir, name, 'title.txt')
        self.tags_fn = os.path.join(self.litman.lit_dir, name, 'tags.txt')
        self.notes_fn = os.path.join(self.litman.lit_dir, name, 'notes.md')
        self.notes_html_fn = os.path.join(self.litman.lit_dir, name, 'notes.html')
        self.summary_fn = os.path.join(self.litman.lit_dir, name, 'summary.json')

        self.has_title_file = os.path.exists(self.title_fn)
        self.has_summary = os.path.exists(self.summary_fn)
        self.has_pdf = os.path.exists(self.pdf_fn)
        self.has_bib = os.path.exists(self.bib_fn)
        self.has_extracted_text = os.path.exists(self.extracted_text_fn)
        self.has_tags = os.path.exists(self.tags_fn)
        self.has_notes = os.path.exists(self.notes_fn)

        if self.has_tags:
            self.tags = _read_tags(self.tags_fn)
        else:
            self.tags = []

        self._bib_loaded = False
        self._extracted_text_loaded = False
        self._notes_loaded = False

    def __repr__(self):
        return f"LitItem({self.litman.__repr__()}, '{self.name}')"

    def _load_bib(self):
        if self.has_bib:
            bib_data = parse_bib_file(self.bib_fn)
            assert len(bib_data.entries.keys()) == 1
            self._bib_name = list(bib_data.entries.keys())[0]
            self._bib_entry = list(bib_data.entries.values())[0]
        else:
            self._bib_name = None
            self._bib_entry = None
        self._bib_loaded = True

    def bib_name(self):
        if not self._bib_loaded:
            self._load_bib()
        return self._bib_name

    def bib_entry(self):
        if not self._bib_loaded:
            self._load_bib()
        return self._bib_entry

    def extracted_text(self):
        if not self._extracted_text_loaded:
            self._load_extracted_text()
        return self._extracted_text

    def _load_extracted_text(self):
        if self.has_extracted_text:
            with open(self.extracted_text_fn, 'r') as f:
                self._extracted_text = f.read()
        else:
            self._extracted_text = None
        self._extracted_text_loaded = True

    def notes(self):
        if not self._notes_loaded:
            self._load_notes()
        return self._notes

    def open_notes(self):
        notes = self.notes()
        if notes:
            with open(self.notes_html_fn, 'w') as f:
                f.write(html_tpl.format(title=self.name, body=markdown.markdown(notes)))
            webbrowser.open(self.notes_html_fn)
        else:
            print(f'DOI for {self.name} not known')

    def _load_notes(self):
        if self.has_notes:
            with open(self.notes_fn, 'r') as f:
                self._notes = f.read()
        else:
            self._notes = None
        self._notes_loaded = True

    def doi_url(self):
        if self.has_bib:
            fields = self.bib_entry().fields
            if 'doi' in fields:
                doi = fields['doi']
                doi = doi.replace('\\', '')
                return 'https://doi.org/' + doi
        return ''

    def open_doi(self):
        doi_url = self.doi_url()
        if doi_url:
            webbrowser.open(doi_url)
        else:
            print(f'DOI for {self.name} not known')

    def title(self):
        if self.has_bib:
            return self.bib_entry().fields['title']
        elif os.path.exists(self.title_fn):
            with open(self.title_fn, 'r') as f:
                return f.read().strip()
        else:
            return ''

    def year(self):
        years = []

        if self.has_bib:
            bib_year = int(self.bib_entry().fields['year'])
            years.append(bib_year)
        name_year = re.match('\D*(?P<year>\d*)\D*', self.name).group('year')
        if len(name_year) != 4:
            logger.debug(f'{self.name}: Year {name_year} in wrong format')
        else:
            name_year = int(name_year)
            years.append(name_year)

        if years[1:] != years[:-1]:
            logger.warn(f'{self.name}: Elements not all equal: {years}')

        if years:
            return years[0]
        else:
            return -999

    def _get_bib_authors(self):
        authors = self.bib_entry().persons['author']
        # returns last names of authors.
        return [a.last()[0] for a in authors]

    def get_authors(self):
        if self.has_bib:
            return self._get_bib_authors()
        else:
            return ''

    def authors(self):
        return ', '.join(self.get_authors())

    def add_tag(self, tag):
        _add_tag(self.tags_fn, tag)
        self.tags = _read_tags(self.tags_fn)

    def set_title(self, title):
        if os.path.exists(self.title_fn):
            logger.error('Title should not already be set!')
            raise Exception('Title should not already be set!')

        logger.info(f'Setting title: {title}')
        with open(self.title_fn, 'w') as f:
            f.write(title)

    def add_pdf(self, pdf_fn):
        _extract_text(pdf_fn, self.extracted_text_fn)

        pdf_symlink = self.pdf_fn
        if not os.path.exists(self.pdf_fn):
            os.symlink(pdf_fn, self.pdf_fn)

    def add_bib_data(self, bib_name, bib_entry):
        single_bib_data = BibliographyData({bib_name: bib_entry})
        single_bib_data.to_file(self.bib_fn)
        self._bib_loaded = False

    def set_field(self, field, value):
        if not self.has_bib:
            raise Exception(f'{self.name} has no bib entry to set {field} on')
        # The DOI is written surgically rather than via pybtex: pybtex's BibTeX
        # writer LaTeX-escapes special chars (_ -> \_, % -> \%) and its reader
        # does not unescape, so a DOI round-tripped through pybtex accumulates
        # backslashes and ceases to be a valid DOI. Insert/replace the raw line.
        if field == 'doi':
            self._set_doi_text(value)
            return
        entry = self.bib_entry()
        entry.fields[field] = value
        self.add_bib_data(self.bib_name(), entry)

    def _set_doi_text(self, doi):
        doi = normalize_doi(doi)
        with open(self.bib_fn, 'r') as f:
            text = f.read()
        line_re = re.compile(r'(?im)^[ \t]*doi[ \t]*=[ \t]*".*?"(,?)[ \t]*$')
        if line_re.search(text):
            text = line_re.sub(lambda m: f'    doi = "{doi}"{m.group(1)}', text)
        else:
            # Insert as the first field, just after the `@type{key,` line.
            text = re.sub(r'(?m)^(@\w+\{[^\n,]+,)[ \t]*$',
                          lambda m: f'{m.group(1)}\n    doi = "{doi}",', text, count=1)
        with open(self.bib_fn, 'w') as f:
            f.write(text)
        self._bib_loaded = False

    def write_summary(self, summary):
        import json
        with open(self.summary_fn, 'w') as f:
            json.dump(summary, f, indent=2)
        self.has_summary = True

    def read_summary(self):
        import json
        if not self.has_summary:
            return None
        with open(self.summary_fn, 'r') as f:
            return json.load(f)

    def display(self):
        if self.has_pdf:
            Popen(['evince', self.pdf_fn])
        else:
            logger.info(f'item {self.name} has no PDF')

    def rename_tag(self, tag_old, tag_new):
        if tag_old in self.tags:
            os.remove(self.tags_fn)
            for tag in self.tags:
                if tag == tag_old:
                    self.add_tag(tag_new)
                else:
                    self.add_tag(tag)



class LitMan:
    def __init__(self, litman_dir):
        self.litman_dir = litman_dir
        self.lit_dir = os.path.join(litman_dir, 'literature')
        # Generated/aggregate files (word index, journal map, theme report).
        self.data_dir = os.path.join(litman_dir, 'data')
        # Per-project symlink collections.
        self.projects_dir = os.path.join(litman_dir, 'projects')
        self.items = []
        self._tags = Counter()
        self._scanned = False

    def data_path(self, *parts):
        os.makedirs(self.data_dir, exist_ok=True)
        return os.path.join(self.data_dir, *parts)

    def __repr__(self):
        return f"LitMan('{self.lit_dir}')"


    def import_pdf(self, import_dir, tags=[], project=None):
        if project == os.path.basename(self.lit_dir):
            raise ValueError(f'Invalid name for project: {project}')

        import_dir = os.path.join(os.getcwd(), import_dir)
        import_dir = _remove_periods(import_dir)
        hashes = check_for_duplicates([import_dir])

        for files in hashes.values():
            pdf_fns = [f for f in files if f.endswith('pdf')]
            for pdf_fn in pdf_fns:
                logger.info(f'Importing: {pdf_fn}')
                pdf_basename = os.path.basename(pdf_fn)
                item_name = os.path.splitext(pdf_basename)[0]

                try:
                    item = self.get_item(item_name)
                    logger.info(f'Item {item_name} already exists')
                except ItemNotFound:
                    logger.info(f'Creating item {item_name}')
                    item = self.create_item(item_name)

                tags = os.path.split(os.path.relpath(pdf_fn, import_dir))[0].split(os.sep) + tags
                for tag in tags:
                    if tag:
                        item.add_tag(tag)

                if not item.has_pdf:
                    item.add_pdf(pdf_fn)

                if project:
                    project_dir = os.path.join(self.projects_dir, project)
                    os.makedirs(project_dir, exist_ok=True)
                    symlink = os.path.join(project_dir, item_name)
                    rel_target = os.path.relpath(os.path.join(self.lit_dir, item_name), project_dir)
                    if not os.path.exists(symlink):
                        os.symlink(rel_target, symlink)

    def import_bib(self, import_dir, tag=None):
        import_dir = os.path.join(os.getcwd(), import_dir)
        import_dir = _remove_periods(import_dir)
        bib_fns = _scan_dirs(import_dir, ext='.bib')
        for bib_fn in bib_fns:
            logger.info(f'Importing: {bib_fn}')
            bib_data = parse_bib_file(bib_fn)

            for bib_name, bib_entry in bib_data.entries.items():
                item_name = bib_name

                try:
                    item = self.get_item(item_name)
                    logger.info(f'Item {item_name} already exists')
                except ItemNotFound:
                    logger.info(f'Creating item {item_name}')
                    item = self.create_item(item_name)

                if tag and tag.lower() != 'references':
                    item.add_tag(tag)

                if not item.has_bib:
                    item.add_bib_data(bib_name, bib_entry)

    def create_item(self, name):
        if not self._scanned:
            self._scan()
        if os.path.exists(os.path.join(self.lit_dir, name)):
            raise Exception(f'Item {name} already exists')

        os.makedirs(os.path.join(self.lit_dir, name))

        item = LitItem(self, name)
        self.items.append(item)
        return item

    def get_item(self, item_name, allow_partial=False):
        if self._scanned and item_name in self._item_cache:
            item = self._item_cache[item_name]
        else:
            try:
                item = LitItem(self, item_name)
            except ItemNotFound:
                if allow_partial:
                    self._scan()
                    potential_items = [item for item in self.items
                                       if item_name == item.name[:len(item_name)]]
                    if len(potential_items) == 1:
                        item = potential_items[0]
                    elif len(potential_items) > 1:
                        item_str = ", ".join([item.name for item in potential_items])
                        msg = f'Multiple items matching {item_name} found: {item_str}'
                        raise ItemNotFound(msg)
                    else:
                        raise ItemNotFound(f'item {item_name} not found')
                else:
                    raise ItemNotFound(f'item {item_name} not found')
        return item

    def get_items(self, tag_filter=None, has_title_file=None,
                  has_pdf=None, has_bib=None, has_extracted_text=None):
        self._scan()
        items = [item for item in self.items]
        if tag_filter:
            items = [item for item in items if tag_filter in item.tags]
        if has_title_file is not None:
            items = [item for item in items if item.has_title_file == has_title_file]
        if has_pdf is not None:
            items = [item for item in items if item.has_pdf == has_pdf]
        if has_bib is not None:
            items = [item for item in items if item.has_bib == has_bib]
        if has_extracted_text is not None:
            items = [item for item in items if item.has_extracted_text == has_extracted_text ]
        return items

    def get_tags(self):
        self._scan()
        return self._tags.most_common()

    def list_items(self, tag_filter=None, sort_on=['name'], reverse=False, **kwargs):
        self._scan()
        items = self.get_items(tag_filter, **kwargs)

        for sort in sort_on:
            if sort == 'year':
                items = sorted(items, key=lambda item: item.year())
            else:
                items = sorted(items, key=lambda item: getattr(item, sort))

        if reverse:
            items = items[::-1]

        # Handle a broken pipe:
        signal(SIGPIPE, SIG_DFL)

        fmt = f'{{0:<{self.max_itemname_len + 1}}}: {{1:<20}} {{2:>4}} {{3}}/{{4}} {{5:<50}} {{6}}'
        print(fmt.format(*['item_name', 'authors', 'year', 'P', 'B', 'title', 'tags']))
        print('=' * len(fmt.format(*['item_name', 'authors', 'year', 'P', 'B', 'title', 'tags'])))

        def bstr(b):
            return 'T' if b else 'F'

        for item in items:
            if not tag_filter or tag_filter in item.tags:
                print(fmt.format(item.name, item.authors()[:20], item.year(),
                                 bstr(item.has_pdf), bstr(item.has_bib),
                                 item.title()[:50], item.tags))

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
            matches = list(re.finditer(m, item.extracted_text()))
            if matches:
                all_matches.append((item, matches))
                logger.debug(f'found matches for {item.name}')
                for match in matches:
                    logger.debug(f'matches: {matches}')
        return all_matches

    def _check_journals(self, bib_data):
        jmap = load_journal_abbr_name_map(self.data_dir)
        # entry is the entry read in from the bib file.
        for k, entry in bib_data.entries.items():
            item = self.get_item(k)
            # item_entry is the one in the litman database.
            # This is the one to check.
            item_entry = item.bib_entry()
            if 'journal' in item_entry.fields and item_entry.fields['journal'] not in jmap:
                logger.warning(f'UNRECOGNIZED JOURNAL: {k}: {item_entry.fields["journal"]}')

    def _check_fields(self, bib_data):
        for k, entry in bib_data.entries.items():
            if 'doi' not in entry.fields:
                logger.warning(f'NO DOI: {k}')

    def check_bib(self, bib_fn):
        bib_data = parse_bib_file(bib_fn)
        _check_people(bib_data)
        self._check_journals(bib_data)
        self._check_fields(bib_data)

    def items_missing_doi(self, tag_filter=None, articles_only=False):
        items = self.get_items(tag_filter, has_bib=True)
        missing = []
        for item in items:
            entry = item.bib_entry()
            doi = entry.fields['doi'].strip() if 'doi' in entry.fields else ''
            if doi:
                continue
            if articles_only and entry.type != 'article':
                continue
            missing.append(item)
        return missing

    def cleanup_report(self, tag_filter=None):
        items = self.get_items(tag_filter, has_bib=True)

        bibname_to_items = defaultdict(list)
        people = defaultdict(set)
        journals = defaultdict(list)
        doi_fixes = []
        missing_doi = 0

        for item in items:
            entry = item.bib_entry()
            bibname_to_items[item.bib_name()].append(item.name)

            doi = entry.fields['doi'].strip() if 'doi' in entry.fields else ''
            if not doi:
                missing_doi += 1
            else:
                fixed = normalize_doi(doi)
                if fixed != doi:
                    doi_fixes.append((item.name, doi, fixed))

            if 'journal' in entry.fields and entry.fields['journal'].strip():
                j = entry.fields['journal'].strip()
                journals[re.sub(r'[^a-z0-9]', '', j.lower())].append(j)

            for person in entry.persons.get('author', []):
                last = ' '.join(person.last_names)
                first = ' '.join(person.first_names + person.middle_names)
                if first:
                    people[last].add(first)

        print('=== DOI FORMAT ISSUES (url prefixes / LaTeX escaping) ===')
        for name, old, new in sorted(doi_fixes):
            print(f'  {name}: {old!r} -> {new!r}')
        print(f'  ({len(doi_fixes)} DOIs would be normalized)\n')

        print('=== JOURNAL NAME VARIANTS ===')
        njv = 0
        for key, vs in sorted(journals.items()):
            uniq = set(vs)
            if len(uniq) > 1:
                canon = max(uniq, key=lambda v: (vs.count(v), sum(c.isupper() for c in v)))
                print(f"  {sorted(uniq)} -> '{canon}'")
                njv += 1
        print(f'  ({njv} journals with multiple spellings)\n')

        print('=== AUTHOR GIVEN-NAME VARIANTS (same surname, same first initial) ===')
        nav = 0
        for last, firsts in sorted(people.items()):
            if last.lower() == 'others':
                continue
            fs = sorted(firsts)
            if len(fs) > 1 and len({f[0] for f in fs}) == 1:
                print(f'  {last}: {fs}')
                nav += 1
        print(f'  ({nav} surnames with inconsistent given-name forms; review by hand -- '
              f'distinct people can share a surname)\n')

        print('=== DUPLICATE CITE KEYS (same key in >1 item dir) ===')
        ndup = 0
        for bibname, names in sorted(bibname_to_items.items()):
            if len(names) > 1:
                print(f'  {bibname}: {names}')
                ndup += 1
        print(f'  ({ndup} duplicated cite keys)\n')

        self._formatting_report(items)

        print(f'=== SUMMARY: {len(items)} items with a bib; {missing_doi} missing a DOI '
              f'(run `litman find-doi` to fill them) ===')

    def _formatting_report(self, items):
        delim = Counter()
        odd_type, single_dash, key_mismatch, overesc = [], [], [], []
        for item in items:
            with open(item.bib_fn) as f:
                t = f.read()
            q = len(re.findall(r'=\s*"', t))
            b = len(re.findall(r'=\s*\{', t))
            delim['braces' if b > q else 'quotes'] += 1
            m = re.search(r'^@(\w+)\{([^,]+),', t, re.M)
            if m:
                if not m.group(1).islower():
                    odd_type.append((item.name, m.group(1)))
                if m.group(2).strip() != item.name:
                    key_mismatch.append((item.name, m.group(2).strip()))
            mp = re.search(r'pages\s*=\s*["{]([^"}]*)', t, re.I)
            if mp and '--' not in mp.group(1) and re.search(r'\d-\d', mp.group(1)):
                single_dash.append((item.name, mp.group(1)))
            if re.search(r'\\{2,}[_%&#$]', t):
                overesc.append(item.name)

        print('=== FORMATTING ===')
        print(f'  value delimiter (dominant per file): {dict(delim)}')
        print(f'  non-lowercase @type ({len(odd_type)}): {odd_type}')
        print(f'  single-dash page ranges ({len(single_dash)}): {single_dash[:8]}'
              + (' ...' if len(single_dash) > 8 else ''))
        print(f'  over-escaped (\\\\x) fields ({len(overesc)}): {overesc}')
        print(f'  citekey != dirname -- MANUAL REVIEW ({len(key_mismatch)}): {key_mismatch}')
        print('  (entry-case, page-dash and over-escaping are fixed by `litman normalize`)\n')

    def _journal_canonical_map(self, items):
        # Map normalized journal name -> preferred spelling (most frequent, then most capitals).
        journals = defaultdict(list)
        for item in items:
            entry = item.bib_entry()
            if 'journal' in entry.fields and entry.fields['journal'].strip():
                j = entry.fields['journal'].strip()
                journals[re.sub(r'[^a-z0-9]', '', j.lower())].append(j)
        canon = {}
        for key, vs in journals.items():
            if len(set(vs)) > 1:
                canon[key] = max(set(vs), key=lambda v: (vs.count(v), sum(c.isupper() for c in v)))
        return canon

    def normalize(self, apply=False, tag_filter=None):
        items = self.get_items(tag_filter, has_bib=True)
        canon = self._journal_canonical_map(items)

        n_doi = n_journal = n_fmt = 0
        for item in items:
            entry = item.bib_entry()

            if 'doi' in entry.fields and entry.fields['doi'].strip():
                old = entry.fields['doi']
                new = normalize_doi(old)
                if new != old:
                    print(f'  DOI  {item.name}: {old!r} -> {new!r}')
                    if apply:
                        item.set_field('doi', new)
                    n_doi += 1

            if 'journal' in entry.fields and entry.fields['journal'].strip():
                j = entry.fields['journal'].strip()
                key = re.sub(r'[^a-z0-9]', '', j.lower())
                if key in canon and j != canon[key]:
                    print(f'  JOUR {item.name}: {j!r} -> {canon[key]!r}')
                    if apply:
                        item.set_field('journal', canon[key])
                    n_journal += 1

            n_fmt += self._normalize_formatting(item, apply)

        verb = 'updated' if apply else 'to update (dry run -- pass --apply to write)'
        print(f'\n{n_doi} DOI(s), {n_journal} journal name(s), {n_fmt} formatting fix(es) {verb}.')

    def _normalize_formatting(self, item, apply):
        # Surgical, text-level fixes that must NOT go through pybtex (which would
        # re-escape special chars). Lowercase @type, page-range -- , and collapse
        # over-escaped backslash runs (\\& -> \&) down to a single LaTeX escape.
        with open(item.bib_fn) as f:
            orig = f.read()
        text = orig
        changes = []

        def _type(m):
            if not m.group(1).islower():
                changes.append(f'@{m.group(1)} -> @{m.group(1).lower()}')
                return '@' + m.group(1).lower() + '{'
            return m.group(0)
        text = re.sub(r'^@(\w+)\{', _type, text, count=1, flags=re.M)

        def _pages(m):
            val = m.group(2)
            if '--' not in val and re.search(r'\d-\d', val):
                new = re.sub(r'(\d)-(\d)', r'\1--\2', val)
                changes.append(f'pages {val} -> {new}')
                return m.group(1) + new + m.group(3)
            return m.group(0)
        text = re.sub(r'(pages\s*=\s*["{])([^"}]*)(["}])', _pages, text, flags=re.I)

        collapsed = re.sub(r'\\{2,}([_%&#$])', r'\\\1', text)
        if collapsed != text:
            changes.append('collapsed over-escaped backslashes')
            text = collapsed

        if text != orig:
            for c in changes:
                print(f'  FMT  {item.name}: {c}')
            if apply:
                with open(item.bib_fn, 'w') as f:
                    f.write(text)
            return 1
        return 0

    def _nice_journal_name_from_journal(self, entry, caps_name):
        caps_name = caps_name.split()
        nice_name = []
        for w in caps_name:
            if w in ['FOR', 'OF', 'IN', 'THE', 'AND']:
                nice_name.append(w.lower())
            elif w in ['IEEE']:
                nice_name.append(w)
            else:
                nice_name.append(w.title())
        entry.fields['journal'] = ' '.join(nice_name)

    def _nice_title_from_journal(self, key, entry):
        if key in ['lin2007double', 'rayleigh1916lix', 'grandpeix2010density1']:
            return

        raw_title = entry.fields['title']
        nice_title = []
        for w in raw_title.split():
            if w.lower() in ['for', 'of', 'in', 'the', 'by', 'from', 'a', 'an', 'and', 'or', 'on',
                             'to', 'over', 'with', 'as', 'during', 'when', 'is', 'are', 'at',
                             'between', 'their', 'its', 'above']:
                nice_title.append(w.lower())
            elif len(w) >= 2 and sum(1 for c in w if c.isupper()) >= 2:
                nice_title.append(w)
            else:
                nice_title.append(w.title())
        logger.info(f'{raw_title} ->')
        nice_title = ' '.join(nice_title)
        nice_title = '{' + nice_title[0].upper() + nice_title[1:] + '}'
        logger.info(f'{nice_title}')
        entry.fields['title'] = nice_title


    def _nicify_bib(self, bib_data, no_rename_title):
        jmap = load_journal_abbr_name_map(self.data_dir)
        for key, entry in bib_data.entries.items():
            entry.fields['title'] = '{' + entry.fields['title'] + '}'
            if not no_rename_title:
                self._nice_title_from_journal(key, entry)
            if 'journal' in entry.fields and entry.fields['journal'] in jmap:
                self._nice_journal_name_from_journal(entry, jmap[entry.fields['journal']])

    def gen_bib_for_tag(self, tag_filter, outfile, dry_run, no_rename_title):
        items = self.get_items(tag_filter)
        bib_data = self._create_bib([item.name for item in items])
        self._nicify_bib(bib_data, no_rename_title)
        if dry_run:
            print(bib_data.to_string('bibtex'))
        else:
            bib_data.to_file(outfile)
        return bib_data

    def gen_bib_for_tex_dir(self, tex_dir, outfile, dry_run, no_rename_title):
        tex_fns = _scan_dirs(tex_dir, '.tex')
        return self.gen_bib_for_tex_fns(tex_fns, outfile, dry_run, no_rename_title)

    def gen_bib_for_tex_fns(self, tex_fns, outfile, dry_run, no_rename_title):
        all_cites = []
        for tex_fn in tex_fns:
            all_cites_for_file, _ = _get_cites_from_tex(tex_fn)
            all_cites.extend(all_cites_for_file)
        all_cites = list(set(all_cites))
        bib_data = self._create_bib(all_cites)
        self._nicify_bib(bib_data, no_rename_title)

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
                logger.info(f'Creating bib entry: {item.bib_name()}')
                bib_data_dict[item.bib_name()] = item.bib_entry()
        return BibliographyData(bib_data_dict)


    def stats(self):
        if not self._scanned:
            self._scan()
        stat_counters = defaultdict(Counter)

        for item in self.get_items():
            if item.has_bib:
                stat_counters['year'][item.year()] += 1
                if 'journal' in item.bib_entry().fields:
                    stat_counters['journal'][item.bib_entry().fields['journal'].lower()] += 1

            for tag in item.tags:
                stat_counters['tag'][tag] += 1
            for author in item.get_authors():
                if author:
                    stat_counters['author'][author] += 1
        self._stat_counters = stat_counters

        return stat_counters

    def _scan(self):
        if self._scanned:
            return
        self._scanned = True
        self.max_itemname_len = 0

        self._item_cache = {}
        self._tags = Counter()

        for item_dir in os.listdir(self.lit_dir):
            if item_dir[0] == '.':
                continue
            if not os.path.isdir(os.path.join(self.lit_dir, item_dir)):
                continue
            logger.debug(f'  adding item_dir {item_dir}')
            item = LitItem(self, item_dir)
            for tag in item.tags:
                self._tags[tag] += 1
            self.max_itemname_len = max(self.max_itemname_len, len(item.name))
            self.items.append(item)
            self._item_cache[item.name] = item

    def rename_tag(self, tag_old, tag_new):
        self._scan()
        for item in self.get_items():
            item.rename_tag(tag_old, tag_new)
