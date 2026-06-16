"""Use Claude to summarize extracted text and synthesize themes.

Requires the `anthropic` package (``pip install -e .[ai]``) and an
``ANTHROPIC_API_KEY`` in the environment. All anthropic imports are done lazily
so the rest of litman works without the dependency installed.

Map step (summarize, run once per paper): cheap and parallel -> Haiku + Batch.
Reduce step (themes, one call over all summaries): intelligence matters -> Opus.
"""
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
    for result in client().messages.batches.results(batch_id):
        if result.result.type == 'succeeded':
            msg = result.result.message
            text = next((b.text for b in msg.content if b.type == 'text'), '')
            try:
                yield result.custom_id, json.loads(text), None
            except json.JSONDecodeError as e:
                yield result.custom_id, None, f'bad json: {e}'
        else:
            yield result.custom_id, None, result.result.type


def synthesize_themes(summaries, model=THEMES_MODEL, max_tokens=16000):
    """summaries: list of (item_name, summary_dict). Returns a markdown theme report."""
    lines = []
    for name, s in summaries:
        kw = ', '.join(s.get('keywords', []))
        lines.append(f'- [{name}] {s.get("topic", "")} | keywords: {kw}')
    corpus = '\n'.join(lines)

    prompt = (
        'Below is a list of papers from a personal literature library, one per line, '
        'each with a one-line topic and keywords. Identify the major recurring themes '
        'across the collection. For each theme: give it a short title, a one-sentence '
        'description, and list the item keys (the [name] tags) that belong to it. A '
        'paper may appear under more than one theme. End with a short note on the '
        "overall shape of the collection. Use markdown.\n\n"
        f'Papers ({len(summaries)}):\n{corpus}'
    )

    parts = []
    with client().messages.stream(
        model=model,
        max_tokens=max_tokens,
        thinking={'type': 'adaptive'},
        messages=[{'role': 'user', 'content': prompt}],
    ) as stream:
        for text in stream.text_stream:
            parts.append(text)
    return ''.join(parts)
