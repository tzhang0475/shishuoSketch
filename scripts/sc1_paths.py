"""Named paths for frozen and current SC1 projection contracts."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# FROZEN_SC1_V1 is intentionally kept at its original locations.  A large
# number of historical manifests refer to these paths, so the namespace is
# declared by manifest rather than by moving the bytes.
FROZEN_SC1_DERIVED_PATH = Path("data/derived/sc1-site.json")
FROZEN_SC1_VITE_PATH = Path("site/src/generated/sc1-site.json")
FROZEN_SC1_MANIFEST_PATH = Path("data/frozen/sc1/v1/manifest.json")
FROZEN_SC1_SHA256 = "cc82c6738fcbf4fc14c12005a459048e71ce329492867d0910562fc6fdfda0d8"
FROZEN_SC1_BYTE_SIZE = 6_868_623

# SC1_CURRENT is the only output target of the active SC1 builder.  Keeping a
# separate derived and Vite path preserves the existing one-bundle/two-view
# contract without allowing a rebuild to mutate the historical snapshot.
CURRENT_SC1_DERIVED_PATH = Path("data/derived/sc1-current-site.json")
CURRENT_SC1_VITE_PATH = Path("site/src/generated/sc1-current-site.json")


def absolute(root: Path, relative: Path) -> Path:
    """Resolve one named SC1 path below a repository root."""

    return root / relative
