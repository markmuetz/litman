"""Find missing DOIs via CrossRef (dry run by default; --apply writes them)"""
import time
from logging import getLogger

from litman.doi_lookup import crossref_lookup, parse_report
from litman.litman import load_config, ItemNotFound

logger = getLogger('litman.find_doi')

ARGS = [
    (['item_name'], {'nargs': '?', 'help': 'Single item to look up (default: all missing a DOI)'}),
    (['--tag-filter', '-t'], {'help': 'Only items carrying this tag', 'default': None}),
    (['--articles-only', '-A'], {'help': 'Only @article entries', 'action': 'store_true'}),
    (['--apply', '-a'], {'help': 'Write CONFIDENT DOIs into ref.bib', 'action': 'store_true'}),
    (['--apply-from'], {'help': 'Apply DOIs from a saved dry-run report (no querying)', 'default': None}),
    (['--min-ratio', '-r'], {'help': 'Min title-match ratio to accept as CONFIDENT',
                             'type': float, 'default': 0.9}),
    (['--mailto', '-m'], {'help': 'Email for CrossRef polite pool', 'default': None}),
    (['--delay', '-d'], {'help': 'Seconds to wait between requests', 'type': float, 'default': 0.15}),
]


def main(litman, args):
    if args.apply_from:
        written = skipped = missing = 0
        with open(args.apply_from) as f:
            for name, ratio, doi in parse_report(f):
                if ratio < args.min_ratio or not doi:
                    skipped += 1
                    continue
                try:
                    litman.get_item(name, allow_partial=True).set_field('doi', doi)
                    written += 1
                except ItemNotFound:
                    missing += 1
                    print(f'  not found: {name}')
        print(f'Wrote {written} DOIs from {args.apply_from} '
              f'(skipped {skipped} below ratio {args.min_ratio}, {missing} not found).')
        return

    mailto = args.mailto
    if not mailto:
        _, conf = load_config()
        if conf and 'crossref_mailto' in conf:
            mailto = conf['crossref_mailto']

    if args.item_name:
        items = [litman.get_item(args.item_name, allow_partial=True)]
    else:
        items = litman.items_missing_doi(args.tag_filter, args.articles_only)

    print(f'{len(items)} item(s) missing a DOI'
          + (' (dry run)' if not args.apply else ' (--apply: writing CONFIDENT matches)'))

    counts = {'CONFIDENT': 0, 'MAYBE': 0, 'UNCERTAIN': 0, 'ERROR': 0, 'WRITTEN': 0}
    for i, item in enumerate(items):
        entry = item.bib_entry()
        title = entry.fields['title'].strip('{} ') if 'title' in entry.fields else ''
        year = entry.fields['year'] if 'year' in entry.fields else None
        try:
            doi, cr_title, ratio = crossref_lookup(title, year, mailto=mailto)
        except Exception as ex:
            counts['ERROR'] += 1
            print(f'[{i + 1}/{len(items)}] {item.name}: ERROR {ex}')
            continue

        status = 'CONFIDENT' if ratio >= args.min_ratio else ('MAYBE' if ratio >= 0.75 else 'UNCERTAIN')
        counts[status] += 1
        print(f'[{i + 1}/{len(items)}] {item.name}  {status} ({ratio:.2f})  {doi}')
        if status != 'CONFIDENT':
            print(f'      local: {title[:75]}')
            print(f'      cref : {cr_title[:75]}')

        if args.apply and status == 'CONFIDENT' and doi:
            item.set_field('doi', doi)
            counts['WRITTEN'] += 1

        time.sleep(args.delay)

    print('\nSummary: ' + ', '.join(f'{k}={v}' for k, v in counts.items()))
    if not args.apply:
        print('Dry run — no files changed. Re-run with --apply to write CONFIDENT DOIs.')
