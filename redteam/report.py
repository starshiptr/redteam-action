import json
import urllib.request

MARKER = "<!-- redteam-action -->"
SEVERITY = ["low", "medium", "high", "critical"]
# $ per million tokens (input, output); thinking tokens bill as output
PRICES = {"claude-opus-5-5": (4, 20), "claude-sonnet-5-5": (2, 10)}


def cost(model, usage):
    # ponytail: priced at the requested model; a server-side fallback to another model is not repriced
    inp, out = PRICES.get(model, (0, 0))
    return (usage["input_tokens"] * inp + usage["output_tokens"] * out) / 1_000_000


def _safe(text):
    return str(text).replace("@", "@​")  # model text must never ping people


def _finding(f):
    return (
        f"#### `{f['severity']}` {_safe(f['title'])}\n"
        f"`{_safe(f['file'])}:{f['line']}`: {_safe(f['impact'])}\n\n"
        f"**Fix direction:** {_safe(f['fix_direction'])}\n\n"
        f"<details><summary>Proof test</summary>\n\n````python\n{f['proof_test']}\n````\n</details>\n"
    )


def render(state):
    if state["status"] == "skipped":
        return f"{MARKER}\n### Red team: skipped\n{_safe(state['reason'])}\n"
    confirmed = [f for f in state["findings"] if f.get("confirmed")]
    rejected = [f for f in state["findings"] if not f.get("confirmed")]
    lines = [MARKER, f"### Red team: {len(confirmed)} confirmed finding(s)"]
    if not confirmed:
        lines.append("No bug was proven by a failing test.")
    lines += [_finding(f) for f in confirmed]
    if rejected:
        lines.append(f"<details><summary>{len(rejected)} unconfirmed (proof test did not fail)</summary>\n")
        lines += [f"- `{f['severity']}` {_safe(f['title'])}" for f in rejected]
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
