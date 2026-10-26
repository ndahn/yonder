from pathlib import Path
import zipfile

from yonder import Soundbank
from yonder.util import logger, unpack_soundbank

# === settings ===

vgmstream = Path("E:/Games/Elden Ring/Modding/Tools/vgmstream-win64/vgmstream-cli.exe")
bnk2json = Path("E:/Games/Elden Ring/Modding/Tools/rewwise_0.3.2/bnk2json.exe")
game_dir = Path("E:/SteamLibrary/steamapps/common/ELDEN RING/Game/sd")

mod = "star0everyone"
npc_dir = "melina_vcmain"

# === prep ===

# TODO place wems in mod/sd/wem/
# TODO check if prefetch snippets need to be adjusted

import_dir = Path(__file__).parent / mod / npc_dir
mod_sd_dir = Path(__file__).parent / mod / "mod" / "sd" / "enus"

