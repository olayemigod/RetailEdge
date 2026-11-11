#!/usr/bin/env bash
# Validate native runner prerequisites before attempting any network-dependent apt.
# GitHub Ubuntu runners usually ship MySQL development headers and pkg-config.
# Redis runs in the dedicated service container, so redis-tools is not required.
set -euo pipefail

if ! command -v pkg-config >/dev/null 2>&1 ||
   { ! pkg-config --exists mysqlclient && ! pkg-config --exists mariadb; }; then
  echo "::notice::MySQL client development metadata missing; installing MariaDB build prerequisites."
  # Only a genuinely missing compiler dependency should hit the Ubuntu apt
  # mirrors. Never update/remove the runner's existing working MySQL headers.
  for source in /etc/apt/sources.list.d/*; do
    if sudo grep -q 'dl.google.com/linux/chrome-stable' "$source" 2>/dev/null; then
      sudo rm -f "$source"
    fi
  done
  sudo apt-get -o Acquire::Retries=3 update
  sudo apt-get -o Acquire::Retries=3 install -y --no-install-recommends libmariadb-dev pkg-config
fi

if ! pkg-config --exists mysqlclient && ! pkg-config --exists mariadb; then
  echo "::error::Neither mysqlclient nor mariadb compiler metadata is available."
  exit 1
fi

echo "::notice::Verified native MySQL/MariaDB compiler dependencies."
python -m pip install --upgrade frappe-bench

# Probe the same live Redis service that Frappe will use; using the RESP wire
# protocol avoids installing redis-tools solely to run 'redis-cli ping'.
python - <<'PY'
import socket

with socket.create_connection(("127.0.0.1", 6379), timeout=10) as conn:
    conn.sendall(b"*1\r\n$4\r\nPING\r\n")
    response = conn.recv(64)
if response != b"+PONG\r\n":
    raise SystemExit(f"Redis preflight failed: {response!r}")
print("Redis service preflight: PONG")
PY
