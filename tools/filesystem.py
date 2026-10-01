"""Applies the Software Engineer's FileChange entries to a real directory on
disk. Kept separate from agents/ so the SWE agent stays a pure function over
state, and side effects live in one auditable place."""
import os

from schemas.implementation import FileChange, FileAction


def apply_file_changes(root_dir: str, changes: list[FileChange]) -> list[str]:
    """Applies each change under `root_dir`. Returns the list of touched paths."""
    touched = []
    os.makedirs(root_dir, exist_ok=True)
    for change in changes:
        full_path = os.path.join(root_dir, change.path)
        if change.action in (FileAction.create, FileAction.modify):
            os.makedirs(os.path.dirname(full_path) or root_dir, exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(change.content)
            touched.append(full_path)
        elif change.action == FileAction.delete:
            if os.path.exists(full_path):
                os.remove(full_path)
            touched.append(full_path)
    return touched
