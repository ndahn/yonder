from pathlib import Path
import csv
import argparse

from yonder import Soundbank
from yonder.util import logger, unpack_soundbank
from yonder.export import export_wems


vgmstream = Path("E:/Games/Elden Ring/Modding/Tools/vgmstream-win64/vgmstream-cli.exe")
bnk2json = Path("E:/Games/Elden Ring/Modding/Tools/rewwise_0.3.2/bnk2json.exe")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("bank", type=Path)
    p.add_argument("infile", type=Path)
    p.add_argument("-p", "--prefix", type=str, default=None)
    p.add_argument("-e", "--evttype", type=str, default="v")
    p.add_argument("-o", "--output", type=Path, default=None)

    args = p.parse_args()

    if not args.output:
        prefix = args.prefix if args.prefix else ""
        args.output = Path(__file__).parent / f"{prefix}export"

    events: list[str] = []
    with args.infile.open() as f:
        dialect = csv.Sniffer().sniff(f.read(1024))
        f.seek(0)
        reader = csv.reader(f, dialect)
        
        # skip header
        next(reader, None)
        for row in reader:
            events.append(f"Play_{args.evttype}{row[0]}")

    if args.bank.suffix == ".bnk":
        args.bank = unpack_soundbank(bnk2json, args.bank)

    bnk = Soundbank.load(args.bank)
    copied, missing = export_wems(bnk, events, args.output, prefix=args.prefix)
    logger.info(f"Done! {len(copied)} wems exported to {args.output}")

    if missing:
        (args.output / "missing.txt").write_text("\n".join(missing))


if __name__ == "__main__":
    main()
