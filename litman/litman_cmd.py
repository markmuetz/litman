import os

import litman.cmds as cmds
from litman.command_parser import parse_commands
from litman.setup_logging import setup_logger, add_file_logging
from litman.litman import LitMan

LITMAN_BASEDIR = '$HOME/LitMan/literature'

ARGS = [(['--DEBUG', '-D'], {'action': 'store_true', 'default': False}),
        (['--litman-dir', '-l'], {'help': 'LitMan directory', 'default': LITMAN_BASEDIR})]


def main(argv):
    litman_cmds, args = parse_commands('litman', ARGS, cmds, argv[1:])
    litman_dir = os.path.expandvars(args.litman_dir)
    cmd = litman_cmds[args.cmd_name]

    if args.DEBUG:
        debug = True
    else:
        debug = False

    logger = setup_logger(debug, colour=True)

    litman = LitMan(litman_dir)

    return cmd.main(litman, args)
