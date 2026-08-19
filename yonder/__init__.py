__author__ = "Nikolas Dahn"
__version__ = "1.5.2"

# suppress pyo warning about wxpython
import os
os.environ["PYO_GUI_WX"] = "0"
del os

from .types.soundbank import Soundbank
from .types.hirc_node import HIRCNode
from .hash import calc_hash, lookup_name, Hash
from .game import set_game, get_selected_game
from .enums import Game
from . import enums
from . import export
from . import convenience
from . import transfer
from . import wem

# Set a reasonable default, especially for non-gui mode
set_game(Game.EldenRing)
