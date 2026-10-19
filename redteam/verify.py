import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Only these reach a proof test. Keys, tokens and runner command files (GITHUB_ENV etc.) never do.
SAFE_ENV = ("PATH", "HOME", "LANG", "SYSTEMROOT", "TEMP", "TMP", "TMPDIR")
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


def verify(findings, repo_dir="."):
    """Confirm a finding only if its proof test FAILS: pytest exit code 1 AND pytest reports a failure.

    Exit code 1 alone isn't enough: sudo, env or a missing interpreter also exit 1.
    """
    with tempfile.TemporaryDirectory() as d:
        if os.environ.get("REDTEAM_PROOF_USER"):
            repo_dir = _readonly_copy(repo_dir, d)
        for f in findings:
            code, output = run_proof(f["proof_test"], repo_dir)
            f["confirmed"] = code == 1 and re.search(r"\b\d+ failed\b", output) is not None
            f["proof_output"] = output
    return findings


def _readonly_copy(repo_dir, into):
    """Copy the repo without .git (checkout keeps the GitHub token in .git/config) where the proof user can read it."""
    # ponytail: full copy per run; fine for normal repos, add an ignore list if huge repos get slow
    dest = shutil.copytree(repo_dir, Path(into) / "repo", ignore=shutil.ignore_patterns(".git"))
    os.chmod(into, 0o755)
    return dest
