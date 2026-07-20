# suppress pyo warning about wxpython
import os
os.environ["PYO_GUI_WX"] = "0"
del os

from .player import Player
from .voice import Voice
from .equalizer import Equalizer, EQPresets