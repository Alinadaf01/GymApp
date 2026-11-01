#!/usr/bin/env bash
# Encrypted backup of the database + private files, with local and off-site retention.
#   sudo /opt/basharnia/infra/backup/backup.sh     (run daily by basharnia-backup.timer)
#
# Produces BACKUP_DIR/daily/basharnia-<UTC timestamp>.tar.age containing:
#   db.dump        pg_dump custom format (verified with pg_restore --list)
#   files.tar.gz   STORAGE_PATH (photos, PDFs, logo); temporary audio excluded
#   MANIFEST       sizes, sha256 checksums, row counts, schema revision
# The archive is encrypted with age to AGE_RECIPIENT (only the public key is on the server).
set -euo pipefail
# shellcheck source=common.sh
source "$(dirname "$0")/common.sh"

[[ ${AGE_RECIPIENT:-} == age1* ]] || die "AGE_RECIPIENT (age public key) is not set"
command -v age >/dev/null || die "age is not installed"
[[ -d $STORAGE_PATH ]] || die "STORAGE_PATH $STORAGE_PATH does not exist"

mkdir -p "$BACKUP_DIR/daily" "$BACKUP_DIR/weekly"
exec 9>"$BACKUP_DIR/.lock"
flock -n 9 || die "another backup is running"

on_error() {
  log "backup FAILED (line $1)"
  notify "⚠️ بکاپ Basharnia ناموفق بود ($(hostname), $(date -u +%F)). جزئیات: journalctl -u basharnia-backup"
}
trap 'on_error $LINENO' ERR

umask 077
TS=$(date -u +%Y%m%dT%H%M%SZ)
WORK=$(mktemp -d "$BACKUP_DIR/.work-XXXXXX")
trap 'remove_tree "$WORK"' EXIT

log "dumping database $PGDATABASE"
pg pg_dump --format=custom --no-owner --no-privileges > "$WORK/db.dump"
pg pg_restore --list < "$WORK/db.dump" > "$WORK/db.toc"  # fails on a corrupt dump
[[ $(grep -c "TABLE DATA" "$WORK/db.toc") -gt 0 ]] || die "dump contains no table data"

log "archiving files from $STORAGE_PATH"
tar -C "$STORAGE_PATH" --exclude=./audio/temporary -czf "$WORK/files.tar.gz" .

log "writing manifest"
{
  echo "created_utc=$TS"
  echo "host=$(hostname)"
  echo "database=$PGDATABASE"
  echo "schema_revision=$(pg psql -Atqc 'SELECT version_num FROM alembic_version' 2>/dev/null || echo unknown)"
  echo "files_count=$(tar -tzf "$WORK/files.tar.gz" | grep -vc '/$' || true)"
  echo "[row_counts]"
  pg psql -Atqc "SELECT relname || '=' || n_live_tup FROM pg_stat_user_tables ORDER BY relname" || true
  echo "[sha256]"
  (cd "$WORK" && sha256sum db.dump files.tar.gz)
} > "$WORK/MANIFEST"

OUT="$BACKUP_DIR/daily/basharnia-$TS.tar.age"
tar -C "$WORK" -cf - MANIFEST db.dump files.tar.gz | age -r "$AGE_RECIPIENT" > "$OUT.partial"
mv "$OUT.partial" "$OUT"
log "created $(basename "$OUT") ($(du -h "$OUT" | cut -f1))"

if [[ $(date -u +%u) == "$WEEKLY_DAY" ]]; then
  cp "$OUT" "$BACKUP_DIR/weekly/"
  log "weekly copy kept"
fi

# Keep the newest N archives in a directory (deletes by exact file name only)
prune_local() {
  local dir=$1 keep=$2 f
  find "$dir" -maxdepth 1 -type f -name 'basharnia-*.tar.age' -printf '%f\n' | sort -r | tail -n +"$((keep + 1))" \
    | while read -r f; do
        find "$dir" -maxdepth 1 -type f -name "$f" -delete
        log "pruned $dir/$f"
      done
}
prune_local "$BACKUP_DIR/daily" "$KEEP_DAILY"
prune_local "$BACKUP_DIR/weekly" "$KEEP_WEEKLY"

if [[ -n $RCLONE_REMOTE ]]; then
  log "off-site copy to $RCLONE_REMOTE"
  for tier in daily weekly; do
    rclone copy --no-traverse "$BACKUP_DIR/$tier" "$RCLONE_REMOTE/$tier" --include 'basharnia-*.tar.age'
    keep=$KEEP_DAILY
    [[ $tier == weekly ]] && keep=$KEEP_WEEKLY
    rclone lsf "$RCLONE_REMOTE/$tier" --include 'basharnia-*.tar.age' | sort -r | tail -n +"$((keep + 1))" \
      | while read -r f; do rclone deletefile "$RCLONE_REMOTE/$tier/$f"; log "pruned remote $tier/$f"; done
  done
  # Verify the newest archive arrived intact
  local_sum=$(sha256sum "$OUT" | cut -d' ' -f1)
  remote_sum=$(rclone cat "$RCLONE_REMOTE/daily/$(basename "$OUT")" | sha256sum | cut -d' ' -f1)
  [[ $local_sum == "$remote_sum" ]] || die "off-site copy checksum mismatch"
  log "off-site copy verified (sha256)"
else
  log "WARNING: RCLONE_REMOTE not set — no off-site copy (required by the backup policy)"
fi
log "backup OK"
