from __future__ import annotations

import logging
import sys
from pathlib import Path

from autodar.gui import run


def main() -> int:
    if getattr(sys, "frozen", False):
        resource_dir = Path(getattr(sys, "_MEIPASS"))
        output_dir = Path(sys.executable).resolve().parent
    else:
        resource_dir = Path(__file__).resolve().parent
        output_dir = resource_dir
    logging.basicConfig(
        filename=output_dir / "autodar.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    return run(resource_dir, output_dir)


if __name__ == "__main__":
    sys.exit(main())

