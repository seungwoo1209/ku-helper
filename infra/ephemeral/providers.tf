terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source                = "hashicorp/aws"
      version               = "~> 5.0"
      configuration_aliases = [aws.route53]
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      project   = "ku-helper"
      module    = "ephemeral"
      managedBy = "terraform"
    }
  }
}

provider "aws" {
  alias  = "route53"
  region = var.aws_region

  assume_role {
    role_arn     = "arn:aws:iam::${data.terraform_remote_state.persistent.outputs.route53_account_id}:role/Route53-kuhelper-CrossAccount-Role"
    session_name = "ku-helper-ephemeral"
  }
}

