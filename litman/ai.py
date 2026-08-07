"""Use Claude to summarize extracted text and synthesize themes.

Requires the `anthropic` package (``pip install -e .[ai]``) and an
``ANTHROPIC_API_KEY`` in the environment. All anthropic imports are done lazily
so the rest of litman works without the dependency installed.

Map step (summarize, run once per paper): cheap and parallel -> Haiku + Batch.
Reduce step (themes, one call over all summaries): intelligence matters -> Opus.

`themes --update` re-uses the reduce step incrementally: the previous report plus
only the papers it doesn't already mention. Cheaper, but the real point is that
untouched themes keep their numbering and wording, so the diff shows just the
papers you added instead of a wholesale re-derivation.
"""
import re
from logging import getLogger

logger = getLogger('litman.ai')

SUMMARY_MODEL = 'claude-haiku-4-5'
THEMES_MODEL = 'claude-opus-4-8'

# Bound per-paper cost; abstract/intro/conclusion carry most of the topical signal.
MAX_TEXT_CHARS = 40000

SUMMARY_SCHEMA = {
    'type': 'object',
    'properties': {
        'topic': {'type': 'string',
                  'description': 'One concise sentence: what the paper is about.'},
        'summary': {'type': 'string',
                    'description': '2-4 sentences covering aims, methods and key findings.'},
        'keywords': {'type': 'array', 'items': {'type': 'string'},
                     'description': '4-8 lower-case topical keywords / themes.'},
    },
    'required': ['topic', 'summary', 'keywords'],
    'additionalProperties': False,
}

SUMMARY_INSTRUCTION = (
    'You are summarizing an academic paper for a personal literature database. '
    'The text below was extracted from a PDF and may be noisy (headers, references, '
    'OCR artifacts). Produce a concise, factual summary; do not invent details.\n\n'
    'Paper text:\n{text}'
)


def client():
    import anthropic
    return anthropic.Anthropic()


def _summary_text(item):
    text = (item.extracted_text() or '').strip()
    return text[:MAX_TEXT_CHARS]


def build_summary_requests(items, model=SUMMARY_MODEL):
    """Build (requests, index_to_name) for a Batches job. custom_id is an index
    (`i0`, `i1`, ...) so item names never run into custom_id length/charset limits."""
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    requests = []
    index_to_name = []
    for item in items:
        text = _summary_text(item)
        if not text:
            continue
        i = len(index_to_name)
        index_to_name.append(item.name)
        requests.append(Request(
            custom_id=f'i{i}',
            params=MessageCreateParamsNonStreaming(
                model=model,
                max_tokens=800,
                messages=[{'role': 'user',
                           'content': SUMMARY_INSTRUCTION.format(text=text)}],
                output_config={'format': {'type': 'json_schema', 'schema': SUMMARY_SCHEMA}},
            ),
        ))
    return requests, index_to_name


def submit_batch(requests):
    return client().messages.batches.create(requests=requests).id


def batch_status(batch_id):
    return client().messages.batches.retrieve(batch_id)


def iter_batch_results(batch_id):
    """Yield (custom_id, summary_dict_or_None, error_or_None)."""
    import json
    # Hold a reference for the whole iteration: results() streams lazily, and a
    # temporary client would be GC'd mid-stream, closing the socket (EBADF).
    c = client()
    for result in c.messages.batches.results(batch_id):
        if result.result.type == 'succeeded':
            msg = result.result.message
            text = next((b.text for b in msg.content if b.type == 'text'), '')
            try:
                yield result.custom_id, json.loads(text), None
            except json.JSONDecodeError as e:
                yield result.custom_id, None, f'bad json: {e}'
        else:
            yield result.custom_id, None, result.result.type


# Item keys as they appear in a generated report: `key` (what the model actually
# emits) or [key] (what the prompt asks for). Both are matched so --update keeps
# working if the output style drifts.
_REPORT_KEY_RE = re.compile(r'`([A-Za-z][\w.-]*)`|\[([A-Za-z][\w.-]*)\]')


def keys_in_report(report):
    """Item keys already cited in a theme report, as a set."""
    return {a or b for a, b in _REPORT_KEY_RE.findall(report)}


def _corpus_lines(summaries):
    lines = []
    for name, s in summaries:
        kw = ', '.join(s.get('keywords', []))
        lines.append(f'- [{name}] {s.get("topic", "")} | keywords: {kw}')
    return '\n'.join(lines)


def _run_themes_prompt(prompt, model, max_tokens):
    parts = []
    c = client()  # keep alive for the whole stream (see iter_batch_results)
    with c.messages.stream(
        model=model,
        max_tokens=max_tokens,
        thinking={'type': 'adaptive'},
        messages=[{'role': 'user', 'content': prompt}],
    ) as stream:
        for text in stream.text_stream:
            parts.append(text)
        final = stream.get_final_message()
    if final.stop_reason == 'max_tokens':
        # max_tokens caps thinking + text combined, so the report can be cut mid-word.
        logger.warning(f'themes report truncated at max_tokens={max_tokens}')
    return ''.join(parts)


def synthesize_themes(summaries, model=THEMES_MODEL, max_tokens=64000):
    """summaries: list of (item_name, summary_dict). Returns a markdown theme report."""
    prompt = (
        'Below is a list of papers from a personal literature library, one per line, '
        'each with a one-line topic and keywords. Identify the major recurring themes '
        'across the collection. For each theme: give it a short title, a one-sentence '
        'description, and list the item keys (the [name] tags) that belong to it. A '
        'paper may appear under more than one theme. End with a short note on the '
        "overall shape of the collection. Use markdown.\n\n"
        f'Papers ({len(summaries)}):\n{_corpus_lines(summaries)}'
    )
    return _run_themes_prompt(prompt, model, max_tokens)


def update_themes(report, new_summaries, model=THEMES_MODEL, max_tokens=64000):
    """Fold new papers into an existing theme report.

    report: the previous report's markdown. new_summaries: list of
    (item_name, summary_dict) for papers the report doesn't already cite.
    Returns the complete updated report.
    """
    prompt = (
        'Below is an existing theme report for a personal literature library, '
        'followed by papers that have been added to the library since it was '
        'written. Update the report to cover the new papers.\n\n'
        'Rules:\n'
        '- Return the COMPLETE updated report, not a diff or a summary of changes.\n'
        '- Preserve existing themes verbatim — same numbering, titles, descriptions '
        'and wording. The only edit to an existing theme is appending new item keys '
        'to its key list.\n'
        '- Add each new paper to whichever existing themes fit. A paper may appear '
        'under more than one theme, and a paper that fits nothing may be left out.\n'
        '- Only create a new theme if several new papers share a subject no existing '
        'theme covers. Append new themes at the end, continuing the numbering.\n'
        '- Leave the closing note on the overall shape of the collection unchanged '
        'unless the new papers genuinely change that picture.\n\n'
        f'EXISTING REPORT:\n{report}\n\n'
        f'NEW PAPERS ({len(new_summaries)}):\n{_corpus_lines(new_summaries)}'
    )
    return _run_themes_prompt(prompt, model, max_tokens)
