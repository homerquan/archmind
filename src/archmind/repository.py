from __future__ import annotations

import shutil
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


def clone_repository(remote: str, branch: str, destination: Path) -> tuple[Path, str]:
    ensure_dir(destination.parent)
    try:
        _clone_branch(remote, branch, destination)
        return destination, branch
    except subprocess.CalledProcessError as error:
        default_branch = resolve_default_branch(remote)
        if default_branch and default_branch != branch:
            _reset_destination(destination)
            try:
                _clone_branch(remote, default_branch, destination)
                return destination, default_branch
            except subprocess.CalledProcessError as retry_error:
                raise RuntimeError(_clone_error_message(remote, branch, default_branch, retry_error)) from retry_error
        raise RuntimeError(_clone_error_message(remote, branch, default_branch, error)) from error


def _clone_branch(remote: str, branch: str, destination: Path) -> None:
    subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", branch, remote, str(destination)],
        check=True,
        capture_output=True,
        text=True,
    )


def _reset_destination(destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)


def resolve_default_branch(remote: str) -> str | None:
    result = subprocess.run(
        ["git", "ls-remote", "--symref", remote, "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        if line.startswith("ref: ") and "\tHEAD" in line:
            ref = line.split("\t", 1)[0].replace("ref: ", "", 1).strip()
            return ref.removeprefix("refs/heads/")
    return None


def list_remote_branches(remote: str) -> list[str]:
    result = subprocess.run(
        ["git", "ls-remote", "--heads", remote],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    branches = []
    for line in result.stdout.splitlines():
        if "\t" not in line:
            continue
        ref = line.split("\t", 1)[1].strip()
        if ref.startswith("refs/heads/"):
            branches.append(ref.removeprefix("refs/heads/"))
    return sorted(set(branches))


def _clone_error_message(
    remote: str,
    requested_branch: str,
    resolved_branch: str | None,
    error: subprocess.CalledProcessError,
) -> str:
    available = list_remote_branches(remote)
    stderr = (error.stderr or "").strip()
    message = [f"Unable to clone repository branch '{requested_branch}' from '{remote}'."]
    if resolved_branch and resolved_branch != requested_branch:
        message.append(f"Remote default branch is '{resolved_branch}', but clone still failed.")
    elif resolved_branch:
        message.append(f"Remote default branch resolves to '{resolved_branch}'.")
    if available:
        message.append(f"Available branches: {', '.join(available)}.")
    if stderr:
        message.append(f"git stderr: {stderr}")
    return " ".join(message)


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
