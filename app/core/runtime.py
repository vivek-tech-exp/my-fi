"""Runtime bootstrap helpers."""

from collections.abc import Iterable
from pathlib import Path


def ensure_directories(paths: Iterable[Path]) -> None:
    """Create required runtime directories when they do not already exist."""

    for path in paths:
        path.mkdir(parents=True, exist_ok=True)
