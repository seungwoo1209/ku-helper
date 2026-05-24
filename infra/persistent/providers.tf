terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source                = "hashicorp/aws"
      version               = "~> 5.0"
      configuration_aliases = [aws.route53]
    }
  }
}

# 배포 계정(DEPLOYMENT_AWS_ACCOUNT_ID) — ACM 인증서, IAM Role 등이 여기 생성된다.
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      project   = "ku-helper"
      module    = "persistent"
      managedBy = "terraform"
    }
  }
}

# Route53 호스팅 존이 있는 별도 계정(ROUTE53_PROVIDER_AWS_ID).
# 사전 구성된 Route53-kuhelper-CrossAccount-Role 을 assume 해 DNS validation 레코드를 생성한다.
provider "aws" {
  alias  = "route53"
  region = var.aws_region

  assume_role {
    role_arn     = "arn:aws:iam::${var.route53_account_id}:role/Route53-kuhelper-CrossAccount-Role"
    session_name = "ku-helper-persistent"
  }

  default_tags {
    tags = {
      project   = "ku-helper"
      module    = "persistent"
      managedBy = "terraform"
    }
  }
}
