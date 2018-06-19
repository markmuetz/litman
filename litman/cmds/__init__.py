import importlib
from collections import OrderedDict
from logging import getLogger

logger = getLogger('litman.cmds')

commands = [
    'build-refs',
    'check-titles',
    'display',
    'gen_bib',
    'import-bib',
    'import-pdf',
    'list',
    'mag-cited-by',
    'mag-search',
    'search',
    'show',
    'stats',
    'version',
]

modules = OrderedDict()
for command in commands:
    command_name = 'cmds.' + command.replace('-', '_')
    try:
        modules[command] = importlib.import_module('litman.' + command_name)
    except ImportError as e:
        logger.warning('Cannot load module {}'.format(command_name))
        logger.warning(e)

