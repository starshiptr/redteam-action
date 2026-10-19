from redteam import report


def finding(severity, verdict, title="bug", **extra):
    f = {"severity": severity, "category": "bug", "cwe": "", "title": title, "file": "app.py", "line": 3,
         "impact": "i", "fix_direction": "f", "proof_test": "def test_x(): assert 0",
         "verdict": verdict, "confirmed": verdict == "confirmed"}
    return f | extra


STATE = {
    "status": "done",
    "model": "claude-opus-5-5",
    "usage": {"input_tokens": 10_000, "output_tokens": 3_000},
    "findings": [finding("high", "confirmed", "real @team bug"), finding("low", "rejected", "guess"),
                 finding("medium", "pre-existing", "old bug")],
}


def test_render_lists_confirmed_and_collapses_the_rest():
    body = report.render(STATE)
    assert body.startswith(report.MARKER)
    assert "1 confirmed finding" in body
    assert "real @​team bug" in body  # no @mention ping
    assert "1 rejected" in body and "1 pre-existing" in body
    assert "~$0.100" in body  # 10k in * $4 + 3k out * $20 per MTok


def test_model_text_cannot_inject_html_links_or_images():
    evil = finding("high", "confirmed", title='<img src=x onerror=1>[fix here](https://evil.example) ![p](http://t.co/x.png)',
                   cwe="CWE-79", category="security", impact="see www.evil.example")
    body = report.render(STATE | {"findings": [evil]})
    assert "<img" not in body
    assert "](" not in body.split("<details>")[0]  # no live Markdown link or image before the proof
    assert "https://" not in body and "www.evil" not in body  # no autolinks
    assert "security · CWE-79" in body


def test_proof_with_backticks_cannot_break_out_of_its_code_block():
    proof = "x = '````'\n"
    body = report.render(STATE | {"findings": [finding("high", "confirmed", proof_test=proof)]})
    assert "`````python" in body  # fence is longer than the 4-backtick run inside


def test_gate_fails_only_on_confirmed_findings_at_or_above_the_floor():
    assert report.should_fail(STATE["findings"], "high")
    assert not report.should_fail(STATE["findings"], "critical")
    assert not report.should_fail([finding("critical", "rejected")], "low")  # unconfirmed never fails
    assert not report.should_fail([finding("critical", "pre-existing")], "low")  # not this PR's bug
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
