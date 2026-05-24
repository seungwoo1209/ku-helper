#!/usr/bin/env bash
set -euo pipefail

# AL2023 + docker + docker compose v2 + amazon-cloudwatch-agent + awscli v2(기본)
# ssm-agent 는 AL2023 기본 포함.

dnf -y update
dnf -y install docker docker-compose-plugin amazon-cloudwatch-agent jq

systemctl enable docker
systemctl start docker
usermod -aG docker ec2-user

install -d -m 0755 /opt/ku-helper /etc/ku-helper
install -m 0644 /tmp/docker-compose.yml /opt/ku-helper/docker-compose.yml

install -d -m 0755 /opt/aws/amazon-cloudwatch-agent/etc
install -m 0644 /tmp/cloudwatch-agent.json /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json

systemctl enable amazon-cloudwatch-agent
# cwagent 는 EC2 부팅 시 user-data 또는 별도 systemd unit 으로 start (config 가 SSM Parameter 일 때는 fetch-config 사용)
# 여기서는 로컬 config 사용이라 enable 만 해두고, ephemeral EC2 user-data 가 start 호출.

# docker compose 가 ghcr 에서 이미지 pull 할 수 있도록 systemd 서비스 등록.
# 실제 .env 와 GHCR 로그인은 ephemeral EC2 user-data 가 처리.
cat <<'UNIT' >/etc/systemd/system/ku-helper-app.service
[Unit]
Description=ku-helper backend + bot docker compose stack
After=docker.service network-online.target
Requires=docker.service
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/ku-helper
EnvironmentFile=-/etc/ku-helper/app.env
ExecStartPre=/usr/bin/docker compose pull
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
# enable 만. start 는 ephemeral EC2 user-data 가 ghcr 로그인 + .env 작성 후 호출.
systemctl enable ku-helper-app.service

dnf clean all
rm -rf /var/cache/dnf /tmp/docker-compose.yml /tmp/cloudwatch-agent.json
