import logging
import sys


# Thanks: http://stackoverflow.com/a/287944/54557
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


# Thanks: # http://stackoverflow.com/a/8349076/54557
class ColourConsoleFormatter(logging.Formatter):
    '''Format messages in colour based on their level'''
    dbg_fmt = bcolors.OKBLUE + '%(levelname)-8s' + bcolors.ENDC + ': %(message)s'
    info_fmt = bcolors.OKGREEN + '%(levelname)-8s' + bcolors.ENDC + ': %(message)s'
    file_fmt = bcolors.HEADER + '%(levelname)-8s' + bcolors.ENDC + ': %(message)s'
    warn_fmt = bcolors.WARNING + '%(levelname)-8s' + bcolors.ENDC + ': %(message)s'
    err_fmt = (bcolors.FAIL + '%(levelname)-8s' + bcolors.ENDC + bcolors.BOLD +
               ': %(message)s' + bcolors.ENDC)

    def __init__(self, fmt="%(levelno)s: %(msg)s"):
        logging.Formatter.__init__(self, fmt)

    def format(self, record):
        # Save the original format configured by the user
        # when the logger formatter was instantiated
        format_orig = self._fmt

        # Replace the original format with one customized by logging level
        if record.levelno == logging.DEBUG:
            self._fmt = ColourConsoleFormatter.dbg_fmt
        elif record.levelno == logging.INFO:
            self._fmt = ColourConsoleFormatter.info_fmt
        elif record.levelno == logging.WARNING:
            self._fmt = ColourConsoleFormatter.warn_fmt
        elif record.levelno == logging.ERROR:
            self._fmt = ColourConsoleFormatter.err_fmt

        # Call the original formatter class to do the grunt work
        result = logging.Formatter.format(self, record)

        # Restore the original format configured by the user
        self._fmt = format_orig

        return result


def add_file_logging(logging_filename):
    root_logger = logging.getLogger()

    if getattr(root_logger, 'has_file_logging', False):
        # Stops log being setup for a 2nd time during ipython reload(...)
        root_logger.debug('Root logger already has file logging')

    else:
        file_formatter = logging.Formatter('%(asctime)s:%(name)-12s:%(levelname)-8s: %(message)s')
        fileHandler = logging.FileHandler(logging_filename, mode='a')
        fileHandler.setFormatter(file_formatter)
        fileHandler.setLevel(logging.DEBUG)

        root_logger.addHandler(fileHandler)
        root_logger.has_file_logging = True


def setup_logger(debug=False, colour=True):
    '''Gets a logger. Sets up root logger ('litman') if nec.'''
    root_logger = logging.getLogger()
    litman_logger = logging.getLogger('litman')
    root_logger.propagate = False

    root_handlers = []
    while root_logger.handlers:
        # By default, the root logger has a stream handler attached.
        # Remove it. N.B any code that uses litman should know this!
        root_handlers.append(root_logger.handlers.pop())

    if getattr(litman_logger, 'is_setup', False):
        # Stops log being setup for a 2nd time during ipython reload(...)
        litman_logger.debug('Root logger already setup')
    else:
        fmt = '%(levelname)-8s: %(message)s'
        if colour:
            console_formatter = ColourConsoleFormatter(fmt)
        else:
            console_formatter = logging.Formatter(fmt)

        if debug:
            level = logging.DEBUG
        else:
            level = logging.INFO

        stdoutStreamHandler = logging.StreamHandler(sys.stdout)
        stdoutStreamHandler.setFormatter(console_formatter)
        stdoutStreamHandler.setLevel(level)

        root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(stdoutStreamHandler)

        root_logger.is_setup = True

    for hdlr in root_handlers:
        litman_logger.debug('Removed root handler: {}'.format(hdlr))

    return litman_logger
