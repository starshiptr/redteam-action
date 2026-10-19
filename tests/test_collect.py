import subprocess
from redteam.collect import get_diff


def git(*args):
    subprocess.run(["git", *args], check=True, capture_output=True)


def test_get_diff_shows_branch_change(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    git("init", "-b", "main")
    git("config", "user.email", "test@example.com")   # CI runners have no git identity
    git("config", "user.name", "test")

    (tmp_path / "app.py").write_text("x = 1\n")
    git("add", ".")
    git("commit", "-m", "base")

    git("checkout", "-b", "feature")
    (tmp_path / "app.py").write_text("x = 2\n")
    git("add", ".")
    git("commit", "-m", "change x")

    diff = get_diff("main")
    assert "-x = 1" in diff
    assert "+x = 2" in diff