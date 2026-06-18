"""Look up DOIs from titles via the CrossRef REST API.

CrossRef is free and needs no key; supplying an email (`mailto`) opts in to the
faster "polite pool". See https://api.crossref.org/swagger-ui/index.html
"""
import re
import difflib
from logging import getLogger

import requests

logger = getLogger('litman.doi_lookup')

CROSSREF_URL = 'https://api.crossref.org/works'


def _norm(s):
    # Reduce a title to lowercase alphanumerics for robust comparison.
    return re.sub(r'[^a-z0-9]', '', s.lower())


def normalize_doi(doi):
    """Strip URL prefixes and LaTeX escaping down to a bare DOI (10.xxxx/...)."""
    doi = doi.strip()
    doi = re.sub(r'^https?://(dx\.)?doi\.org/', '', doi, flags=re.IGNORECASE)
    doi = re.sub(r'^doi\.org/', '', doi, flags=re.IGNORECASE)
    doi = re.sub(r'^doi:\s*', '', doi, flags=re.IGNORECASE)
    # Old AMS-style DOIs are often stored with LaTeX escaping (\%3C, \_, ...).
    doi = doi.replace('\\%', '%').replace('\\_', '_').replace('\\&', '&').replace('\\', '')
    return doi.strip()


_REPORT_RE = re.compile(
    r'^\[\d+/\d+\]\s+(?P<name>\S+)\s+'
    r'(?P<status>CONFIDENT|MAYBE|UNCERTAIN)\s+\((?P<ratio>[\d.]+)\)\s*(?P<doi>\S+)?\s*$')


def parse_report(lines):
    """Parse the lines of a `find-doi` dry-run report; yield (name, ratio, doi)."""
    for line in lines:
        m = _REPORT_RE.match(line)
        if m:
            yield m.group('name'), float(m.group('ratio')), (m.group('doi') or '')


# A DOI is `10.<registrant>/<suffix>`; the suffix runs until whitespace or a
# closing delimiter. Trailing sentence punctuation is stripped by the caller.
DOI_RE = re.compile(r'\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+', re.IGNORECASE)


def find_doi_in_text(text, search_chars=4000):
    """Return the paper's own DOI from its extracted text, or '' if none found.

    Only the leading portion is searched: a paper prints its own DOI near the
    top (header/footer/first page), whereas DOIs further down belong to cited
    references.
    """
    m = DOI_RE.search(text[:search_chars])
    if not m:
        return ''
    return normalize_doi(m.group(0).rstrip('.,;)'))


def fetch_bibtex(doi, mailto=None, timeout=25):
    """Fetch a ready-made BibTeX entry for a DOI via CrossRef content negotiation.

    Returns the raw BibTeX string, or '' on failure.
    """
    doi = normalize_doi(doi)
    url = f'{CROSSREF_URL}/{doi}/transform/application/x-bibtex'
    params = {'mailto': mailto} if mailto else {}
    headers = {'User-Agent': f'litman-doi/1.0 (mailto:{mailto})' if mailto else 'litman-doi/1.0'}
    resp = requests.get(url, params=params, headers=headers, timeout=timeout)
    if resp.status_code != 200:
        logger.warning(f'CrossRef bibtex fetch for {doi} returned {resp.status_code}')
        return ''
    # CrossRef serves UTF-8 but omits the charset, so requests would assume
    # Latin-1 for text/* and mangle non-ASCII (en-dashes, accents).
    return resp.content.decode('utf-8', 'replace').strip()


def crossref_lookup(title, year=None, mailto=None, rows=3, timeout=25):
    """Best CrossRef match for a title.

    Returns (doi, crossref_title, ratio) where ratio is the similarity between
    the normalized local and CrossRef titles (1.0 == identical). Returns
    ('', '', 0.0) if nothing is found.
    """
    query = title if not year else f'{title} {year}'
    params = {'query.bibliographic': query, 'rows': rows}
    if mailto:
        params['mailto'] = mailto
    headers = {'User-Agent': f'litman-doi/1.0 (mailto:{mailto})' if mailto else 'litman-doi/1.0'}

    resp = requests.get(CROSSREF_URL, params=params, headers=headers, timeout=timeout)
    resp.raise_for_status()
    items = resp.json()['message']['items']
    if not items:
        return '', '', 0.0

    best = items[0]
    cr_titles = best.get('title') or ['']
    cr_title = cr_titles[0]
    ratio = difflib.SequenceMatcher(None, _norm(title), _norm(cr_title)).ratio() if cr_title else 0.0
    return normalize_doi(best.get('DOI', '')), cr_title, ratio
