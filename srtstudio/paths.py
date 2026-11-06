import os
import sys
from pathlib import Path


def data_dir():
    p = Path(os.environ.get("SZEPT_DATA_DIR", Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Szept"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def resource_dir():
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
