from __future__ import annotations

from pathlib import Path

# Make `app.*` imports resolve to the real backend package even when the
# server is launched from the repository root.
__path__ = [str(Path(__file__).resolve().parents[1] / "backend" / "app")]
