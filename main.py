from __future__ import annotations

import logging
import sys
from pathlib import Path

from autodar.gui import run


def main() -> int:
    project_dir = Path(__file__).resolve().parent
    logging.basicConfig(
        filename=project_dir / "autodar.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    return run(project_dir)


if __name__ == "__main__":
    sys.exit(main())

