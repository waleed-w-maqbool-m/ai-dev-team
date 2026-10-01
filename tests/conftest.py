import pytest


@pytest.fixture(autouse=True)
def isolated_workspace(tmp_path, monkeypatch):
    """Every test writes generated files into its own temp dir, never into
    the real workspace/ folder."""
    workspace = tmp_path / "workspace"
    monkeypatch.setenv("AI_TEAM_WORKSPACE", str(workspace))
    return workspace
