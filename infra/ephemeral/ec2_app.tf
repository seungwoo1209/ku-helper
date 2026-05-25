locals {
  # 환경 파일 작성과 GitHub Container Registry 로그인은 AMI 안의 refresh-env.sh 가 담당한다.
  # 첫 부팅 시점에는 시크릿 파라미터가 아직 placeholder 일 수 있어 앱 기동이 실패할 수 있으나,
  # 이후 워크플로의 put-secrets 와 rollout(refresh-env.sh 재호출)이 실제 값으로 복구한다.
  app_user_data = <<-EOT
    #!/bin/bash
    set -euo pipefail
    exec > >(tee -a /var/log/ku-helper-userdata.log) 2>&1

    # 1) SSM 에서 환경 파일 작성 + GitHub Container Registry 로그인
    /opt/ku-helper/refresh-env.sh || true

    # 2) CloudWatch agent 시작
    systemctl start amazon-cloudwatch-agent || true

    # 3) compose stack 부팅
    systemctl start ku-helper-app.service || true
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

  # 시크릿 파라미터(app_secrets, ghcr_pat)는 persistent 모듈에 있고 ephemeral 보다 먼저
  # apply 되므로 cross-state depends_on 은 필요 없다.
  depends_on = [
    aws_db_instance.main,
    aws_elasticache_serverless_cache.main,
    aws_ssm_parameter.app_config,
  ]
}
