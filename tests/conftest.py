"""Session-wide test setup.

Studio Next runs the 2.x SDK runner and needs `gl.contract.Contract` plus
`genlayer.storage`. The runner gltest uses locally is 1.x and accepts the
star-import form with `gl.Contract`. Generate a 1.x-loadable copy once per
session so the chain source stays canonical and the two cannot drift.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.direct._local_pin import build as _build_local_copy  # noqa: E402

_build_local_copy()
