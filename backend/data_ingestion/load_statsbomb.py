"""Inspect the local StatsBomb Open Data copy; this script does not download data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_ROOT = PROJECT_ROOT / "archive (3)"


def json_files(path: Path) -> list[Path]:
    return list(path.rglob("*.json")) if path.exists() else []


def rate_limit_placeholders(path: Path) -> list[Path]:
    return [
        item for item in json_files(path)
        if item.stat().st_size <= 200 and b"temporarily unavailable" in item.read_bytes()
    ]


def inspect_dataset(data_root: Path, list_seasons: bool = False) -> None:
    data_dir = data_root / "data"
    required_dirs = [data_dir / "events", data_dir / "matches", data_dir / "lineups"]
    missing = [path for path in required_dirs if not path.is_dir()]
    if missing:
        formatted = "\n".join(f"  - {path}" for path in missing)
        raise FileNotFoundError(
            f"StatsBomb Open Data folders were not found under {data_root}:\n{formatted}"
        )

    print(f"StatsBomb Open Data root: {data_root}")
    for name in ("events", "matches", "lineups", "three-sixty"):
        path = data_dir / name
        files = json_files(path)
        errors = rate_limit_placeholders(path)
        print(f"{name}: {len(files):,} JSON files; {len(errors):,} rate-limit error placeholders")
        if errors:
            print("  invalid IDs: " + ", ".join(sorted(item.stem for item in errors)))

    competitions_file = data_dir / "competitions.json"
    if competitions_file.exists():
        competitions = json.loads(competitions_file.read_text(encoding="utf-8"))
        print(f"competition-season entries: {len(competitions):,}")
        if list_seasons:
            for item in competitions:
                print(
                    f"{item.get('competition_id')}\t{item.get('competition_name')}\t"
                    f"{item.get('season_id')}\t{item.get('season_name')}"
                )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-root",
        type=Path,
        default=DEFAULT_DATA_ROOT,
        help="StatsBomb Open Data repository root (default: archive (3))",
    )
    parser.add_argument(
        "--list-seasons",
        action="store_true",
        help="Also print every competition and season ID",
    )
    args = parser.parse_args()
    inspect_dataset(args.data_root, list_seasons=args.list_seasons)


if __name__ == "__main__":
    main()
