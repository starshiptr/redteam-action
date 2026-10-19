# redteam-action

A GitHub Action that red-teams each pull request with Claude and **only reports bugs it can prove**.

Claude attacks the PR diff and must attach a pytest test to every finding. The Action then runs each test itself, twice: on the PR and on the code before it. A finding is confirmed only if its test **fails on the PR and doesn't fail before it**, so the PR introduced the bug. A test that fails on both (a pre-existing bug, or `assert False`) is not blamed on the PR. The model suggests; CI verifies.

## Usage

```yaml
# .github/workflows/redteam.yml
on: pull_request            # never pull_request_target

concurrency:                # a new push cancels the old run, so rapid pushes don't each pay for a review
  group: redteam-${{ github.event.pull_request.number }}
  cancel-in-progress: true

permissions:
  contents: read
  pull-requests: write      # to post the comment

jobs:
  redteam:
    runs-on: ubuntu-latest  # Linux only (the sandbox uses network namespaces)
    steps:
      - uses: actions/checkout@<sha>
        with:
          fetch-depth: 0    # needed to diff against the base branch
      - uses: actions/setup-python@<sha>
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt   # proof tests import your code
      - uses: starshiptr/redteam-action@<sha>   # the v1.0 commit SHA; pin by SHA, not by tag
        with:
          anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
          fail-on: high     # low | medium | high | critical | none
```

| Input | Default | |
|---|---|---|
| `anthropic-api-key` | (empty) | An empty key skips the run. Fork PRs get no secrets, so they're skipped. |
| `model` | `claude-opus-5-5` | |
| `fail-on` | `high` | The lowest **confirmed** severity that fails the check. |
| `max-chars` | `200000` | Larger PRs are skipped, not truncated. |

## How a finding is verified

Each step gets only what it needs:

1. **attack**: the only step with the API key. It sends the diff, the changed files and their tests to Claude. PR content is marked as untrusted data in the prompt.
2. **verify**: no key, no token. It runs inside a fresh network namespace, so proofs have no network. Each proof runs as an unprivileged user against `git archive` snapshots of the PR and of its merge base (no `.git`, so no checkout token). A run counts as failed only when pytest exits 1 **and** reports a failed test. Verdicts: **confirmed** (fails on the PR only), **pre-existing** (fails on both), **rejected** (doesn't fail).
3. **report**: has the token. It posts one PR comment, updated in place on each push, with the token cost, and applies the `fail-on` gate to confirmed findings only. Model text is sanitised before rendering: no HTML, Markdown links or images, autolinks or @mentions.

Findings carry a category (`security` or `bug`) and a CWE ID where one applies. At most 10 findings per run.

CI runs escape-attempt proofs through the real sandbox on every PR: network access, writing runner files, reading secrets, reading `.git/config`. The sandbox holds only if every escape fails (see `tests/sandbox_probe.py`).

## Results (v1.0, 2026-10-19)

Run on [redteam-eval](https://github.com/starshiptr/redteam-eval). That repo is a small Streamlit + SQLite dashboard after a correctness pass, with 8 open PRs, each reintroducing one real bug that the pass fixed. An oracle test per bug confirmed the setup: `main` passes all 8, and each PR fails only its own.

| PR | Planted bug | Verdict | Cost |
|---|---|---|---|
| [1](https://github.com/starshiptr/redteam-eval/pull/1) | Month filter matches by prefix | confirmed (low) | $0.032 |
| [2](https://github.com/starshiptr/redteam-eval/pull/2) | Month 00 / 13 accepted | confirmed (medium, CWE-20) | $0.015 |
| [3](https://github.com/starshiptr/redteam-eval/pull/3) | Negative amounts saved | confirmed (medium) | $0.015 |
| [4](https://github.com/starshiptr/redteam-eval/pull/4) | Blank amounts pass validation | confirmed (high), plus a second real crash the change introduced | $0.025 |
| [5](https://github.com/starshiptr/redteam-eval/pull/5) | Save wipes and reinserts, so ids change | confirmed (high) | $0.038 |
| [6](https://github.com/starshiptr/redteam-eval/pull/6) | Export overwrites the previous month | confirmed (high) | $0.014 |
| [7](https://github.com/starshiptr/redteam-eval/pull/7) | Export no longer creates its folder | confirmed (medium) | $0.015 |
| [8](https://github.com/starshiptr/redteam-eval/pull/8) | Date check only looks at the shape | confirmed (medium, CWE-20) | $0.016 |

**8/8 planted bugs confirmed, 0 false confirms, ~$0.17 in total (~$0.02 per PR) on `claude-opus-5-5`.** One unproven guess was correctly rejected.

**Read this as "the mechanism works", not as a benchmark:**
- The set is small and easy: one file, logic-level bugs, short diffs, and docstrings that state the intended behaviour.
- The 8 bugs were originally found by a Claude-based agent, so the set leans toward what Claude finds. Human-found bugs would be a harder test.
- One run per PR. The model isn't deterministic.

## Limits

- Python repos with pytest only.
- A finding the model can't prove with a failing test is never confirmed. Some real issues, such as design flaws or weak crypto choices, can't be reported this way. That's deliberate: precision over coverage.
- Prompt injection in a PR can make the model miss bugs. It can't make the Action confirm a bug that doesn't fail a test.
- The base/PR comparison can still be fooled when a proof asserts the old behaviour of something the PR changed on purpose, or tests a function that only exists in the PR with a wrong expected value. Read the proof before acting on a finding.
- Issues a unit test can't show (a leaked secret in the diff, a vulnerable dependency) belong to dedicated scanners such as secret scanning and pip-audit.
- The Action's own dependencies are pinned by version, not by hash.
- The cost line prices the requested model. A server-side fallback to another model isn't repriced.

## License

MIT
