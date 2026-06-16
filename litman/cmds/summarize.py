"""Summarize each paper's extracted text with Claude (Batch API)"""
import os
import json
import time
from logging import getLogger

logger = getLogger('litman.summarize')

ARGS = [
    (['--tag-filter', '-t'], {'default': None, 'help': 'Only items carrying this tag'}),
    (['--force', '-f'], {'action': 'store_true',
                         'help': 'Re-summarize items that already have summary.json'}),
    (['--limit'], {'type': int, 'default': None, 'help': 'Cap number of items (e.g. a pilot run)'}),
    (['--poll-interval'], {'type': int, 'default': 30, 'help': 'Seconds between batch status checks'}),
]


def _state_fn(litman):
    # Lets an interrupted run resume the same batch instead of resubmitting.
    return os.path.join(litman.litman_dir, '.summarize_batch.json')


def main(litman, args):
    try:
        import anthropic  # noqa: F401
    except ImportError:
        print('summarize needs the anthropic package: `pip install -e .[ai]` and set ANTHROPIC_API_KEY')
        return
    from litman import ai

    state_fn = _state_fn(litman)

    if os.path.exists(state_fn):
        with open(state_fn) as f:
            state = json.load(f)
        batch_id = state['batch_id']
        index_to_name = state['items']
        print(f'Resuming batch {batch_id} ({len(index_to_name)} items)')
    else:
        items = litman.get_items(args.tag_filter, has_extracted_text=True)
        if not args.force:
            items = [it for it in items if not it.has_summary]
        if args.limit:
            items = items[:args.limit]
        if not items:
            print('Nothing to summarize (all items already have a summary.json).')
            return
        requests, index_to_name = ai.build_summary_requests(items)
        print(f'Submitting Batch job for {len(requests)} items (model {ai.SUMMARY_MODEL})...')
        batch_id = ai.submit_batch(requests)
        with open(state_fn, 'w') as f:
            json.dump({'batch_id': batch_id, 'items': index_to_name}, f)
        print(f'Batch {batch_id} submitted (resumable; state in {state_fn}).')

    while True:
        batch = ai.batch_status(batch_id)
        if batch.processing_status == 'ended':
            break
        rc = batch.request_counts
        print(f'  {batch.processing_status}: processing={rc.processing} '
              f'succeeded={rc.succeeded} errored={rc.errored}')
        time.sleep(args.poll_interval)

    written = errors = 0
    for custom_id, summary, err in ai.iter_batch_results(batch_id):
        name = index_to_name[int(custom_id[1:])]
        if summary is None:
            errors += 1
            logger.warning(f'{name}: {err}')
            continue
        litman.get_item(name).write_summary(summary)
        written += 1

    print(f'Wrote {written} summaries, {errors} errors.')
    os.remove(state_fn)
