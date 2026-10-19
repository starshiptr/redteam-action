from redteam.verify import verify


def finding(proof):
    return {"severity": "high", "title": "t", "proof_test": proof}


def test_failing_proof_is_confirmed():
    [f] = verify([finding("def test_bug():\n    assert 1 == 2\n")])
    assert f["confirmed"] is True


def test_passing_proof_is_rejected():
    [f] = verify([finding("def test_bug():\n    assert 1 == 1\n")])
    assert f["confirmed"] is False


def test_broken_proof_is_rejected():
    [f] = verify([finding("from redteam.nothing import x\n\ndef test_bug():\n    pass\n")])
    assert f["confirmed"] is False


def test_exit_code_1_without_a_pytest_failure_is_rejected(monkeypatch):
    # e.g. sudo or env failing before pytest runs also exits 1
    monkeypatch.setattr("redteam.verify.run_proof", lambda code, repo: (1, "sudo: unknown user"))
    [f] = verify([finding("def test_bug():\n    assert True\n")])
    assert f["confirmed"] is False


def test_proof_can_import_the_repo_under_test():
    [f] = verify([finding("from redteam.cli import main\n\ndef test_bug():\n    assert main is None\n")])
    assert f["confirmed"] is True  # failed on the assert, so the import worked


def two_versions(tmp_path):
    """The code before the PR (base) and after it (head): the PR breaks add()."""
    base, head = tmp_path / "base", tmp_path / "head"
    for d, body in ((base, "a + b"), (head, "a - b")):
        d.mkdir()
        (d / "calc.py").write_text(f"def add(a, b):\n    return {body}\n")
    return head, base


def test_bug_introduced_by_the_pr_is_confirmed(tmp_path):
    head, base = two_versions(tmp_path)
    [f] = verify([finding("from calc import add\n\ndef test_add():\n    assert add(2, 2) == 4\n")], head, base)
    assert (f["head_failed"], f["base_failed"], f["verdict"]) == (True, False, "confirmed")


def test_proof_that_fails_before_the_pr_too_is_not_blamed_on_it(tmp_path):
    head, base = two_versions(tmp_path)
    [f] = verify([finding("def test_nothing():\n    assert False\n")], head, base)
    assert f["verdict"] == "pre-existing" and f["confirmed"] is False


def test_snapshot_exports_a_commit_without_git(tmp_path, monkeypatch):
    import subprocess

    from redteam.verify import snapshot

    monkeypatch.chdir(tmp_path)
    for args in (["init", "-b", "main"], ["config", "user.email", "t@e.com"], ["config", "user.name", "t"]):
        subprocess.run(["git", *args], check=True, capture_output=True)
    (tmp_path / "calc.py").write_text("v1\n")
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-qm", "v1"], check=True)
    (tmp_path / "calc.py").write_text("v2 uncommitted\n")

    out = snapshot("HEAD", tmp_path / "snap")
    assert (out / "calc.py").read_text() == "v1\n"  # the commit, not the working tree
    assert not (out / ".git").exists()


def test_proof_cannot_see_secrets(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret")
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_secret")
    proof = "import os\n\ndef test_bug():\n    assert 'ANTHROPIC_API_KEY' in os.environ or 'GITHUB_TOKEN' in os.environ\n"
    [f] = verify([finding(proof)])
    assert f["confirmed"] is True  # the assert failed: neither secret was visible
