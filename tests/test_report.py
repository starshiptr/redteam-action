from redteam import report


def finding(severity, confirmed, title="bug"):
    return {"severity": severity, "title": title, "file": "app.py", "line": 3, "impact": "i",
            "fix_direction": "f", "proof_test": "def test_x(): assert 0", "confirmed": confirmed}


STATE = {
    "status": "done",
    "model": "claude-opus-5-5",
    "usage": {"input_tokens": 10_000, "output_tokens": 3_000},
    "findings": [finding("high", True, "real @team bug"), finding("low", False, "guess")],
}


def test_render_lists_confirmed_and_collapses_the_rest():
    body = report.render(STATE)
    assert body.startswith(report.MARKER)
    assert "1 confirmed finding" in body
    assert "real @​team bug" in body  # no @mention ping
    assert "1 unconfirmed" in body
    assert "~$0.100" in body  # 10k in * $4 + 3k out * $20 per MTok


def test_gate_fails_only_on_confirmed_findings_at_or_above_the_floor():
    assert report.should_fail(STATE["findings"], "high")
    assert not report.should_fail(STATE["findings"], "critical")
    assert not report.should_fail([finding("critical", False)], "low")  # unconfirmed never fails
    assert not report.should_fail(STATE["findings"], "none")


def test_post_creates_then_updates_one_comment(monkeypatch):
    calls, comments = [], []

    def fake_api(method, url, token, body=None):
        calls.append((method, url))
        if method == "GET":
            return comments
        if method == "POST":
            comments.append({"id": 7, "body": body["body"]})
        return {}

    monkeypatch.setattr(report, "_api", fake_api)
    report.post(report.MARKER + " v1", "o/r", 5, "t")
    report.post(report.MARKER + " v2", "o/r", 5, "t")

    assert [m for m, _ in calls] == ["GET", "POST", "GET", "PATCH"]
    assert calls[-1][1].endswith("/issues/comments/7")
