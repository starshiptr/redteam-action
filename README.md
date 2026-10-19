# redteam-action

A GitHub Action that red-teams each pull request with Claude and **only reports bugs it can prove**.

Claude attacks the PR diff and must attach a pytest test to every finding. The Action then runs each test itself. A finding is reported as confirmed only if its test **fails** on the PR's code. Everything else is listed as unconfirmed. The model suggests; CI verifies.

## Usage

```yaml
# .github/workflows/redteam.yml
on: pull_request            # never pull_request_target

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
      - uses: starshiptr/redteam-action@<sha>
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
2. **verify**: no key, no token. It runs inside a fresh network namespace, so proofs have no network. Each proof runs as an unprivileged user against a read-only copy of the repo without `.git`. A finding is confirmed only when pytest exits 1 **and** reports a failed test.
3. **report**: has the token. It posts one PR comment, updated in place on each push, with the token cost, and applies the `fail-on` gate.

CI runs escape-attempt proofs through the real sandbox on every PR: network access, writing runner files, reading secrets, reading `.git/config`. The sandbox holds only if every escape fails (see `tests/sandbox_probe.py`).

## Limits

- Python repos with pytest only.
- A finding the model can't prove with a failing test is never confirmed. Some real issues, such as design flaws or weak crypto choices, can't be reported this way. That's deliberate: precision over coverage.
- Prompt injection in a PR can make the model miss bugs. It can't make the Action confirm a bug that doesn't fail a test.
- The cost line prices the requested model. A server-side fallback to another model isn't repriced.

## License

MIT
