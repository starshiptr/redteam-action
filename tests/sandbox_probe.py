"""CI-only probe of verify-sandboxed.sh. `setup` writes escape-attempt proofs; `check` asserts they were contained.

Each escape proof asserts the escape WORKED, so it fails (= "confirmed") only when the sandbox holds.
"""
import json
import os
import sys
from pathlib import Path

STATE = Path(os.environ["REDTEAM_STATE"])
CANARY = Path(os.environ["RUNNER_TEMP"]) / "redteam-canary"

PROOFS = {
    "network": "import socket\n\ndef test_escape():\n    socket.create_connection(('1.1.1.1', 53), timeout=3)\n",
    "runner_files": f"def test_escape():\n    open({str(CANARY)!r}, 'w').write('pwned')\n",
    "secrets": "import os\n\ndef test_escape():\n    assert 'GITHUB_TOKEN' in os.environ\n",
    "git_token": "import os\n\ndef test_escape():\n    assert os.path.exists('.git/config')\n",
    "repo_import": "from redteam.cli import main\n\ndef test_bug():\n    assert main is None\n",
    "control_pass": "def test_not_a_bug():\n    assert True\n",
}
EXPECTED = {"network": True, "runner_files": True, "secrets": True, "git_token": True, "repo_import": True,
            "control_pass": False}

if sys.argv[1] == "setup":
    findings = [{"severity": "low", "title": k, "proof_test": v} for k, v in PROOFS.items()]
    STATE.write_text(json.dumps({"status": "done", "findings": findings}))
else:
    findings = json.loads(STATE.read_text())["findings"]
    for f in findings:
        print(f"--- {f['title']}: confirmed={f['confirmed']}\n{f['proof_output'][-600:]}")
    results = {f["title"]: f["confirmed"] for f in findings}
    assert results == EXPECTED, f"sandbox probe mismatch: {results}"
    assert not CANARY.exists(), "a proof wrote to the runner's temp dir"
    print("sandbox holds")
