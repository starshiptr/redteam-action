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


def test_proof_can_import_the_repo_under_test():
    [f] = verify([finding("from redteam.cli import main\n\ndef test_bug():\n    assert main is None\n")])
    assert f["confirmed"] is True  # failed on the assert, so the import worked


def test_proof_cannot_see_secrets(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret")
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_secret")
    proof = "import os\n\ndef test_bug():\n    assert 'ANTHROPIC_API_KEY' in os.environ or 'GITHUB_TOKEN' in os.environ\n"
    [f] = verify([finding(proof)])
    assert f["confirmed"] is True  # the assert failed: neither secret was visible
