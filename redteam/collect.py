import subprocess
from pathlib import Path


def _git(*args):
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        encoding="utf-8",
        errors="replace",  # non-UTF-8 bytes in a PR must not crash the collector
        check=True,
    )
    return result.stdout


def get_diff(base):
    return _git("diff", f"{base}...HEAD")


def changed_files(base):
    # --diff-filter=d drops deleted files (nothing left to read); -z keeps odd filenames intact
    out = _git("diff", "--name-only", "-z", "--diff-filter=d", f"{base}...HEAD")
    return [p for p in out.split("\0") if p]


def _read_text(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None  # binary file: nothing for Claude to read


def find_tests(paths):
    # ponytail: matches test_<name>.py by filename only; add import tracing if tests live under other names
    wanted = {f"test_{Path(p).name}" for p in paths if p.endswith(".py")}
    tracked = _git("ls-files", "-z").split("\0")
    return [t for t in tracked if Path(t).name in wanted and t not in paths]


def collect(base):
    files = {}
    for p in changed_files(base):
        text = _read_text(p)
        if text is not None:
            files[p] = text
    tests = {t: _read_text(t) for t in find_tests(list(files))}
    return {"diff": get_diff(base), "files": files, "tests": tests}
