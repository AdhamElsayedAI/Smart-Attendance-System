"""Compare current operational records and photos to an ignored local backup."""
from __future__ import annotations

import argparse
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    value = sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def sqlite_digest(path: Path) -> str:
    with closing(sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)) as conn:
        return sha256("\n".join(conn.iterdump()).encode()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("backup", type=Path, help="Folder created by backup_data.py")
    args = parser.parse_args()
    backup = args.backup.resolve()
    manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
    failures = []
    databases = photos = 0
    for name, expected in manifest["files"].items():
        source = ROOT / name
        copy = backup / name
        if not source.is_file() or not copy.is_file() or digest(copy) != expected:
            failures.append(f"Missing or changed backup: {name}")
            continue
        if name.endswith(".db"):
            databases += 1
            if sqlite_digest(source) != sqlite_digest(copy):
                failures.append(f"Database content differs: {name}")
        else:
            photos += 1
            if digest(source) != expected:
                failures.append(f"Photo content differs: {name}")
    print(f"Checked {databases} SQLite databases and {photos} image files against {backup.name}")
    if failures:
        for failure in failures:
            print(failure)
        raise SystemExit(1)
    print("All original database content and image checksums match the backup.")


if __name__ == "__main__":
    main()
