"""Recorded runs: saved by every entry point, listed and served to the web
console, and never readable outside the replay folders."""
import pytest
from fastapi.testclient import TestClient

from utils import replays


@pytest.fixture
def replay_dirs(tmp_path, monkeypatch):
    local, published = tmp_path / "local", tmp_path / "published"
    monkeypatch.setattr(replays, "LOCAL_DIR", str(local))
    monkeypatch.setattr(replays, "PUBLISHED_DIR", str(published))
    monkeypatch.setattr(replays, "BENCH_GLOB", str(tmp_path / "bench" / "*" / "*" / "replay.json"))
    return local, published


def _messages(ts="2026-09-01T10:00:00+00:00"):
    return [{"sender": "project_manager", "message_type": "plan", "payload": {"tasks": []}, "timestamp": ts}]


def test_saved_replays_are_listed_newest_first_without_messages(replay_dirs):
    local, published = replay_dirs
    replays.save_replay(replays.build_replay("old", "a", _messages("2026-01-01T00:00:00+00:00"), source="cli"), str(local))
    replays.save_replay(replays.build_replay("new", "b", _messages("2026-09-01T00:00:00+00:00"), source="curated"), str(published))

    listed = replays.list_replays()
    assert [r["id"] for r in listed] == ["new", "old"]
    assert all("messages" not in r for r in listed)
    assert replays.load_replay("old")["messages"][0]["message_type"] == "plan"


def test_published_copy_wins_over_a_local_one_with_the_same_id(replay_dirs):
    local, published = replay_dirs
    replays.save_replay(replays.build_replay("x", "local", _messages(), source="cli"), str(local))
    replays.save_replay(replays.build_replay("x", "published", _messages(), source="curated"), str(published))
    assert [r["request"] for r in replays.list_replays()] == ["published"]


@pytest.mark.parametrize("bad", ["../secrets", "a/b", "..", "x" * 200, ""])
def test_unsafe_ids_are_refused(replay_dirs, bad):
    assert replays.load_replay(bad) is None


def test_api_serves_replays_and_404s_unknown_ones(replay_dirs):
    import api

    local, _ = replay_dirs
    replays.save_replay(replays.build_replay("run-1", "req", _messages(), source="live"), str(local))
    client = TestClient(api.app)
    assert [r["id"] for r in client.get("/api/replays").json()] == ["run-1"]
    assert client.get("/api/replays/run-1").json()["request"] == "req"
    assert client.get("/api/replays/nope").status_code == 404
    bench = client.get("/api/benchmark").json()
    assert bench["task_count"] == 12 and isinstance(bench["configs"], list)


def test_console_routes_fall_back_to_the_app_shell(tmp_path, monkeypatch):
    import api

    (tmp_path / "index.html").write_text("<div id=root></div>")
    (tmp_path / "poster.jpg").write_bytes(b"jpg")
    monkeypatch.setattr(api, "DIST_DIR", str(tmp_path))
    client = TestClient(api.app)
    assert "root" in client.get("/theater").text
    assert client.get("/poster.jpg").content == b"jpg"
    # Paths that escape the build folder get the shell, not the file.
    assert "root" in client.get("/..%2F..%2Fapi.py").text
