"""pytest config: put site_scripts/ on sys.path once so tests can
``import fetch_schedule`` (etc.) without a per-file sys.path hack."""
import sys
from pathlib import Path

SITE_SCRIPTS = str(Path(__file__).resolve().parents[1])
if SITE_SCRIPTS not in sys.path:
    sys.path.insert(0, SITE_SCRIPTS)
