"""Locate the explicitly configured or installed Chromium-family browser."""
import os
import shutil
from pathlib import Path

def browser_executable() -> str:
    requested = os.environ.get("STUDIO_BROWSER")
    if requested:
        found = shutil.which(requested)
        if not found:
            raise FileNotFoundError("STUDIO_BROWSER is not an executable")
        return str(Path(found).absolute())
    for name in ("google-chrome", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return str(Path(found).absolute())
    raise FileNotFoundError("Install Chrome/Chromium or set STUDIO_BROWSER to its executable")
