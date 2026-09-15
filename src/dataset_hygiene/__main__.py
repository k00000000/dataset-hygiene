from __future__ import annotations

"""Allow `python -m dataset_hygiene`."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
