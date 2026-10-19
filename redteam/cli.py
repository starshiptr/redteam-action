import json
import os
import sys

STATE = os.environ.get("REDTEAM_STATE", "redteam-state.json")
MAX_CHARS = 200_000  # ~50k tokens; bigger PRs are skipped, not truncated


def load():
    with open(STATE, encoding="utf-8") as f:
        return json.load(f)


def save(state):
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(state, f)
    return 0


def attack_step():
    from redteam.attack import MODEL, attack, build_prompt
    from redteam.collect import collect

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return save({"status": "skipped", "reason": "No ANTHROPIC_API_KEY (fork PRs get no secrets).", "post": False})
    base = os.environ.get("GITHUB_BASE_REF")
    if not base:
        return save({"status": "skipped", "reason": "Not a pull request.", "post": False})
    bundle = collect(f"origin/{base}")
    size = len(build_prompt(bundle))
    cap = int(os.environ.get("INPUT_MAX_CHARS") or MAX_CHARS)
    if size > cap:
        return save({"status": "skipped", "reason": f"PR too large to review ({size:,} > {cap:,} chars).", "post": True})
    model = os.environ.get("INPUT_MODEL") or MODEL
    findings, usage = attack(bundle, model=model)
    usage = {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens}
    return save({"status": "done", "model": model, "findings": findings, "usage": usage, "post": True})


def verify_step():
    from redteam.verify import verify

    state = load()
    if state["status"] == "done":
        verify(state["findings"])
    return save(state)  # written after every proof ran, so a proof can't forge the result


def report_step():
    from redteam import report

    state = load()
    body = report.render(state)
    print(body)
    token, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    if state.get("post") and token and repo and os.environ.get("GITHUB_EVENT_PATH"):
        with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as f:
            pr = json.load(f)["pull_request"]["number"]
        report.post(body, repo, pr, token)
    if state["status"] == "done" and report.should_fail(state["findings"], os.environ.get("INPUT_FAIL_ON", "high")):
        print("redteam: confirmed finding at or above fail-on; failing the check")
        return 1
    return 0


STEPS = {"attack": attack_step, "verify": verify_step, "report": report_step}


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if not args or args[0] not in STEPS:
        print(f"usage: python -m redteam.cli {{{'|'.join(STEPS)}}}")
        return 2
    return STEPS[args[0]]()


if __name__ == "__main__":
    sys.exit(main())
