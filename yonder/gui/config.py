from __future__ import annotations
from typing import Generator, TYPE_CHECKING
import sys
import yaml
import inspect
from pathlib import Path
from dataclasses import dataclass, field, asdict

from yonder.hash import global_hash_dict, load_lookup_table
from yonder.util import logger
from yonder.gui.dialogs.file_dialog import open_file_dialog

if TYPE_CHECKING:
    from yonder.types.soundbank import Soundbank


@dataclass
class Config:
    recent_files: list[str] = field(default_factory=list)
    language: str = "English"

    bnk2json_exe: str = None
    wwise_exe: str = None
    vgmstream_exe: str = None

    bankdirs: list[str] = field(default_factory=list)
    hash_dicts: list[str] = field(default_factory=list)

    # Your advertisement could go here

    def add_recent_file(self, file_path: str) -> None:
        file_path = str(Path(file_path).absolute())
        if file_path in self.recent_files:
            self.recent_files.remove(file_path)

        self.recent_files.insert(0, file_path)
        self.recent_files = self.recent_files[:10]

    def remove_recent_file(self, file_path: str) -> None:
        if file_path in self.recent_files:
            self.recent_files.remove(file_path)

    def save(self, config_path: str = None) -> None:
        if not config_path:
            config_path = get_default_config_path()

        with open(config_path, "w") as f:
            yaml.safe_dump(asdict(self), f)

    def locate_bnk2json(self) -> str:
        if not self.bnk2json_exe or not Path(self.bnk2json_exe).is_file():
            bnk2json_exe = open_file_dialog(
                title="Locate bnk2json.exe", filetypes={"bnk2json.exe": "bnk2json.exe"}
            )
            if not bnk2json_exe:
                raise ValueError("bnk2json not found")

            self.bnk2json_exe = bnk2json_exe
            self.save()

        return self.bnk2json_exe

    def locate_wwise(self) -> str:
        if not self.wwise_exe or not Path(self.wwise_exe).is_file():
            wwise_exe = open_file_dialog(
                title="Locate WwiseConsole.exe",
                filetypes={"WwiseConsole.exe": "WwiseConsole.exe"},
            )
            if not wwise_exe:
                raise ValueError("WwiseConsole not found")

            self.wwise_exe = wwise_exe
            self.save()

        return self.wwise_exe

    def locate_vgmstream(self) -> str:
        if not self.vgmstream_exe or not Path(self.vgmstream_exe).is_file():
            vgmstream_exe = open_file_dialog(
                title="Locate vgmstream-cli.exe",
                filetypes={"vgmstream-cli.exe": "vgmstream-cli.exe"},
            )
            if not vgmstream_exe:
                raise ValueError("vgmstream-cli not found")

            self.vgmstream_exe = vgmstream_exe
            self.save()

        return self.vgmstream_exe

    def load_hash_dicts(self) -> None:
        for path in self.hash_dicts:
            path = Path(path)
            if not path.is_file():
                logger.warning(f"Hash dict not found: {path}")
            else:
                global_hash_dict.update(load_lookup_table(path))

    def find_external_sounds(
        self, source_id: int, bnk: Soundbank = None
    ) -> Generator[Path, None, None]:
        bnkdirs = [Path(p) for p in self.bankdirs]
        if bnk:
            # Soundbanks unpacked in the game folder
            bnkdirs.insert(0, bnk.bnk_dir.parent)

        # For game folders
        for path in bnkdirs:
            if path.name != "sd" and (path / "sd").is_dir():
                bnkdirs.append(path / "sd")

        for path in bnkdirs:
            path: Path = Path(path)
            stream_path = f"wem/{str(source_id)[:2]}/{source_id}.wem"

            # Check locations for streaming sounds first before searching the entire directory
            wem = path / stream_path
            if wem.is_file():
                yield wem

            wem = path / "enus" / stream_path
            if wem.is_file():
                yield wem

            # Check if we can find the sound in any other unpacked soundbank
            yield from path.glob(f"**/{source_id}.wem")

    def refresh(self) -> None:
        # Not a full reload, just makes sure that any changes are applied
        self.load_hash_dicts()


_config: Config = None


def get_default_config_path() -> str:
    return str(Path(sys.argv[0]).parent / "config.yaml")


def get_config() -> Config:
    return _config


def load_config(config_path: str = None) -> Config:
    global _config

    if not config_path:
        config_path = get_default_config_path()

    config_path: Path = Path(config_path)
    if config_path.is_file():
        with config_path.open() as f:
            cfg = yaml.safe_load(f)

        sig = inspect.signature(Config.__init__)
        kw = {}

        # Match the args from the config to the current implementation in case it changed
        for key, val in cfg.items():
            if key in sig.parameters:
                kw[key] = val

        _config = Config(**kw)
    else:
        print(f"Creating new config in {config_path}")
        _config = Config()
        _config.save(config_path)

    _config.load_hash_dicts()
    return _config
