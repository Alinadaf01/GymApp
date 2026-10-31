#!/usr/bin/env bash
# Integration test for infra/nginx/default.conf.template (test machines only).
# Renders the template, runs nginx with a self-signed cert in front of an echo
# server standing in for the API, and checks behaviour with curl.
# Needs: nginx, openssl, python3, curl, and permission to bind 80/443 + edit /etc/hosts.
set -euo pipefail
cd "$(dirname "$0")/../.."

DOMAIN=api.test.local
WORK=$(mktemp -d)
chmod 755 "$WORK"  # nginx workers (www-data) must read the webroot
trap 'nginx -c "$WORK/nginx.conf" -s stop 2>/dev/null || true; [[ -n "${ECHO_PID:-}" ]] && kill "$ECHO_PID" 2>/dev/null || true; rm -rf "$WORK"' EXIT
pass() { echo "✓ $*"; }
fail() { echo "✗ $*" >&2; exit 1; }

for port in 80 443 8000; do
  if ss -ltn "sport = :$port" | grep -q LISTEN; then fail "port $port is already in use; stop the service using it first"; fi
done
grep -q "^127.0.0.1 api$" /etc/hosts || echo "127.0.0.1 api" >> /etc/hosts

mkdir -p "$WORK/letsencrypt/live/$DOMAIN" "$WORK/certbot/.well-known/acme-challenge" "$WORK/logs"
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj "/CN=$DOMAIN" \
  -keyout "$WORK/letsencrypt/live/$DOMAIN/privkey.pem" -out "$WORK/letsencrypt/live/$DOMAIN/fullchain.pem" 2>/dev/null
echo "acme-token" > "$WORK/certbot/.well-known/acme-challenge/t1"
chmod -R a+rX "$WORK/certbot"

# Render exactly like the nginx image does (envsubst on the defined variables only)
API_DOMAIN=$DOMAIN NGINX_MAX_BODY_MB=1 envsubst '${API_DOMAIN} ${NGINX_MAX_BODY_MB}' \
  < infra/nginx/default.conf.template \
  | sed "s#/etc/letsencrypt#$WORK/letsencrypt#g; s#/var/www/certbot#$WORK/certbot#g" > "$WORK/site.conf"
# Production runs nginx:1.27 ("http2 on;"). Older local nginx (<1.25.1) needs the legacy form.
if ! nginx -v 2>&1 | grep -qE "nginx/(1\.(2[5-9]|[3-9][0-9])|[2-9])"; then
  sed -i 's/^\s*http2 on;//; s/listen 443 ssl;/listen 443 ssl http2;/' "$WORK/site.conf"
fi
cat > "$WORK/nginx.conf" <<CONF
pid $WORK/nginx.pid;
error_log $WORK/logs/error.log;
events {}
http {
  access_log off;
  client_body_temp_path $WORK/body; proxy_temp_path $WORK/proxy;
  fastcgi_temp_path $WORK/f; uwsgi_temp_path $WORK/u; scgi_temp_path $WORK/s;
  include $WORK/site.conf;
}
CONF

out=$(nginx -t -c "$WORK/nginx.conf" 2>&1) || { echo "$out"; fail "nginx -t"; }
pass "nginx -t: configuration valid"

# Echo server standing in for the API: returns the headers it received as JSON
python3 - <<'PY' &
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _r(self):
        n = int(self.headers.get("Content-Length") or 0); self.rfile.read(n)
        b = json.dumps({k.lower(): v for k, v in self.headers.items()}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    do_GET = do_POST = _r
HTTPServer(("127.0.0.1", 8000), H).serve_forever()
PY
ECHO_PID=$!
sleep 0.5
nginx -c "$WORK/nginx.conf"
sleep 0.5

C=(curl -sk --noproxy '*' --resolve "$DOMAIN:443:127.0.0.1" --resolve "$DOMAIN:80:127.0.0.1")

code=$("${C[@]}" -o /dev/null -w '%{http_code} %{redirect_url}' "http://$DOMAIN/api/health")
[[ $code == "301 https://$DOMAIN/api/health" ]] && pass "HTTP redirects to HTTPS" || fail "redirect: $code"

got=$("${C[@]}" "http://$DOMAIN/.well-known/acme-challenge/t1"); [[ $got == "acme-token" ]] \
  && pass "ACME challenge served over HTTP" || fail "acme: $got"

body=$("${C[@]}" -S -H "X-Forwarded-For: 6.6.6.6" "https://$DOMAIN/api/health") || { cat "$WORK/logs/error.log"; fail "https request failed"; }
xff=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["x-forwarded-for"])' <<<"$body")
[[ $xff == "127.0.0.1" ]] && pass "client-sent X-Forwarded-For is overwritten (got $xff)" || fail "XFF spoofable: $xff"

headers=$("${C[@]}" -D - -o /dev/null "https://$DOMAIN/api/health")
for h in "strict-transport-security" "x-content-type-options: nosniff" "x-frame-options: DENY" "content-security-policy"; do
  grep -qi "^$h" <<<"$headers" && pass "header: $h" || fail "missing header $h"
done
grep -qiE "^server: nginx\s*$" <<<"$headers" && pass "server version hidden" || fail "server_tokens"

code=$("${C[@]}" -o /dev/null -w '%{http_code}' -X POST "https://$DOMAIN/api/telegram/webhook")
[[ $code == 403 ]] && pass "webhook refused from non-Telegram network" || fail "webhook: $code"

code=$("${C[@]}" -o /dev/null -w '%{http_code}' "https://$DOMAIN/")
[[ $code == 404 ]] && pass "non-API paths return 404" || fail "root: $code"

code=$(head -c 2000000 /dev/zero | "${C[@]}" -o /dev/null -w '%{http_code}' -X POST --data-binary @- "https://$DOMAIN/api/students/x/photos")
[[ $code == 413 ]] && pass "upload size limit enforced (413)" || fail "body limit: $code"

codes=$(for _ in $(seq 1 12); do "${C[@]}" -o /dev/null -w '%{http_code}\n' -X POST "https://$DOMAIN/api/auth/login"; done | sort | uniq -c)
grep -q " 429" <<<"$codes" && pass "login rate limit at the edge (429 after burst)" || fail "no 429: $codes"
echo "ALL PASSED"
