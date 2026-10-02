import importlib
from collections import OrderedDict
from logging import getLogger

logger = getLogger('litman.cmds')

commands = [
    'check-bib',
    'check-titles',
    'citation-graph',
    'cleanup-report',
    'display',
    'edit',
    'embed',
    'find-doi',
    'gen-bib',
    'import-bib',
    'import-pdf',
    'list',
    'normalize',
    'open-doi',
    'search',
    'search-semantic',
    'shell',
    'similar',
    'show',
    'stats',
    'summarize',
    'themes',
    'version',
    'word-index',
]

modules = OrderedDict()
for command in commands:
    command_name = 'cmds.' + command.replace('-', '_')
    try:
        modules[command] = importlib.import_module('litman.' + command_name)
    except ImportError as e:
        logger.warning('Cannot load module {}'.format(command_name))
        logger.warning(e)

