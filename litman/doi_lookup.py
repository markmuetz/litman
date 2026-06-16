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
