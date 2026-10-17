"""Create a local, ignored, verified backup of operational SQLite and face images."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sqlite3


ROOT = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    value = sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> None:
    destination = ROOT / ".local-backups" / datetime.now().strftime("%Y%m%d-%H%M%S")
    destination.mkdir(parents=True, exist_ok=False)
    manifest: dict[str, object] = {"created_at": datetime.now().astimezone().isoformat(), "files": {}}
    files: dict[str, str] = manifest["files"]  # type: ignore[assignment]
    for source in sorted(path for path in ROOT.glob("*.db") if not path.name.startswith(".")):
        target = destination / source.name
        with closing(sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)) as original:
            with closing(sqlite3.connect(target)) as backup:
                original.backup(backup)
                if backup.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise RuntimeError(f"SQLite backup failed integrity check: {source.name}")
        files[source.name] = digest(target)
    photos = ROOT / "known_faces"
    if photos.exists():
        for source in sorted(p for p in photos.rglob("*") if p.is_file()):
            relative = source.relative_to(ROOT)
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            if digest(source) != digest(target):
                raise RuntimeError(f"Photo backup checksum mismatch: {relative}")
            files[relative.as_posix()] = digest(target)
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Verified backup: {destination} ({len(files)} files)")


if __name__ == "__main__":
    main()
