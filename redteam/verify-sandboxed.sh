#!/usr/bin/env bash
# Run the verify step with no network (fresh network namespace) and each proof
# test as an unprivileged user that can't write runner files. Linux runners only.
set -euo pipefail
sudo useradd --system --no-create-home redteam-proof 2>/dev/null || true
PY="$(command -v python3)"
sudo env PATH="$PATH" PYTHONPATH="$PYTHONPATH" REDTEAM_STATE="$REDTEAM_STATE" REDTEAM_PROOF_USER=redteam-proof \
  unshare --net --setuid "$(id -u)" --setgid "$(id -g)" -- "$PY" -m redteam.cli verify
