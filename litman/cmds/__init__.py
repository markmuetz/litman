import importlib
from collections import OrderedDict
from logging import getLogger

logger = getLogger('litman.cmds')

commands = [
    'display',
    'gen_bib',
    'import_bib',
    'import_pdf',
    'list',
    'search',
    'show',
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

