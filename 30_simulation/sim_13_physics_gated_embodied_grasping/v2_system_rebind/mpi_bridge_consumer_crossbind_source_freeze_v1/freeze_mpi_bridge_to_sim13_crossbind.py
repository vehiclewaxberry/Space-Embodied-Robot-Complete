from __future__ import annotations

import json
from pathlib import Path

from crossbind.package import find_repo_root, freeze_package


if __name__ == "__main__":
    package_root = Path(__file__).resolve().parent
    result = freeze_package(package_root, find_repo_root(package_root))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))

