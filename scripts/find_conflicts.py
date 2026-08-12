from pathlib import Path
import shutil
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from yonder import Soundbank
from yonder.util import unpack_soundbank, logger


if __name__ == "__main__":
    path_offender = Path(
        "E:/Games/Elden Ring/Modding/Tools/yonder/test/discord/cs_c4340_orig"
    )
    banks_dir = Path("E:/SteamLibrary/steamapps/common/ELDEN RING NIGHTREIGN/Game/sd")
    bnk2json = Path("E:/Games/Elden Ring/Modding/Tools/rewwise_0.3.2/bnk2json.exe")

    bank_offender = Soundbank.load(path_offender)
    game_banks = list(banks_dir.glob("**/*.bnk"))

    with logging_redirect_tqdm():
        with tqdm(game_banks) as t:
            for bnk_file in t:
                t.set_description(bnk_file.stem)

                unpacked = False
                bnk_dir = bnk_file.parent / bnk_file.stem

                if not bnk_dir.is_dir():
                    unpack_soundbank(bnk2json, bnk_file)
                    unpacked = True

                bnk = Soundbank.load(bnk_dir)
                conflicts = bank_offender.check_conflicts(bnk, soft=False)
                if conflicts:
                   conflicts = [(c[0], c[1].__name__, c[2].__name__) for c in conflicts]
                   logger.warning(f"Found conflicts with {bnk.name}: {conflicts}")

                #redundant = [n for n in bank_offender if n.id in bnk]
                #if redundant:
                #    logger.warning(
                #        f"The following nodes are also defined in {bnk.name}:\n{redundant}"
                #    )

                if unpacked:
                    shutil.rmtree(bnk_dir)
