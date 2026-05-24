variable "aws_region" {
  description = "ku-helper 리전. bootstrap 과 동일."
  type        = string
  default     = "ap-northeast-2"
}

variable "project" {
  description = "리소스 이름 접두사."
  type        = string
  default     = "ku-helper"
}

variable "domain_name" {
  description = "ALB 가 노출할 API 도메인."
  type        = string
  default     = "api.ku-helper.seungwoo1209.site"
}

variable "route53_zone_name" {
  description = "Route53 호스팅 존(루트 도메인). cross-account 계정에 위치."
  type        = string
  default     = "seungwoo1209.site"
}

variable "route53_account_id" {
  description = "Route53 호스팅 존을 보유한 AWS 계정 ID. GitHub Actions Secret `ROUTE53_PROVIDER_AWS_ID` 와 같은 값을 -var 또는 *.tfvars 로 주입."
  type        = string
}

variable "db_iam_user" {
  description = "RDS IAM 인증으로 EC2 가 사용할 PostgreSQL role 이름. ephemeral 모듈에서 동일 값 사용."
  type        = string
  default     = "ku_helper_app"
}

variable "redis_iam_user" {
  description = "ElastiCache Valkey IAM 인증으로 EC2 가 사용할 user 이름."
  type        = string
  default     = "ku-helper-app"
}

variable "cache_name" {
  description = "ElastiCache serverless cache 이름. ephemeral 모듈과 동일."
  type        = string
  default     = "ku-helper-cache"
}

variable "ami_name_prefix" {
  description = "Packer 가 발행한 AMI 의 이름 prefix. data source lookup 에 사용."
  type        = string
  default     = "ku-helper-app"
}
