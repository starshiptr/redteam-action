import json

from redteam import cli


def run(monkeypatch, tmp_path, step, **env):
    monkeypatch.setattr(cli, "STATE", str(tmp_path / "state.json"))
    for k in ("ANTHROPIC_API_KEY", "GITHUB_BASE_REF", "GITHUB_TOKEN", "GITHUB_EVENT_PATH"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return cli.main([step])


def test_unknown_step_prints_usage():
    assert cli.main([]) == 2


def test_attack_skips_without_a_key(monkeypatch, tmp_path):
    assert run(monkeypatch, tmp_path, "attack") == 0
    state = json.loads((tmp_path / "state.json").read_text())
    assert state["status"] == "skipped" and state["post"] is False


def test_report_fails_the_check_on_a_confirmed_high(monkeypatch, tmp_path):
    finding = {"severity": "high", "title": "t", "file": "a.py", "line": 1, "impact": "i",
               "fix_direction": "f", "proof_test": "x", "confirmed": True}
    state = {"status": "done", "model": "claude-opus-5-5", "post": False,
             "usage": {"input_tokens": 1, "output_tokens": 1}, "findings": [finding]}
    (tmp_path / "state.json").write_text(json.dumps(state))

    assert run(monkeypatch, tmp_path, "report", INPUT_FAIL_ON="high") == 1
    assert run(monkeypatch, tmp_path, "report", INPUT_FAIL_ON="critical") == 0
