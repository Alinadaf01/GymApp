#!/usr/bin/env bash
# First Let's Encrypt certificate for the site domain + automatic renewal (run as root).
#
#   DOMAIN=api.example.com LE_EMAIL=you@example.com bash infra/scripts/init-ssl.sh
#
# 1) issues the first certificate with certbot "standalone" (nginx must not be
#    running yet, port 80 must be free and the domain's DNS must point here);
# 2) switches renewal to the webroot that nginx serves (/var/www/certbot), so
#    renewals happen while nginx keeps running;
# 3) reloads nginx after every renewal. Ubuntu's certbot package ships a systemd
#    timer that runs renewals twice a day.
set -euo pipefail

DOMAIN=${DOMAIN:?set DOMAIN (the site domain, e.g. coach.example.com)}
LE_EMAIL=${LE_EMAIL:?set LE_EMAIL (expiry notices from Let\'s Encrypt)}
APP_DIR=${APP_DIR:-/opt/basharnia}
WEBROOT=/var/www/certbot

[[ $EUID -eq 0 ]] || { echo "run as root" >&2; exit 1; }

if [[ ! -s /etc/letsencrypt/live/$DOMAIN/fullchain.pem ]]; then
  if ss -ltn 'sport = :80' | grep -q LISTEN; then
    echo "port 80 is in use; stop nginx first: docker compose -f $APP_DIR/docker-compose.yml stop nginx" >&2
    exit 1
  fi
  certbot certonly --standalone --non-interactive --agree-tos -m "$LE_EMAIL" -d "$DOMAIN"
fi

install -d -m 755 "$WEBROOT"
# Renew through nginx's webroot from now on (no downtime). certbot tests the
# webroot right away, so this needs nginx running; run this script again then.
if ss -ltn 'sport = :80' | grep -q LISTEN; then
  certbot reconfigure --cert-name "$DOMAIN" --webroot -w "$WEBROOT" --non-interactive
else
  echo "nginx is not running yet: renewal stays 'standalone' until this script runs again with nginx up."
fi

install -d /etc/letsencrypt/renewal-hooks/deploy
cat > /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh <<HOOK
#!/bin/sh
docker compose -f $APP_DIR/docker-compose.yml exec -T nginx nginx -s reload
HOOK
chmod 755 /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh

systemctl enable --now certbot.timer
echo "Certificate ready. Test renewal any time with: certbot renew --dry-run"
