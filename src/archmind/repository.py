from __future__ import annotations

import subprocess
from pathlib import Path

from archmind.models import RepositorySnapshot
from archmind.utils import compact_path, ensure_dir, utc_now_iso


MANIFEST_FILES = {
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "setup.py",
    "package.json",
    "Cargo.toml",
    "go.mod",
}


def clone_repository(remote: str, branch: str, destination: Path) -> Path:
    ensure_dir(destination.parent)
    subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", branch, remote, str(destination)],
        check=True,
        capture_output=True,
        text=True,
    )
    return destination


def repository_commit_sha(repo_path: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def detect_language_hints(repo_path: Path) -> list[str]:
    suffixes: set[str] = set()
    for path in repo_path.rglob("*"):
        if path.is_file() and ".git" not in path.parts:
            suffixes.add(path.suffix)
    hints = []
    if ".py" in suffixes:
        hints.append("python")
    if ".js" in suffixes or ".ts" in suffixes:
        hints.append("javascript")
    if ".go" in suffixes:
        hints.append("go")
    if ".rs" in suffixes:
        hints.append("rust")
    return hints or ["unknown"]


def manifest_files(repo_path: Path) -> list[str]:
    manifests: list[str] = []
    for path in repo_path.rglob("*"):
        if path.is_file() and path.name in MANIFEST_FILES:
            manifests.append(compact_path(path, repo_path))
    return sorted(manifests)


def source_tree(repo_path: Path) -> dict[str, list[str]]:
    files: list[str] = []
    dirs: set[str] = set()
    for path in repo_path.rglob("*"):
        if ".git" in path.parts:
            continue
        rel = compact_path(path, repo_path)
        if path.is_dir():
            dirs.add(rel)
        elif path.is_file():
            files.append(rel)
    return {"directories": sorted(dirs), "files": sorted(files)}


def build_snapshot(repo_path: Path, remote: str, branch: str) -> RepositorySnapshot:
    return RepositorySnapshot(
        github_url=remote,
        branch=branch,
        commit_sha=repository_commit_sha(repo_path),
        fetched_at=utc_now_iso(),
        root_path=str(repo_path),
        language_hints=detect_language_hints(repo_path),
        manifests=manifest_files(repo_path),
    )
