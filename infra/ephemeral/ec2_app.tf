locals {
  app_env_keys = concat(keys(local.app_config), keys(local.app_secrets))

  app_user_data = <<-EOT
    #!/bin/bash
    set -euo pipefail
    exec > >(tee -a /var/log/ku-helper-userdata.log) 2>&1

    REGION="${var.aws_region}"
    PROJECT="${var.project}"

    install -d -m 0700 /etc/ku-helper

    # 1) SSM Parameter Store 에서 /ku-helper/app/* 전부 fetch → /etc/ku-helper/app.env
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

    # 2) GHCR 로그인
    GHCR_PAT=$(aws ssm get-parameter --region "$REGION" --name "/$PROJECT/ghcr/pat" --with-decryption --query Parameter.Value --output text)
    echo "$GHCR_PAT" | docker login ghcr.io -u ${var.github_owner} --password-stdin
    unset GHCR_PAT

    # 3) CloudWatch agent 시작
    systemctl start amazon-cloudwatch-agent || true

    # 4) compose stack 부팅
    systemctl start ku-helper-app.service
  EOT
}

resource "aws_instance" "app" {
  ami                    = local.persistent.app_ami_id
  instance_type          = var.app_instance_type
  subnet_id              = aws_subnet.public[0].id
  vpc_security_group_ids = [aws_security_group.app.id]
  key_name               = aws_key_pair.ec2.key_name
  iam_instance_profile   = local.persistent.ec2_instance_profile_name

  user_data                   = local.app_user_data
  user_data_replace_on_change = true

  root_block_device {
    volume_size           = 20
    volume_type           = "gp3"
    encrypted             = true
    delete_on_termination = true
  }

  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
    http_endpoint               = "enabled"
  }

  tags = {
    Name = "${var.project}-app"
    role = "app"
  }

  depends_on = [
    aws_db_instance.main,
    aws_elasticache_serverless_cache.main,
    aws_ssm_parameter.app_config,
    aws_ssm_parameter.app_secrets,
    aws_ssm_parameter.ghcr_pat,
  ]
}
