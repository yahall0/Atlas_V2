#!/bin/bash
# EC2 user-data bootstrap for Atlas_V2 demo box.
# Runs once at first boot (Ubuntu 22.04). Installs docker, nginx, certbot, and prepares /opt/atlas.
# Logs: /var/log/cloud-init-output.log

set -eux

export DEBIAN_FRONTEND=noninteractive

# Base packages
apt-get update
apt-get upgrade -y
apt-get install -y \
  ca-certificates curl gnupg lsb-release \
  git rsync jq ufw \
  nginx certbot python3-certbot-nginx

# Docker (official repo, not distro)
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Ubuntu user → docker group
usermod -aG docker ubuntu

# Deployment target
mkdir -p /opt/atlas
chown ubuntu:ubuntu /opt/atlas

# Firewall (defence in depth on top of SG)
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable

# Enable services
systemctl enable --now docker
systemctl enable --now nginx

# Disable default nginx site; atlas site is installed by deploy.sh
rm -f /etc/nginx/sites-enabled/default

touch /var/log/atlas-bootstrap.done
echo "Atlas bootstrap complete at $(date -u)" >> /var/log/atlas-bootstrap.done
