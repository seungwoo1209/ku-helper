#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v terraform >/dev/null 2>&1; then
  echo "Error: terraform is not installed or not in PATH." >&2
  exit 1
fi

if [ ! -f terraform.tfstate ] && [ -z "${TF_DATA_DIR:-}" ]; then
  echo "Error: terraform state not found. Run 'terraform apply' first." >&2
  exit 1
fi

KEY_PATH="$(terraform output -raw private_key_path)"
PUBLIC_IP="$(terraform output -raw instance_public_ip)"
USER="${EC2_USER:-ec2-user}"

if [ ! -f "$KEY_PATH" ]; then
  echo "Error: private key not found at $KEY_PATH" >&2
  exit 1
fi

chmod 400 "$KEY_PATH"

echo "Connecting to ${USER}@${PUBLIC_IP} ..."
exec ssh \
  -i "$KEY_PATH" \
  -o StrictHostKeyChecking=accept-new \
  -o UserKnownHostsFile="$HOME/.ssh/known_hosts" \
  "${USER}@${PUBLIC_IP}" "$@"
