output "alb_dns_name" {
  description = "ALB DNS — Route53 alias 가 가리킴. health check / smoke test 에 사용."
  value       = aws_lb.main.dns_name
}

output "api_url" {
  description = "최종 사용자가 접근하는 HTTPS URL."
  value       = "https://${local.persistent.domain_name}"
}

output "app_instance_id" {
  description = "deploy-* 워크플로 가 SSH 대상 IP 를 조회할 때 사용."
  value       = aws_instance.app.id
}

output "app_public_ip" {
  description = "app EC2 public IP — GitHub Actions SSH 진입점."
  value       = aws_instance.app.public_ip
}

output "bastion_public_ip" {
  description = "개발자가 SSH 터널 / IAM 인증 SQL 실행에 사용."
  value       = aws_instance.bastion.public_ip
}

output "rds_endpoint" {
  description = "PostgreSQL 엔드포인트 (private). bastion 경유 접속."
  value       = aws_db_instance.main.address
}

output "rds_port" {
  value = aws_db_instance.main.port
}

output "rds_resource_id" {
  description = "rds-db:connect IAM 정책에 사용되는 dbi-resource-id."
  value       = aws_db_instance.main.resource_id
}

output "rds_master_secret_arn" {
  description = "부트스트랩 SQL 실행 시 fetch. 일상 운영에서는 사용 금지."
  value       = aws_secretsmanager_secret.db_master.arn
}

output "valkey_endpoint" {
  description = "Valkey serverless reader/writer 엔드포인트."
  value       = aws_elasticache_serverless_cache.main.endpoint[0].address
}

output "valkey_port" {
  value = aws_elasticache_serverless_cache.main.endpoint[0].port
}

output "ec2_ssh_private_key_pem" {
  description = "tls_private_key 가 발행한 PEM. 워크플로는 GitHub Secret 사용. 로컬은 terraform output -raw 로 추출."
  value       = tls_private_key.ec2.private_key_pem
  sensitive   = true
}
