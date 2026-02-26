import sys
from pathlib import Path

def resource_path(relative_path: str) -> str:
    try:

        base_path = Path(sys._MEIPASS)
    except Exception:

        base_path = Path(__file__).resolve().parent.parent

    full_path = base_path / relative_path

    if full_path.exists():
        pass
    else:
        pass

    return str(full_path)

