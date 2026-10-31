#!/usr/bin/env bash
# Shared settings/helpers for backup.sh, restore.sh and restore-drill.sh.
# Configuration: /etc/basharnia/backup.env (see backup.env.example).
set -euo pipefail

CONFIG=${BASHARNIA_BACKUP_CONFIG:-/etc/basharnia/backup.env}
if [[ -f $CONFIG ]]; then
  # shellcheck disable=SC1090
  source "$CONFIG"
fi

APP_DIR=${APP_DIR:-/opt/basharnia}
BACKUP_DIR=${BACKUP_DIR:-/var/backups/basharnia}
STORAGE_PATH=${STORAGE_PATH:-/data/basharnia}
KEEP_DAILY=${KEEP_DAILY:-7}
KEEP_WEEKLY=${KEEP_WEEKLY:-4}
WEEKLY_DAY=${WEEKLY_DAY:-5}      # ISO weekday for the weekly copy (5 = Friday)
RCLONE_REMOTE=${RCLONE_REMOTE:-} # e.g. "offsite:basharnia-backups" (empty = no off-site copy)
DB_MODE=${DB_MODE:-compose}      # compose (production) | local (tests: uses PG* env vars)

# Database credentials: from the app's .env in compose mode
if [[ $DB_MODE == compose && -f $APP_DIR/.env ]]; then
  PGUSER=${PGUSER:-$(grep -E '^POSTGRES_USER=' "$APP_DIR/.env" | cut -d= -f2- || true)}
  PGDATABASE=${PGDATABASE:-$(grep -E '^POSTGRES_DB=' "$APP_DIR/.env" | cut -d= -f2- || true)}
fi
export PGUSER=${PGUSER:-basharnia} PGDATABASE=${PGDATABASE:-basharnia}

log() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*"; }
die() { log "ERROR: $*" >&2; exit 1; }

# Delete a temporary directory tree. Refuses anything that is not one of our
# own scratch directories, so an empty/wrong variable can never wipe real data.
remove_tree() {
  local d=${1:-}
  case $d in
    /tmp/basharnia-*|"$BACKUP_DIR"/.work-*) ;;
    *) log "refusing to delete unexpected path: '$d'"; return 0 ;;
  esac
  [[ -d $d ]] && find "$d" -depth -delete
  return 0
}

# Run a PostgreSQL client tool next to the database (stdin/stdout pass through).
pg() {
  if [[ $DB_MODE == compose ]]; then
    compose exec -T -e PGUSER -e PGDATABASE db "$@"
  else
    "$@"
  fi
}

# Uses $APP_DIR/docker-compose.yml, or the files in the standard COMPOSE_FILE variable.
compose() { docker compose --project-directory "$APP_DIR" "$@"; }

# Notify the coach on Telegram (best effort; uses the bot already configured).
notify() {
  local env=$APP_DIR/.env token chat
  [[ -f $env ]] || return 0
  token=$(grep -E '^TELEGRAM_BOT_TOKEN=' "$env" | cut -d= -f2- || true)
  chat=$(grep -E '^TELEGRAM_ALLOWED_USER_ID=' "$env" | cut -d= -f2- || true)
  [[ -n $token && -n $chat ]] || return 0
  curl -fsS -m 15 "https://api.telegram.org/bot${token}/sendMessage" \
    --data-urlencode "chat_id=${chat}" --data-urlencode "text=$1" >/dev/null 2>&1 || true
}
