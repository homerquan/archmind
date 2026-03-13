from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, contents: str) -> None:
    ensure_dir(path.parent)
    path.write_text(contents, encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def workspace_dir(root: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return root / f"run-{timestamp}-{uuid4().hex[:8]}"


def compact_path(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def env_truthy(name: str) -> bool:
    value = os.getenv(name, "")
    return value.lower() in {"1", "true", "yes", "on"}
