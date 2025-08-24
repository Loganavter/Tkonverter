import logging
import sys
from pathlib import Path

paths_logger = logging.getLogger("Paths")
paths_logger.setLevel(logging.WARNING)

def resource_path(relative_path: str) -> str:
    try:

        base_path = Path(sys._MEIPASS)
    except Exception:

        base_path = Path(__file__).resolve().parent.parent

    full_path = base_path / relative_path

    if full_path.exists():
        pass
    else:
        paths_logger.warning(f"Resource NOT found: {full_path}")

    return str(full_path)
