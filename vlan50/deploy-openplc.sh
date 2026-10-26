#!/usr/bin/env bash
set -euo pipefail

# Run this script inside an OpenPLC container. The candidate ST file must be
# mounted or copied into the container before invocation.
#
# Usage: deploy-openplc.sh FILE NAME DESCRIPTION

candidate=${1:?Structured Text file is required}
program_name=${2:?Program name is required}
program_description=${3:-}
base_url=http://127.0.0.1:8080
cookie_jar=$(mktemp)
upload_page=$(mktemp)
compile_page=$(mktemp)
trap 'rm -f "$cookie_jar" "$upload_page" "$compile_page"' EXIT

openplc_user=${OPENPLC_USERNAME:-openplc}
openplc_password=${OPENPLC_PASSWORD:-openplc}

curl -fsS -c "$cookie_jar" -b "$cookie_jar" \
  --data-urlencode "username=$openplc_user" \
  --data-urlencode "password=$openplc_password" \
  "$base_url/login" >/dev/null

curl -fsS -c "$cookie_jar" -b "$cookie_jar" \
  -F "file=@$candidate" "$base_url/upload-program" >"$upload_page"

program_file=$(sed -n "s/.*value='\([^']*\)' id='prog_file' name='prog_file'.*/\1/p" "$upload_page" | head -n 1)
epoch_time=$(sed -n "s/.*value='\([^']*\)' id='epoch_time' name='epoch_time'.*/\1/p" "$upload_page" | head -n 1)

if [[ -z "$program_file" || -z "$epoch_time" ]]; then
  echo "Unable to parse OpenPLC upload response" >&2
  exit 1
fi

curl -fsS -c "$cookie_jar" -b "$cookie_jar" \
  --data-urlencode "prog_name=$program_name" \
  --data-urlencode "prog_descr=$program_description" \
  --data-urlencode "prog_file=$program_file" \
  --data-urlencode "epoch_time=$epoch_time" \
  "$base_url/upload-program-action" >/dev/null

curl -fsS -c "$cookie_jar" -b "$cookie_jar" \
  "$base_url/compile-program?file=$program_file" >"$compile_page"

for _ in $(seq 1 120); do
  compile_log=$(curl -fsS -c "$cookie_jar" -b "$cookie_jar" "$base_url/compilation-logs")
  if grep -q "Compilation finished successfully" <<<"$compile_log"; then
    curl -fsS -c "$cookie_jar" -b "$cookie_jar" "$base_url/start_plc" >/dev/null
    sleep 2
    dashboard=$(curl -fsS -c "$cookie_jar" -b "$cookie_jar" "$base_url/dashboard")
    if grep -q "Status:.*Running" <<<"$dashboard"; then
      # The pinned upstream runtime defaults to stopped after a reboot.
      # Its entrypoint persists this database in /docker_persistent.
      python3 - <<'PY'
import sqlite3
with sqlite3.connect('/workdir/webserver/openplc.db', timeout=15) as db:
    rows = db.execute("SELECT Value FROM Settings WHERE Key='Start_run_mode'").fetchall()
    if len(rows) != 1:
        raise RuntimeError('Unexpected pinned OpenPLC automatic-start schema')
    db.execute("UPDATE Settings SET Value='true' WHERE Key='Start_run_mode'")
PY
      echo "$program_name: compiled and running; automatic start enabled ($program_file)"
      exit 0
    fi
    echo "$program_name compiled, but runtime did not report Running" >&2
    exit 1
  fi
  if grep -q "Compilation finished with errors" <<<"$compile_log"; then
    printf '%s\n' "$compile_log" >&2
    exit 1
  fi
  sleep 1
done

echo "$program_name compilation timed out" >&2
exit 1
