output "acm_certificate_arn" {
  description = "ALB HTTPS listener 가 사용할 인증서 ARN."
  value       = aws_acm_certificate_validation.api.certificate_arn
}

output "domain_name" {
  description = "API 도메인 — ALB DNS alias 가 가리킬 대상."
  value       = var.domain_name
}

output "route53_zone_id" {
  description = "ALB alias 레코드를 생성할 호스팅 존 ID. ephemeral 모듈의 route53 alias provider 가 사용."
  value       = data.aws_route53_zone.parent.zone_id
}

output "route53_account_id" {
  description = "cross-account assume 에 다시 사용."
  value       = var.route53_account_id
}

output "ec2_iam_role_arn" {
  description = "ephemeral EC2 에 attach 할 IAM Role ARN."
  value       = aws_iam_role.ec2.arn
}

output "ec2_instance_profile_name" {
  description = "ephemeral aws_instance.iam_instance_profile 에 그대로 사용."
  value       = aws_iam_instance_profile.ec2.name
}

output "app_ami_id" {
  description = "Packer 산출 AMI 의 최신 ID."
  value       = data.aws_ami.app.id
}

output "db_iam_user" {
  description = "ephemeral RDS aws_db_instance 생성 후 동일 user 를 IAM 매핑."
  value       = var.db_iam_user
}

output "redis_iam_user" {
  description = "ephemeral Valkey aws_elasticache_user 의 user_name."
  value       = var.redis_iam_user
}

output "cache_name" {
  description = "ephemeral Valkey serverless cache 이름."
  value       = var.cache_name
}
