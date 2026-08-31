from typing import ClassVar
import re
from pathlib import Path
from Crypto.Cipher import AES

from yonder.enums import Game, EnumWithUnknown
from .data.actormixer_summary import AmxSummary
from .steam import find_game_folder


_undefined = object()


class GameObjects:
    game: ClassVar[Game]
    steam_app_id: ClassVar[int]
    regbin_key: ClassVar[bytes]
    rtpc_params: ClassVar[type[EnumWithUnknown]]
    game_states: ClassVar[dict[str, list[str]]]
    amx_summary: ClassVar[AmxSummary]

    @classmethod
    def get_game_path(cls, default: Path = _undefined) -> Path:
        try:
            return find_game_folder(cls.steam_app_id)
        except FileNotFoundError:
            if default is not _undefined:
                return default
            raise


_selected_game: GameObjects = None


def set_game(game: Game) -> None:
    # Need to load these for subclass discovery even if we're not using them here
    from .eldenring import GameEldenring  # noqa: F401
    from .nightreign import GameNightreign  # noqa: F401
    # from .armoredcore6 import GameArmoredCore6
    # AC6 regbin key: 10ceed477b7cd9d7e6938e114713e787d53913b1d318ec135e4be50504ee10
    # AC6 steam app id: 1888160
    
    global _selected_game

    for game_spec in GameObjects.__subclasses__():
        if game_spec.game == game:
            _selected_game = game_spec
            break
    else:
        raise ValueError(f"Game {game} is not supported yet")


def get_selected_game() -> type[GameObjects]:
    return _selected_game


def guess_game(path: Path) -> Game:
    # Search for more reliable clues first
    while True:
        regbin = path / "regulation.bin"
        if regbin.is_file():
            # Check if we can decrypt the regbin with a known key
            data = regbin.read_bytes()
            for game_spec in GameObjects.__subclasses__():
                iv = data[:16]
                encrypted = data[16:]

                # Pad to block size (16)
                remainder = len(encrypted) % 16
                if remainder > 0:
                    encrypted += b"\x00" * (16 - remainder)

                cipher = AES.new(game_spec.regbin_key, AES.MODE_CBC, iv=iv)
                content = cipher.decrypt(encrypted)
                if content[:3].decode(errors="ignore") == "DCX":
                    return game_spec.game

        me3profile = next(path.glob("*.me3"), None)
        if me3profile:
            # If we can find an me3 profile it's somewhat safe to assume it's related
            # to this soundbank
            for line in me3profile.read_text().splitlines():
                if re.match(r"^game\w*=.*", line):
                    game = line.split("=")[-1].strip().lower()

                    if game == "eldenring":
                        return Game.EldenRing
                    if game == "nightreign":
                        return Game.Nightreign
                    if game == "armoredcore6":
                        return Game.ArmoredCore6

        path = path.parent
        if path.parent == path:
            break

    # Check if the path can give us any hints
    path_str = str(path).lower()

    if "nightreign" in path_str:
        return Game.Nightreign

    if re.search(r"elden.ring", path_str):
        return Game.EldenRing

    if re.search(r"armored.core", path_str):
        return Game.ArmoredCore6

    return None
