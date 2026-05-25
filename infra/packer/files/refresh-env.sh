#!/usr/bin/env bash
# SSM Parameter Store 에서 /ku-helper/app/* 를 fetch 하여 /etc/ku-helper/app.env 로 기록하고,
# GitHub Container Registry 에 docker login 한다. EC2 첫 부팅(user-data)과 일상 배포 rollout
# 양쪽이 호출하는 멱등 스크립트다. 시크릿 값은 terraform state 가 아니라 SSM 에만 존재한다.
set -euo pipefail

PROJECT="ku-helper"

# IMDSv2 로 현재 리전 조회.
TOKEN=$(curl -sS -X PUT "http://169.254.169.254/latest/api/token" \
  -H "X-aws-ec2-metadata-token-ttl-seconds: 300")
REGION=$(curl -sS -H "X-aws-ec2-metadata-token: $TOKEN" \
  http://169.254.169.254/latest/dynamic/instance-identity/document | jq -r .region)

install -d -m 0700 /etc/ku-helper

# /ku-helper/app/* 전부 fetch → /etc/ku-helper/app.env (KEY="VALUE" 형식)
aws ssm get-parameters-by-path \
  --region "$REGION" \
  --path "/$PROJECT/app/" \
  --with-decryption \
  --recursive \
  --query "Parameters[*].[Name,Value]" \
  --output text | \
awk -F'\t' -v project="$PROJECT" '{
  n=$1; sub("/"project"/app/", "", n);
  v=$2;
  gsub("\"", "\\\"", v);
  printf "%s=\"%s\"\n", n, v;
}' > /etc/ku-helper/app.env
chmod 0600 /etc/ku-helper/app.env

# GitHub Container Registry 로그인. owner 는 비시크릿이라 app.env 의 GHCR_OWNER 를 사용한다.
# PAT 는 app.env 에 넣지 않고 별도 네임스페이스에서 직접 읽어 로그인에만 사용한다.
GHCR_OWNER=$(awk -F'=' '/^GHCR_OWNER=/{gsub(/"/,"",$2); print $2}' /etc/ku-helper/app.env)
GHCR_PAT=$(aws ssm get-parameter \
  --region "$REGION" \
  --name "/$PROJECT/ghcr/pat" \
  --with-decryption \
  --query Parameter.Value \
  --output text)
echo "$GHCR_PAT" | docker login ghcr.io -u "$GHCR_OWNER" --password-stdin
unset GHCR_PAT
