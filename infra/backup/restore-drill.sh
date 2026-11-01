#!/usr/bin/env bash
# Restore drill: prove a backup really restores — without touching production.
# Restores into a scratch database + directory, compares every table's row count
# and every file's checksum with the live system, then removes the scratch copies.
#
#   sudo infra/backup/restore-drill.sh --key /path/to/basharnia-backup.key [backup.tar.age]
#
# Exit 0 = identical to live; 2 = restored fine but live data changed since the backup.
set -euo pipefail
# shellcheck source=common.sh
source "$(dirname "$0")/common.sh"

KEY="" SRC=""
while [[ $# -gt 0 ]]; do
  case $1 in --key) KEY=$2; shift 2 ;; *) SRC=$1; shift ;; esac
done
[[ -f $KEY ]] || die "--key: age private key file not found"
SRC=${SRC:-$(find "$BACKUP_DIR/daily" -maxdepth 1 -name 'basharnia-*.tar.age' | sort | tail -1)}
[[ -n $SRC ]] || die "no backup found"

DRILL_DB="${PGDATABASE}_restore_drill"
DRILL_DIR=$(mktemp -d /tmp/basharnia-drill-XXXXXX)
cleanup() { pg dropdb --if-exists --force "$DRILL_DB" >/dev/null 2>&1 || true; remove_tree "$DRILL_DIR"; }
trap cleanup EXIT

"$(dirname "$0")/restore.sh" --key "$KEY" --yes --no-stop --target-db "$DRILL_DB" --target-dir "$DRILL_DIR/files" "$SRC"

counts() {  # exact row count of every table in database $1
  # Inner command reads /dev/null: `docker compose exec -T` would otherwise swallow
  # the rest of the table list from the loop's stdin (only the first table counted).
  pg psql -d "$1" -Atqc "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY 1" \
    | while read -r t; do printf '%s=%s\n' "$t" "$(pg psql -d "$1" -Atqc "SELECT count(*) FROM \"$t\"" </dev/null)"; done
}
log "comparing row counts (live vs restored)"
diff <(counts "$PGDATABASE") <(counts "$DRILL_DB") > "$DRILL_DIR/rows.diff" || true
log "comparing file checksums (live vs restored)"
(cd "$STORAGE_PATH" && find . -path ./audio/temporary -prune -o -type f -print0 | sort -z | xargs -0 -r sha256sum) > "$DRILL_DIR/live.sha"
(cd "$DRILL_DIR/files" && find . -type f -print0 | sort -z | xargs -0 -r sha256sum) > "$DRILL_DIR/restored.sha"
diff "$DRILL_DIR/live.sha" "$DRILL_DIR/restored.sha" > "$DRILL_DIR/files.diff" || true

tables=$(counts "$DRILL_DB" | wc -l)
[[ $tables -ge 10 ]] || die "only $tables tables found in the restored database — schema incomplete"
nfiles=$(wc -l < "$DRILL_DIR/restored.sha")
if [[ -s $DRILL_DIR/rows.diff || -s $DRILL_DIR/files.diff ]]; then
  echo "Differences (expected only if data changed after the backup was taken):"
  cat "$DRILL_DIR/rows.diff" "$DRILL_DIR/files.diff"
  log "restore drill: backup restored, but live data differs from it (see above)"
  exit 2
fi
log "restore drill PASSED: $tables tables and $nfiles files identical to live"
