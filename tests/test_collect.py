import subprocess
from redteam.collect import collect, get_diff


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


def test_collect_bundles_changed_files_and_their_tests(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    git("init", "-b", "main")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "test")

    (tmp_path / "app.py").write_text("x = 1\n")
    (tmp_path / "old.py").write_text("gone soon\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_app.py").write_text("def test_x(): pass\n")
    (tmp_path / "tests" / "test_other.py").write_text("unrelated\n")
    git("add", ".")
    git("commit", "-m", "base")

    git("checkout", "-b", "feature")
    (tmp_path / "app.py").write_text("x = 2\n")       # modified
    (tmp_path / "old.py").unlink()                    # deleted
    (tmp_path / "logo.png").write_bytes(b"\x89PNG\xff\xfe")  # binary
    git("add", "-A")
    git("commit", "-m", "pr")

    bundle = collect("main")
    assert "+x = 2" in bundle["diff"]
    assert bundle["files"] == {"app.py": "x = 2\n"}
    assert bundle["tests"] == {"tests/test_app.py": "def test_x(): pass\n"}