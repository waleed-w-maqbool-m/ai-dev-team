"""Applies the Software Engineer's FileChange entries to a real directory on
disk. Kept separate from agents/ so the SWE agent stays a pure function over
state, and side effects live in one auditable place."""
import os

from schemas.implementation import FileChange, FileAction


def resolve_in_workspace(root_dir: str, rel_path: str) -> str | None:
    """Returns the absolute path for `rel_path` under `root_dir`, or None if
    it would land outside it. File paths come straight from model output, so
    "../../x", an absolute path, or a symlink out of the workspace must never
    be written to or executed."""
    root = os.path.realpath(root_dir)
    full = os.path.realpath(os.path.join(root, rel_path))
    if full == root or os.path.commonpath([root, full]) != root:
        return None
    return full


def apply_file_changes(root_dir: str, changes: list[FileChange]) -> tuple[list[FileChange], list[str]]:
    """Applies each change under `root_dir`. Returns (applied changes,
    rejected paths) — a rejected change is skipped, not fatal, so one bad
    path from the model doesn't abort the whole run."""
    applied: list[FileChange] = []
    rejected: list[str] = []
    os.makedirs(root_dir, exist_ok=True)
    for change in changes:
        full_path = resolve_in_workspace(root_dir, change.path)
        if full_path is None:
            rejected.append(change.path)
            continue
        if change.action in (FileAction.create, FileAction.modify):
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(change.content)
        elif change.action == FileAction.delete:
            if os.path.isfile(full_path):
                os.remove(full_path)
        applied.append(change)
    return applied, rejected
