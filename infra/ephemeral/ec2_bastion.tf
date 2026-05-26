locals {
  bastion_user_data = <<-EOT
    #!/bin/bash
    set -euo pipefail
    exec > >(tee -a /var/log/ku-helper-userdata.log) 2>&1

    # bastion 에는 psql 클라이언트 + redis-cli 만 추가 설치. compose stack 비활성.
    systemctl disable --now ku-helper-app.service || true

    dnf -y install postgresql16 redis6 || true

    systemctl start amazon-cloudwatch-agent || true
  EOT
}

resource "aws_instance" "bastion" {
  ami                    = local.persistent.app_ami_id
  instance_type          = var.bastion_instance_type
  subnet_id              = aws_subnet.public[0].id
  vpc_security_group_ids = [aws_security_group.bastion.id]
  key_name               = aws_key_pair.ec2.key_name
  iam_instance_profile   = local.persistent.ec2_instance_profile_name

  user_data                   = local.bastion_user_data
  user_data_replace_on_change = true

  root_block_device {
    volume_size           = 10
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
    Name = "${var.project}-bastion"
    role = "bastion"
  }
}
