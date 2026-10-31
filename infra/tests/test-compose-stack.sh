#!/usr/bin/env bash
# End-to-end test of the production Docker Compose stack (APP_ENV=production):
# PostgreSQL + migrations + API + nginx (self-signed TLS), then backup.sh and
# restore-drill.sh in compose mode against it. Runs as a SEPARATE compose project
# on ports 18080/18443 with its own data, so it never touches a real deployment.
#
#   sudo infra/tests/test-compose-stack.sh
#   BASHARNIA_TEST_IMAGE=basharnia-backend:test sudo infra/tests/test-compose-stack.sh  # use a prebuilt image
#
# Needs: docker (compose v2), openssl, curl, ffmpeg, age.
set -euo pipefail
cd "$(dirname "$0")/../.."
REPO=$(pwd)

DOMAIN=api.test.local
PROJECT=basharnia-stacktest
WORK=$(mktemp -d /tmp/basharnia-stack-XXXXXX)
chmod 755 "$WORK"
pass() { echo "✓ $*"; }
fail() { echo "✗ $*" >&2; exit 1; }

DC=(docker compose -p "$PROJECT" --project-directory "$REPO" --env-file "$WORK/.env"
    -f "$REPO/docker-compose.yml" -f "$WORK/override.yml")
cleanup() {
  "${DC[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
  # files in storage belong to uid 10001; we are root, so plain deletion works
  find "$WORK" -depth -delete 2>/dev/null || true
}
trap cleanup EXIT

rand() { openssl rand -hex 24; }
PGPASS=$(rand)
mkdir -p "$WORK/storage" "$WORK/le/live/$DOMAIN" "$WORK/webroot"
chown 10001:10001 "$WORK/storage" && chmod 750 "$WORK/storage"
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj "/CN=$DOMAIN" \
  -keyout "$WORK/le/live/$DOMAIN/privkey.pem" -out "$WORK/le/live/$DOMAIN/fullchain.pem" 2>/dev/null
chmod -R a+rX "$WORK/le"

cat > "$WORK/.env" <<ENV
APP_ENV=production
APP_SECRET_KEY=$(rand)
POSTGRES_DB=basharnia
POSTGRES_USER=basharnia
POSTGRES_PASSWORD=$PGPASS
DATABASE_URL=postgresql+psycopg://basharnia:$PGPASS@db:5432/basharnia
FRONTEND_URL=https://coach.test.local
API_BASE_URL=https://$DOMAIN
API_DOMAIN=$DOMAIN
STORAGE_HOST_PATH=$WORK/storage
STORAGE_ROOT=/data/basharnia
MAX_UPLOAD_MB=20
ENV
chmod 600 "$WORK/.env"

IMAGE_OVERRIDE=""
if [[ -n ${BASHARNIA_TEST_IMAGE:-} ]]; then
  IMAGE_OVERRIDE="    image: $BASHARNIA_TEST_IMAGE
    build: !reset null"
fi
cat > "$WORK/override.yml" <<YML
services:
  migrate:
    env_file: !override [$WORK/.env]
$IMAGE_OVERRIDE
  api:
    env_file: !override [$WORK/.env]
$IMAGE_OVERRIDE
  worker:
    profiles: [whisper]   # needs the Whisper model; not part of this test
    env_file: !override [$WORK/.env]
$IMAGE_OVERRIDE
  nginx:
    ports: !override
      - "127.0.0.1:18080:80"
      - "127.0.0.1:18443:443"
    volumes: !override
      - $REPO/infra/nginx/default.conf.template:/etc/nginx/templates/default.conf.template:ro
      - $WORK/le:/etc/letsencrypt:ro
      - $WORK/webroot:/var/www/certbot:ro
YML

"${DC[@]}" config -q && pass "compose config valid (production + test override)"
"${DC[@]}" up -d --wait db migrate api nginx >"$WORK/up.log" 2>&1 || { cat "$WORK/up.log"; "${DC[@]}" logs --tail 50; fail "stack did not start"; }
pass "stack up: db healthy, migrations applied, api healthy, nginx running"

C=(curl -sk --noproxy '*' --resolve "$DOMAIN:18443:127.0.0.1")
API="https://$DOMAIN:18443/api"
[[ $("${C[@]}" "$API/health/ready") == '{"status":"ok","database":"ok"}' ]] && pass "HTTPS via nginx -> API -> PostgreSQL" || fail "ready"
[[ $("${C[@]}" -o /dev/null -w '%{http_code}' "$API/docs") == 404 ]] && pass "API docs hidden in production" || fail "docs exposed"
mapped=$(docker ps --filter "label=com.docker.compose.project=$PROJECT" --format '{{.Names}} {{.Ports}}')
if grep -qE -- "->(5432|8000)/tcp" <<<"$mapped"; then echo "$mapped"; fail "internal port published"; fi
grep -qE -- "127.0.0.1:18443->443/tcp" <<<"$mapped" && pass "only nginx publishes ports; PostgreSQL/API stay internal" || { echo "$mapped"; fail "nginx port"; }

"${DC[@]}" run --rm -e ADMIN_USERNAME=coach -e INITIAL_ADMIN_PASSWORD=stack-test-password api \
  python -m app.cli create-admin >/dev/null 2>&1 && pass "admin created with the CLI inside the container" || fail "create-admin"

H=(-H "Origin: https://coach.test.local" -H "X-Requested-With: fetch" -H "Content-Type: application/json")
login=$("${C[@]}" -D - -o /dev/null -c "$WORK/cookies" "${H[@]}" -d '{"username":"coach","password":"stack-test-password"}' "$API/auth/login")
grep -qi "set-cookie: __Host-basharnia_session=.*HttpOnly.*Secure\|set-cookie: __Host-basharnia_session=.*Secure.*HttpOnly" <<<"$login" \
  && pass "login: __Host- cookie, Secure + HttpOnly" || { echo "$login"; fail "cookie flags"; }
grep -qi "access-control-allow-origin: https://coach.test.local" <<<"$login" && pass "CORS allows the panel origin" || fail "cors"
evil=$("${C[@]}" -D - -o /dev/null -X OPTIONS -H "Origin: https://evil.example" -H "Access-Control-Request-Method: POST" "$API/auth/login")
grep -qi "access-control-allow-origin" <<<"$evil" && fail "CORS allows a foreign origin" || pass "CORS refuses foreign origins"

sid=$("${C[@]}" -b "$WORK/cookies" "${H[@]}" -d '{"first_name":"آزمون","last_name":"استک"}' "$API/students" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
ffmpeg -loglevel error -f lavfi -i color=c=blue:s=64x64 -frames:v 1 "$WORK/p.jpg"
code=$("${C[@]}" -o /dev/null -w '%{http_code}' -b "$WORK/cookies" -H "Origin: https://coach.test.local" -H "X-Requested-With: fetch" \
  -X PUT -F "file=@$WORK/p.jpg;type=image/jpeg" -F consent=true "$API/students/$sid/profile-photo")
[[ $code == 200 ]] || fail "photo upload $code"
owner=$(find "$WORK/storage" -name '*.jpg' -printf '%u\n' | head -1)
[[ $owner == 10001 || $owner == app ]] && pass "uploads land in the host storage dir, owned by the non-root app user" || fail "owner $owner"

"${DC[@]}" restart api db >/dev/null 2>&1
"${DC[@]}" up -d --wait db api >/dev/null 2>&1
"${DC[@]}" down >/dev/null 2>&1   # containers removed, named volumes kept
"${DC[@]}" up -d --wait db migrate api nginx >/dev/null 2>&1
n=$("${C[@]}" -b "$WORK/cookies" "$API/students" | python3 -c 'import json,sys; print(json.load(sys.stdin)["total"])')
[[ $n == 1 ]] && pass "data and login session survive restart and container re-creation" || fail "after restart: $n"

# Backup + restore drill in compose mode against this stack
age-keygen -o "$WORK/age.key" 2>/dev/null
export BASHARNIA_BACKUP_CONFIG=$WORK/none DB_MODE=compose APP_DIR=$REPO BACKUP_DIR=$WORK/backups STORAGE_PATH=$WORK/storage
export COMPOSE_PROJECT_NAME=$PROJECT COMPOSE_FILE="$REPO/docker-compose.yml:$WORK/override.yml" COMPOSE_ENV_FILES=$WORK/.env
export PGUSER=basharnia PGDATABASE=basharnia RCLONE_REMOTE="" AGE_RECIPIENT
AGE_RECIPIENT=$(age-keygen -y "$WORK/age.key")
mkdir -p "$BACKUP_DIR"
infra/backup/backup.sh >"$WORK/backup.log" 2>&1 || { cat "$WORK/backup.log"; fail "backup.sh (compose mode)"; }
pass "backup.sh in compose mode: $(grep -o 'created .*' "$WORK/backup.log")"
infra/backup/restore-drill.sh --key "$WORK/age.key" >"$WORK/drill.log" 2>&1 || { cat "$WORK/drill.log"; fail "restore drill"; }
echo "✓ $(grep -o 'restore drill PASSED.*' "$WORK/drill.log")"

total() {  # number of students visible through the API (prints the response on error)
  local body code
  body=$("${C[@]}" -w '\n%{http_code}' -b "$WORK/cookies" "$API/students")
  code=${body##*$'\n'}; body=${body%$'\n'*}
  [[ $code == 200 ]] || { echo "GET /students -> $code: $body" >&2; "${DC[@]}" ps >&2; "${DC[@]}" logs --tail 20 api >&2; return 1; }
  python3 -c 'import json,sys; print(json.load(sys.stdin)["total"])' <<<"$body"
}

# Real restore: data changed after the backup must be rolled back to the backup
"${C[@]}" -b "$WORK/cookies" "${H[@]}" -d '{"first_name":"بعد","last_name":"ازبکاپ"}' "$API/students" >/dev/null
[[ $(total) == 2 ]] || fail "setup"
infra/backup/restore.sh --key "$WORK/age.key" --latest --yes >"$WORK/restore.log" 2>&1 || { cat "$WORK/restore.log"; fail "restore.sh"; }
"${DC[@]}" up -d --wait api nginx >/dev/null 2>&1
n=$(total) || fail "API after restore"
[[ $n == 1 ]] && pass "full restore (services stopped, DB re-created, files restored, restarted): back to backup state" || fail "after restore: $n"
ls -d "$WORK"/storage.before-restore-* >/dev/null 2>&1 && pass "previous files kept aside, not deleted" || fail "no aside copy"
echo "ALL PASSED"
