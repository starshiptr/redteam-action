import subprocess

def get_diff(base):
    result = subprocess.run(
        ["git", "diff", f"{base}...HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout
