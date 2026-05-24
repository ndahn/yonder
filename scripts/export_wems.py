from pathlib import Path
import csv
import argparse

from yonder import Soundbank
from yonder.util import logger
from yonder.export import export_wems


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("bank")
    p.add_argument("input", type=Path)
    p.add_argument("-p", "--prefix", type=str, default=None)
    p.add_argument("-e", "--evttype", type=str, default="v")
    p.add_argument("-s", "--srcpath", type=Path, default=Path("E:/SteamLibrary/steamapps/common/ELDEN RING/Game/sd/"))
    p.add_argument("-o", "--output", type=Path, default=None)

    args = p.parse_args()

    if not args.output:
        args.output = Path(__file__).parent / "export"


    events: list[str] = []
    with open(args.input) as f:
        dialect = csv.Sniffer().sniff(f.read(1024))
        f.seek(0)
        reader = csv.reader(f, dialect)
        
        # skip header
        next(reader, None)
        for row in reader:
            events.append(f"Play_{args.evttype}{row[0]}")

    bnk = Soundbank.load(args.bank)
    export_wems(bnk, events, args.output, prefix=args.prefix)
    logger.info(f"Done! Wems exported to {args.output}")



if __name__ == "__main__":
    main()
