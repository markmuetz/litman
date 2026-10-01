"""Synthesize recurring themes across all paper summaries with Claude"""
import os


ARGS = [
    (['--tag-filter', '-t'], {'default': None, 'help': 'Only items carrying this tag'}),
    (['--outfile', '-o'], {'default': None,
                           'help': 'Write report here (default: <litman_dir>/themes.md)'}),
    (['--update', '-u'], {'action': 'store_true',
                          'help': 'Fold papers missing from the existing report into it, '
                                  'rather than re-deriving every theme from scratch'}),
    (['--dry-run', '-n'], {'action': 'store_true',
                           'help': 'Report what would be sent, then stop (no API call)'}),
]


def main(litman, args):
    # Safe without the anthropic package: ai.py imports it lazily, per its docstring.
    from litman import ai

    outfile = args.outfile or litman.data_path('themes.md')

    items = litman.get_items(args.tag_filter, shareable=True)
    summaries = [(it.name, it.read_summary()) for it in items if it.has_summary]
    if not summaries:
        print('No summaries found. Run `litman summarize` first.')
        return

    report = None
    if args.update:
        if not os.path.exists(outfile):
            print(f'No existing report at {outfile}; synthesizing from scratch.')
        else:
            with open(outfile) as f:
                report = f.read()

    if report is not None:
        # An item is "new" if the report never cites its key. Keys the report
        # cites that no longer exist (deleted items) are simply ignored.
        covered = ai.keys_in_report(report)
        summaries = [(name, s) for name, s in summaries if name not in covered]
        if not summaries:
            print(f'{outfile} already covers every summarized item; nothing to update.')
            return
        names = [name for name, _ in summaries]
        shown = ', '.join(names[:12]) + (f', ... (+{len(names) - 12} more)'
                                         if len(names) > 12 else '')
        print(f'Updating {outfile} with {len(summaries)} uncited item(s): {shown}')
        # "Uncited" is not the same as "newly imported": a synthesis run places
        # papers into themes at its own discretion and routinely leaves some out.
        # Those stay uncited and are picked up here, so the first --update after a
        # full run is usually larger than the number of papers actually added.
    else:
        print(f'Synthesizing themes from {len(summaries)} summaries')

    if args.dry_run:
        print('--dry-run: stopping before the API call.')
        return

    try:
        import anthropic  # noqa: F401
    except ImportError:
        print('themes needs the anthropic package: `pip install -e .[ai]` and set ANTHROPIC_API_KEY')
        return

    print(f'Calling {ai.THEMES_MODEL}...')
    if report is not None:
        new_report = ai.update_themes(report, summaries)
    else:
        new_report = ai.synthesize_themes(summaries)

    with open(outfile, 'w') as f:
        f.write(new_report)
    print(f'Wrote theme report -> {outfile}\n')
    print(new_report)
