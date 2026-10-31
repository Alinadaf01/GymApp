#!/usr/bin/env bash
# Restore a backup made by backup.sh.
#
#   sudo infra/backup/restore.sh --key /path/to/basharnia-backup.key <backup.tar.age | remote:path> [--yes]
#   sudo infra/backup/restore.sh --key KEY --latest [--yes]      # newest local daily backup
#
# For drills (restore elsewhere, production untouched):
#   --target-db NAME    restore into this database (re-created)
#   --target-dir DIR    restore files into this directory
#   --no-stop           do not stop api/worker (only with --target-db and --target-dir)
#
# The private age key is required; it is not stored on the server.
set -euo pipefail
# shellcheck source=common.sh
source "$(dirname "$0")/common.sh"

KEY="" SRC="" YES=0 TARGET_DB="" TARGET_DIR="" STOP=1 LATEST=0
while [[ $# -gt 0 ]]; do
  case $1 in
    --key) KEY=$2; shift 2 ;;
    --yes) YES=1; shift ;;
    --latest) LATEST=1; shift ;;
    --target-db) TARGET_DB=$2; shift 2 ;;
    --target-dir) TARGET_DIR=$2; shift 2 ;;
    --no-stop) STOP=0; shift ;;
    -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
    *) SRC=$1; shift ;;
  esac
done
[[ -f $KEY ]] || die "--key: age private key file not found"
if [[ $LATEST == 1 ]]; then
  SRC=$(find "$BACKUP_DIR/daily" -maxdepth 1 -name 'basharnia-*.tar.age' | sort | tail -1)
fi
[[ -n $SRC ]] || die "no backup given"
if [[ $STOP == 0 && ( -z $TARGET_DB || -z $TARGET_DIR ) ]]; then
  die "--no-stop is only allowed together with --target-db and --target-dir"
fi
DB=${TARGET_DB:-$PGDATABASE}
DIR=${TARGET_DIR:-$STORAGE_PATH}

umask 077
WORK=$(mktemp -d /tmp/basharnia-restore-XXXXXX)
trap 'remove_tree "$WORK"' EXIT

if [[ $SRC == *:* && ! -f $SRC ]]; then
  log "downloading $SRC"
  rclone copyto "$SRC" "$WORK/backup.tar.age"
  SRC="$WORK/backup.tar.age"
fi

log "decrypting $(basename "$SRC")"
age -d -i "$KEY" "$SRC" | tar -C "$WORK" -xf - MANIFEST db.dump files.tar.gz
(cd "$WORK" && sed -n '/^\[sha256\]$/,$p' MANIFEST | tail -n +2 | sha256sum -c --quiet) \
  || die "checksum mismatch: the backup is damaged"
log "checksums OK"
echo "------ MANIFEST ------"; sed -n '1,5p' "$WORK/MANIFEST"; echo "----------------------"

if [[ $YES != 1 ]]; then
  read -r -p "Restore into database '$DB' and directory '$DIR'? Existing data there is REPLACED. Type 'restore': " ans
  [[ $ans == restore ]] || die "aborted"
fi

if [[ $STOP == 1 && $DB_MODE == compose ]]; then
  log "stopping api and worker"
  compose stop api worker
fi

log "restoring database into '$DB'"
pg dropdb --if-exists --force "$DB"
pg createdb -O "$PGUSER" "$DB"
pg pg_restore --no-owner --role="$PGUSER" --exit-on-error -d "$DB" < "$WORK/db.dump"

log "restoring files into $DIR"
if [[ -d $DIR && -n $(ls -A "$DIR" 2>/dev/null) ]]; then
  ASIDE="$DIR.before-restore-$(date -u +%Y%m%dT%H%M%SZ)"
  mv "$DIR" "$ASIDE"
  log "previous files moved to $ASIDE (delete it yourself once satisfied)"
fi
mkdir -p "$DIR"
tar -C "$DIR" -xzf "$WORK/files.tar.gz"
if [[ $DIR == "$STORAGE_PATH" ]]; then chown -R 10001:10001 "$DIR" 2>/dev/null || true; fi

if [[ $STOP == 1 && $DB_MODE == compose ]]; then
  log "starting api and worker (migrations run first)"
  compose up -d migrate api worker
fi
log "restore OK"
