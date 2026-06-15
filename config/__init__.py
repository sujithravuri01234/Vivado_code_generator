from __future__ import annotations

from pathlib import Path

# Mirror the backend config package for repo-root launches.
__path__ = [str(Path(__file__).resolve().parents[1] / "backend" / "config")]
