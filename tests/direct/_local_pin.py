"""Generate a 1.x-loadable copy of the ledger for local tests.

Studio Next runs the 2.x runner and needs `gl.contract.Contract` plus
`genlayer.storage`; the runner gltest has is 1.x and accepts the star-import
form with `gl.Contract`. Rewrite the three 2.x-only constructs for the local
copy so the chain source stays canonical and nothing drifts.
"""
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "contracts" / "agent_reputation_ledger.py"
LOCAL = SRC.parent / "_local_pin_ledger.py"
LOCAL_PIN = "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6"

# Match the explicit-import BLOCK rather than an exact string. Pinning the
# literal silently stopped working the moment `Address` was added to it, and
# every test failed with a confusing loader error instead of a clear one.
_EXPLICIT_IMPORTS = re.compile(
    r"^import genlayer as gl\n"
    r"^from genlayer import .*\n"
    r"^from genlayer\.storage import TreeMap\n"
    r"^from genlayer\.storage import allow as allow_storage$",
    re.MULTILINE,
)


def build() -> Path:
    src = re.sub(r"py-genlayer:[a-z0-9]+", LOCAL_PIN, SRC.read_text(), count=1)
    src = src.replace("gl.contract.Contract", "gl.Contract")
    src, n = _EXPLICIT_IMPORTS.subn("from genlayer import *", src)
    if n != 1:
        raise RuntimeError(
            f"expected to rewrite one explicit-import block, rewrote {n}. "
            "The chain source changed shape - update this helper."
        )
    LOCAL.write_text(src)
    return LOCAL
