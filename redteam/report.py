import html
import json
import re
import urllib.request

MARKER = "<!-- redteam-action -->"
SEVERITY = ["low", "medium", "high", "critical"]
# $ per million tokens (input, output); thinking tokens bill as output
PRICES = {"claude-opus-5-5": (4, 20), "claude-sonnet-5-5": (2, 10)}
ZW = "\u200b"  # zero-width space: breaks a pattern without changing what the reader sees


def cost(model, usage):
    # ponytail: priced at the requested model; a server-side fallback to another model is not repriced
    inp, out = PRICES.get(model, (0, 0))
    return (usage["input_tokens"] * inp + usage["output_tokens"] * out) / 1_000_000


def _safe(text):
    """Model text is untrusted: no HTML, no Markdown links/images/formatting, no @mentions, no autolinks."""
    text = " ".join(str(text).split())  # one line: no new Markdown block (heading, list) can start inside it
    text = html.escape(text, quote=False)  # quotes are harmless outside attributes; escaping them showed &#x27;
    text = re.sub(r"([\\`*_\[\]()!|~])", r"\\\1", text)
    return text.replace("@", "@" + ZW).replace("://", ":" + ZW + "//").replace("www.", "www" + ZW + ".")


def _fence(code):
    """A code fence longer than any backtick run inside the code, so the proof can't close it early."""
    longest = max((len(m) for m in re.findall(r"`+", code)), default=0)
    return "`" * max(3, longest + 1)


def _finding(f):
    tag = f["category"] + (f" · {_safe(f['cwe'])}" if f.get("cwe") else "")
    fence = _fence(f["proof_test"])
    return (
        f"#### {f['severity']} ({tag}): {_safe(f['title'])}\n"
        f"{_safe(f['file'])}, line {int(f['line'])}: {_safe(f['impact'])}\n\n"
        f"**Fix direction:** {_safe(f['fix_direction'])}\n\n"
        f"<details><summary>Proof test (fails on this PR, not before it)</summary>\n\n"
        f"{fence}python\n{f['proof_test']}\n{fence}\n</details>\n"
    )


def render(state):
    if state["status"] == "skipped":
        return f"{MARKER}\n### Red team: skipped\n{_safe(state['reason'])}\n"
    by = {v: [f for f in state["findings"] if f.get("verdict") == v] for v in ("confirmed", "pre-existing", "rejected")}
    lines = [MARKER, f"### Red team: {len(by['confirmed'])} confirmed finding(s)"]
    if not by["confirmed"]:
        lines.append("No bug introduced by this PR was proven by a failing test.")
    lines += [_finding(f) for f in by["confirmed"]]
    for verdict, why in (("pre-existing", "proof also fails before this PR"), ("rejected", "proof test did not fail")):
        if by[verdict]:
            lines.append(f"<details><summary>{len(by[verdict])} {verdict} ({why})</summary>\n")
            lines += [f"- {f['severity']}: {_safe(f['title'])}" for f in by[verdict]]
            lines.append("</details>")
    u = state["usage"]
    lines.append(
        f"\n<sub>{state['model']} · {u['input_tokens']:,} in / {u['output_tokens']:,} out · "
        f"~${cost(state['model'], u):.3f}</sub>"
    )
    return "\n".join(lines)


def should_fail(findings, fail_on):
    if fail_on not in SEVERITY:
        return False  # "none" disables the gate
    floor = SEVERITY.index(fail_on)
    return any(f.get("confirmed") and SEVERITY.index(f["severity"]) >= floor for f in findings)


def _api(method, url, token, body=None):
    req = urllib.request.Request(
        url,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def post(body, repo, pr, token, api="https://api.github.com"):
    """Create the PR comment, or update ours in place on later pushes."""
    # ponytail: first 100 comments only; paginate if PRs get that busy
    comments = _api("GET", f"{api}/repos/{repo}/issues/{pr}/comments?per_page=100", token)
    mine = next((c for c in comments if MARKER in c["body"]), None)
    if mine:
        _api("PATCH", f"{api}/repos/{repo}/issues/comments/{mine['id']}", token, {"body": body})
    else:
        _api("POST", f"{api}/repos/{repo}/issues/{pr}/comments", token, {"body": body})
