#!/usr/bin/env bash
# One-time hardening + prerequisites for a fresh Ubuntu 24.04 VPS (run as root).
#
#   ADMIN_USER=coachadmin bash infra/scripts/setup-vps.sh            # apply
#   DRY_RUN=1 ADMIN_USER=coachadmin bash infra/scripts/setup-vps.sh  # print only
#
# Idempotent: safe to run again. It will NOT disable SSH passwords/root login
# unless ADMIN_USER already has an SSH key (prevents locking yourself out).
set -euo pipefail

ADMIN_USER=${ADMIN_USER:?set ADMIN_USER (a non-root sudo user to log in with)}
SSH_PORT=${SSH_PORT:-22}
SWAP_GB=${SWAP_GB:-2}
APP_UID=10001  # the API/worker containers run as this uid
DRY_RUN=${DRY_RUN:-0}

log() { printf '\n== %s\n' "$*"; }
run() { if [[ $DRY_RUN == 1 ]]; then printf '+ %s\n' "$*"; else "$@"; fi; }
write() {  # write <file> <mode>  (content from stdin)
  local file=$1 mode=$2 content
  content=$(cat)
  if [[ $DRY_RUN == 1 ]]; then printf '+ write %s (%s)\n%s\n' "$file" "$mode" "$content"; return; fi
  install -d "$(dirname "$file")"
  printf '%s\n' "$content" > "$file"
  chmod "$mode" "$file"
}

if [[ $DRY_RUN != 1 && $EUID -ne 0 ]]; then echo "run as root" >&2; exit 1; fi
if ! grep -q 'VERSION_ID="24.04"' /etc/os-release; then echo "warning: tested on Ubuntu 24.04 only" >&2; fi

log "System updates and packages"
run apt-get update -q
run env DEBIAN_FRONTEND=noninteractive apt-get -y -q upgrade
# docker.io + compose plugin from the Ubuntu archive (no third-party repository needed)
run env DEBIAN_FRONTEND=noninteractive apt-get -y -q install \
  ufw fail2ban unattended-upgrades docker.io docker-compose-v2 certbot age rclone git curl ca-certificates

log "Automatic security updates"
write /etc/apt/apt.conf.d/20auto-upgrades 0644 <<'CONF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
CONF

log "Admin user: $ADMIN_USER"
if ! id "$ADMIN_USER" >/dev/null 2>&1; then
  run adduser --disabled-password --gecos "" "$ADMIN_USER"
fi
run usermod -aG sudo,docker "$ADMIN_USER"
ADMIN_HOME=$(getent passwd "$ADMIN_USER" | cut -d: -f6 || echo "/home/$ADMIN_USER")
ADMIN_KEYS="$ADMIN_HOME/.ssh/authorized_keys"
if [[ ! -s $ADMIN_KEYS && -s /root/.ssh/authorized_keys ]]; then
  # Reuse the key the VPS provider installed for root
  run install -d -m 700 -o "$ADMIN_USER" -g "$ADMIN_USER" "$ADMIN_HOME/.ssh"
  run install -m 600 -o "$ADMIN_USER" -g "$ADMIN_USER" /root/.ssh/authorized_keys "$ADMIN_KEYS"
fi

log "SSH hardening"
if [[ -s $ADMIN_KEYS ]]; then
  write /etc/ssh/sshd_config.d/99-basharnia.conf 0644 <<CONF
Port $SSH_PORT
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
MaxAuthTries 4
LoginGraceTime 30
AllowUsers $ADMIN_USER
CONF
  run sshd -t
  # Ubuntu 24.04 starts sshd through ssh.socket (socket activation):
  # a new Port takes effect via the socket generator after daemon-reload.
  if [[ $SSH_PORT != 22 ]]; then
    run systemctl daemon-reload
    run systemctl restart ssh.socket
    echo "!! SSH moved to port $SSH_PORT. Keep this session open and test a new login first."
  fi
  run systemctl try-reload-or-restart ssh
else
  echo "!! $ADMIN_USER has no SSH key in $ADMIN_KEYS — SSH hardening SKIPPED to avoid a lockout."
  echo "!! Add your public key there, check you can log in as $ADMIN_USER, then run this script again."
fi

log "Firewall (UFW): only SSH, HTTP, HTTPS"
run ufw default deny incoming
run ufw default allow outgoing
run ufw limit "$SSH_PORT/tcp"
run ufw allow 80/tcp
run ufw allow 443/tcp
run ufw --force enable
# Note: Docker publishes ports by editing iptables directly (bypassing UFW).
# That is why only nginx publishes ports; PostgreSQL (5432) and the API (8000)
# are never published and stay on the internal Docker network.

log "Fail2ban (SSH brute force)"
write /etc/fail2ban/jail.d/basharnia.local 0644 <<CONF
[sshd]
enabled  = true
port     = $SSH_PORT
backend  = systemd
maxretry = 5
findtime = 10m
bantime  = 1h
CONF
run systemctl enable --now fail2ban
run systemctl restart fail2ban

log "Swap (${SWAP_GB}G, helps Whisper on small VPS)"
if ! swapon --show | grep -q .; then
  run fallocate -l "${SWAP_GB}G" /swapfile
  run chmod 600 /swapfile
  run mkswap /swapfile
  run swapon /swapfile
  grep -q "^/swapfile" /etc/fstab || run sh -c 'echo "/swapfile none swap sw 0 0" >> /etc/fstab'
fi

log "Directories"
run install -d -m 750 -o "$APP_UID" -g "$APP_UID" /data/basharnia     # private files (photos, PDFs)
run install -d -m 755 /var/www/certbot                                # ACME webroot (public by design)
run install -d -m 700 /var/backups/basharnia                          # encrypted backups
run install -d -m 750 -o "$ADMIN_USER" -g "$ADMIN_USER" /opt/basharnia # application checkout
run install -d -m 700 /etc/basharnia                                  # backup configuration

run systemctl enable --now docker
log "Done. Next: docs/DEPLOYMENT.md, step 3 (clone the repository into /opt/basharnia)."
