#!/usr/bin/env bash
# Integration test for infra/backup/*.sh (development/test machines only).
# Runs the real scripts in DB_MODE=local against a PostgreSQL reachable through
# the PG* environment variables, with a local-directory rclone remote standing
# in for the off-site storage.
#
#   PGHOST=localhost PGUSER=basharnia PGPASSWORD=... PGDATABASE=basharnia_dev \
#   STORAGE_PATH=/path/to/dev/storage infra/tests/test-backup-restore.sh
set -euo pipefail
cd "$(dirname "$0")/../.."

: "${PGDATABASE:?}" "${STORAGE_PATH:?}"
T=$(mktemp -d /tmp/basharnia-backuptest-XXXXXX)
cleanup() { find "$T" -depth -delete 2>/dev/null || true; }
trap cleanup EXIT
pass() { echo "✓ $*"; }
fail() { echo "✗ $*" >&2; exit 1; }

age-keygen -o "$T/key" 2>/dev/null
age-keygen -o "$T/wrong.key" 2>/dev/null
export BASHARNIA_BACKUP_CONFIG=$T/none.env DB_MODE=local BACKUP_DIR=$T/backups APP_DIR=$T/app
export AGE_RECIPIENT; AGE_RECIPIENT=$(age-keygen -y "$T/key")
export RCLONE_CONFIG_OFFSITE_TYPE=local RCLONE_REMOTE=offsite:$T/offsite KEEP_DAILY=2 KEEP_WEEKLY=1
export WEEKLY_DAY; WEEKLY_DAY=$(date -u +%u)  # today counts as the weekly day

infra/backup/backup.sh > "$T/log1" 2>&1 || { cat "$T/log1"; fail "backup"; }
f=$(find "$T/backups/daily" -name 'basharnia-*.tar.age' | head -1)
[[ -s $f ]] && pass "backup created ($(du -h "$f" | cut -f1))" || fail "no archive"
head -c 21 "$f" | grep -q "age-encryption.org" && pass "archive is age-encrypted" || fail "not encrypted"
if strings "$f" | grep -q "CREATE TABLE"; then fail "plaintext SQL visible"; else pass "no plaintext inside the archive"; fi
[[ -f $T/offsite/daily/$(basename "$f") && -f $T/offsite/weekly/$(basename "$f") ]] && pass "off-site daily + weekly copies" || fail "off-site copy"
grep -q "off-site copy verified" "$T/log1" && pass "off-site copy checksum verified" || fail "offsite verify"

# Retention: three more runs -> only KEEP_DAILY=2 daily, KEEP_WEEKLY=1 weekly remain (local + remote)
for _ in 1 2 3; do sleep 1; infra/backup/backup.sh > /dev/null 2>&1; done
d=$(find "$T/backups/daily" -name '*.tar.age' | wc -l); w=$(find "$T/backups/weekly" -name '*.tar.age' | wc -l)
rd=$(find "$T/offsite/daily" -name '*.tar.age' | wc -l); rw=$(find "$T/offsite/weekly" -name '*.tar.age' | wc -l)
[[ $d == 2 && $w == 1 && $rd == 2 && $rw == 1 ]] && pass "retention: daily=$d weekly=$w (remote $rd/$rw)" || fail "retention $d/$w/$rd/$rw"

latest=$(find "$T/backups/daily" -name '*.tar.age' | sort | tail -1)
if infra/backup/restore.sh --key "$T/wrong.key" --yes --no-stop --target-db x_wrong --target-dir "$T/w" "$latest" >/dev/null 2>&1; then
  fail "restore with the wrong key succeeded"
else pass "wrong key is rejected"; fi

cp "$latest" "$T/damaged.tar.age"
printf 'XXXX' | dd of="$T/damaged.tar.age" bs=1 seek=4000 conv=notrunc 2>/dev/null
if infra/backup/restore.sh --key "$T/key" --yes --no-stop --target-db x_damaged --target-dir "$T/d" "$T/damaged.tar.age" >/dev/null 2>&1; then
  fail "damaged archive restored"
else pass "damaged archive is rejected"; fi

infra/backup/restore-drill.sh --key "$T/key" "$latest" > "$T/drill" 2>&1 || { cat "$T/drill"; fail "drill"; }
grep -o "restore drill PASSED.*" "$T/drill" | sed 's/^/✓ /'

# Restore straight from the off-site copy (as after losing the whole server)
remote=$(find "$T/offsite/daily" -name '*.tar.age' | sort | tail -1)
infra/backup/restore.sh --key "$T/key" --yes --no-stop --target-db "${PGDATABASE}_from_offsite" \
  --target-dir "$T/fromoffsite" "offsite:$remote" > "$T/r2" 2>&1 || { cat "$T/r2"; fail "restore from off-site"; }
n=$(psql -d "${PGDATABASE}_from_offsite" -Atqc "SELECT count(*) FROM students")
live=$(psql -Atqc "SELECT count(*) FROM students")
[[ $n == "$live" ]] && pass "restore from off-site copy: students=$n" || fail "offsite restore students $n != $live"
dropdb --if-exists "${PGDATABASE}_from_offsite"
echo "ALL PASSED"
