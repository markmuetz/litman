"""Build a word-frequency / inverted index across all extracted text.

Produces a controlled vocabulary of the corpus: which terms appear, how often,
and in which items. Useful as a discovery aid -- given a vague query, look up
the real terms (and their frequencies) before grepping the extracted_text.txt
files. Pure-local; no API calls.
"""
import re
from collections import Counter, defaultdict

# A small, generic English stopword list plus a few PDF/academic-boilerplate words.
STOPWORDS = set((
    'the of and to in a is for that this with are be as by on we it an at from or '
    'which can has have not but these their its also been was were will more such '
    'than then they our using used use one two between into may both each other '
    'all any some when where while if so no there here over under above below about '
    'figure table section et al fig eq cf ie eg vol pp doi http https www abstract '
    'introduction conclusion conclusions references acknowledgements appendix '
    'however therefore thus hence within across during given per via due based '
    'results method methods data model models study studies paper show shown shows'
).split())

WORD_RE = re.compile(r"[a-z][a-z'\-]{2,}")


def build_word_index(items, min_count=3):
    """Return {word: {count, docs, items: [...]}} for words with total >= min_count."""
    freq = Counter()
    doc_freq = Counter()
    inverted = defaultdict(list)

    for item in items:
        text = item.extracted_text()
        if not text:
            continue
        local = Counter()
        for m in WORD_RE.finditer(text.lower()):
            w = m.group().strip("-'")
            if len(w) < 3 or w in STOPWORDS:
                continue
            local[w] += 1
        for w, c in local.items():
            freq[w] += c
            doc_freq[w] += 1
            inverted[w].append(item.name)

    index = {}
    for w, c in freq.items():
        if c < min_count:
            continue
        index[w] = {'count': c, 'docs': doc_freq[w], 'items': sorted(inverted[w])}
    return index
