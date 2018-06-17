import os

import litman.cmds as cmds
from litman.command_parser import parse_commands
from litman.setup_logging import setup_logger, add_file_logging
from litman.litman import LitMan, load_config

LITMAN_BASEDIR = '$HOME/LitMan'

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
    cmd_string = ' '.join(argv)
    litmanrc_fn, config = load_config()

    if not os.path.exists(litman_dir):
        print('You can change your litman dir by editing $HOME/.litmanrc')
        print('e.g.')
        print('')
        print('[litman]')
        print('litman_dir = /path/to/dir')
        print('')
        r = input('Create litman dir {litman_dir}? (y/[n]): ')
        if r.lower() != 'y':
            logger.debug(f'user exiting')
            print('Exiting')
            return
        os.makedirs(litman_dir)

    add_file_logging(os.path.join(litman_dir, '.litman.log'))

    logger.debug(f'CMD: {cmd_string}')
    if os.path.exists(litmanrc_fn):
        logger.debug(f'reading config {litmanrc_fn}')
    logger.debug(f'using litman_dir {litman_dir}')

    litman = LitMan(config['litman_dir'])

    logger.debug(f'dispatching to {cmd}')
    return cmd.main(litman, args)
