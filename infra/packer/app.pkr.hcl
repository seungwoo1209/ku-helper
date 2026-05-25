packer {
  required_version = ">= 1.10.0"

  required_plugins {
    amazon = {
      version = ">= 1.3.0"
      source  = "github.com/hashicorp/amazon"
    }
  }
}

variable "aws_region" {
  type        = string
  default     = "ap-northeast-2"
  description = "AMI 가 등록될 리전. ku-helper 가 배포되는 리전과 동일해야 한다."
}

variable "ami_name_prefix" {
  type        = string
  default     = "ku-helper-app"
  description = "persistent 모듈의 aws_ami data source 가 <prefix>-* 으로 lookup."
}

variable "instance_type" {
  type        = string
  default     = "t3.micro"
  description = "AMI 빌드용 임시 EC2 인스턴스 타입."
}

source "amazon-ebs" "app" {
  region        = var.aws_region
  instance_type = var.instance_type
  ssh_username  = "ec2-user"

  ami_name        = "${var.ami_name_prefix}-{{timestamp}}"
  ami_description = "ku-helper app/bastion AMI - AL2023 + docker + compose v2 + cwagent + awscli v2"

  source_ami_filter {
    filters = {
      name                = "al2023-ami-2023*-x86_64"
      virtualization-type = "hvm"
      root-device-type    = "ebs"
      architecture        = "x86_64"
    }
    most_recent = true
    owners      = ["amazon"]
  }

  tags = {
    project = "ku-helper"
    Name    = "${var.ami_name_prefix}-{{timestamp}}"
    builder = "packer"
  }

  run_tags = {
    project = "ku-helper"
    role    = "packer-builder"
  }

  snapshot_tags = {
    project = "ku-helper"
  }

  encrypt_boot = true
}

build {
  name    = "ku-helper-app"
  sources = ["source.amazon-ebs.app"]

  provisioner "file" {
    source      = "files/cloudwatch-agent.json"
    destination = "/tmp/cloudwatch-agent.json"
  }

  provisioner "file" {
    source      = "files/docker-compose.yml"
    destination = "/tmp/docker-compose.yml"
  }

  provisioner "file" {
    source      = "files/refresh-env.sh"
    destination = "/tmp/refresh-env.sh"
  }

  provisioner "shell" {
    script          = "files/install.sh"
    execute_command = "{{ .Vars }} sudo -E -S bash '{{ .Path }}'"
  }
}
