terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
    }
    github = {
      source  = "integrations/github"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = var.region
}

provider "github" {
  owner = var.github_owner
  token = var.github_token
}
