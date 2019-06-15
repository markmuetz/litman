from .version import __version__, get_version

from .litman_cmd import main as litman_main
from .litman import LitMan, LitItem, ItemNotFound, load_config
from .gen_journal_abbr_name import gen_journal_abbr_name_map, load_journal_abbr_name_map
from .experimental.mag_client import MagClient, HttpException, PaperNotFound
