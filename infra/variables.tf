variable "region" {
  description = "AWS region"
  type        = string
  default     = "ap-northeast-2"
}

variable "project" {
  description = "Project name prefix for tagging"
  type        = string
  default     = "ku-helper"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidr" {
  description = "CIDR block for the public subnet"
  type        = string
  default     = "10.0.1.0/24"
}

variable "instance_type" {
  description = "EC2 instance type (free tier)"
  type        = string
  default     = "t3.micro"
}

variable "ssh_ingress_cidr" {
  description = "CIDR allowed to SSH into the instance"
  type        = string
  default     = "0.0.0.0/0"
}

variable "github_owner" {
  description = "GitHub owner (user or organization) that owns the deployment repository"
  type        = string
  default     = "seungwoo1209"
}

variable "github_repository" {
  description = "GitHub repository name where Actions secrets should be created"
  type        = string
  default     = "ku-helper"
}

variable "github_token" {
  description = "GitHub Personal Access Token with `repo` scope, used to publish Actions secrets"
  type        = string
  sensitive   = true
}

variable "ec2_ssh_private_key_secret_name" {
  description = "Name of the GitHub Actions secret that stores the EC2 SSH private key (PEM)"
  type        = string
  default     = "EC2_SSH_PRIVATE_KEY"
}
