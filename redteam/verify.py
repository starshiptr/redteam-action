import io
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

# Only these reach a proof test. Keys, tokens and runner command files (GITHUB_ENV etc.) never do.
SAFE_ENV = ("PATH", "HOME", "LANG", "TEMP", "TMP", "TMPDIR",
            # Windows system paths and CPU info (not secrets); without them Python crashes intermittently
            "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "SYSTEMDRIVE", "USERPROFILE", "APPDATA", "LOCALAPPDATA",
            "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE")
TIMEOUT = 120


def run_proof(test_code, repo_dir="."):
    """Run one proof test; return (pytest exit code, last lines of output)."""
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "test_redteam_proof.py"
        path.write_text(test_code, encoding="utf-8")
        os.chmod(d, 0o755)  # readable by the proof user
        env = {k: os.environ[k] for k in SAFE_ENV if k in os.environ}
        env["HOME"] = d
        env["PYTHONPATH"] = str(Path(repo_dir).resolve())
        cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(path)]
        user = os.environ.get("REDTEAM_PROOF_USER")
        if user:  # CI: run as an unprivileged user that can't touch runner files
            cmd = ["sudo", "-n", "-u", user, "env", *(f"{k}={v}" for k, v in env.items()), *cmd]
        try:
            r = subprocess.run(
                cmd,
                cwd=repo_dir,
                env=env,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            return None, f"timed out after {TIMEOUT}s"
        return r.returncode, (r.stdout + r.stderr)[-1500:]


def _failed(code, output):
    # Exit code 1 alone isn't enough: sudo, env or a missing interpreter also exit 1.
    return code == 1 and re.search(r"\b\d+ failed\b", output) is not None


def verify(findings, head_dir=".", base_dir=None):
    """Differential check: a finding is confirmed only if its proof FAILS on the PR and does NOT fail on the base.

    Failing on both means a pre-existing bug or a test that proves nothing (e.g. `assert False`),
    so it isn't blamed on the PR.
    """
    for f in findings:
        code, output = run_proof(f["proof_test"], head_dir)
        f["head_failed"] = _failed(code, output)
        f["base_failed"] = bool(f["head_failed"] and base_dir and _failed(*run_proof(f["proof_test"], base_dir)))
        f["proof_output"] = output
        if not f["head_failed"]:
            f["verdict"] = "rejected"
        else:
            f["verdict"] = "pre-existing" if f["base_failed"] else "confirmed"
        f["confirmed"] = f["verdict"] == "confirmed"
    return findings


def snapshot(ref, into):
    """Export a commit's files with git archive: no .git (checkout keeps the token there), readable by the proof user."""
    dest = Path(into) / ref.replace("/", "_")
    dest.mkdir(parents=True)
    tar = subprocess.run(["git", "archive", "--format=tar", ref], capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(tar)) as t:
        t.extractall(dest, filter="data")
    os.chmod(into, 0o755)
    return dest
