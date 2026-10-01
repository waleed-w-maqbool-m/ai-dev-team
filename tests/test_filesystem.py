"""File paths in FileChange come straight from model output, so the
workspace boundary must hold no matter what the model asks for."""
import os

from schemas.implementation import FileAction, FileChange
from tools.filesystem import apply_file_changes, resolve_in_workspace


def test_relative_and_nested_paths_resolve_inside(tmp_path):
    assert resolve_in_workspace(str(tmp_path), "cli.py") == os.path.realpath(tmp_path / "cli.py")
    assert resolve_in_workspace(str(tmp_path), "pkg/mod.py") == os.path.realpath(tmp_path / "pkg" / "mod.py")
    assert resolve_in_workspace(str(tmp_path), "pkg/../cli.py") == os.path.realpath(tmp_path / "cli.py")


def test_escaping_paths_are_rejected(tmp_path):
    outside = tmp_path.parent / "outside.py"
    for bad in ["../outside.py", "pkg/../../outside.py", str(outside), ".", ""]:
        assert resolve_in_workspace(str(tmp_path), bad) is None, bad


def test_sibling_dir_with_shared_prefix_is_rejected(tmp_path):
    # "/tmp/ws" vs "/tmp/ws-evil": a naive startswith() check passes this.
    root = tmp_path / "ws"
    root.mkdir()
    assert resolve_in_workspace(str(root), "../ws-evil/x.py") is None


def test_apply_skips_rejected_changes_and_writes_the_rest(tmp_path):
    root = tmp_path / "ws"
    changes = [
        FileChange(path="ok.py", action=FileAction.create, content="x = 1\n"),
        FileChange(path="../escape.py", action=FileAction.create, content="boom\n"),
    ]
    applied, rejected = apply_file_changes(str(root), changes)

    assert [c.path for c in applied] == ["ok.py"]
    assert rejected == ["../escape.py"]
    assert (root / "ok.py").read_text() == "x = 1\n"
    assert not (tmp_path / "escape.py").exists()


def test_delete_cannot_remove_files_outside(tmp_path):
    root = tmp_path / "ws"
    victim = tmp_path / "keep.txt"
    victim.write_text("important")
    apply_file_changes(str(root), [FileChange(path="../keep.txt", action=FileAction.delete)])
    assert victim.exists()
