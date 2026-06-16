"""Synthesize recurring themes across all paper summaries with Claude"""
import os


ARGS = [
    (['--tag-filter', '-t'], {'default': None, 'help': 'Only items carrying this tag'}),
    (['--outfile', '-o'], {'default': None,
                           'help': 'Write report here (default: <litman_dir>/themes.md)'}),
]


def main(litman, args):
    try:
        import anthropic  # noqa: F401
    except ImportError:
        print('themes needs the anthropic package: `pip install -e .[ai]` and set ANTHROPIC_API_KEY')
        return
    from litman import ai

    items = litman.get_items(args.tag_filter)
    summaries = [(it.name, it.read_summary()) for it in items if it.has_summary]
    if not summaries:
        print('No summaries found. Run `litman summarize` first.')
        return

    print(f'Synthesizing themes from {len(summaries)} summaries (model {ai.THEMES_MODEL})...')
    report = ai.synthesize_themes(summaries)

    outfile = args.outfile or litman.data_path('themes.md')
    with open(outfile, 'w') as f:
        f.write(report)
    print(f'Wrote theme report -> {outfile}\n')
    print(report)
