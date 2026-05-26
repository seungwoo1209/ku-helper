output "tfstate_bucket" {
  description = "persistent / ephemeral 모듈의 backend.tf 에서 사용할 S3 버킷 이름."
  value       = aws_s3_bucket.tfstate.bucket
}

output "tflock_table" {
  description = "persistent / ephemeral 모듈의 backend.tf 에서 사용할 DynamoDB lock 테이블 이름."
  value       = aws_dynamodb_table.tflock.name
}

output "aws_region" {
  description = "backend 설정에 그대로 사용."
  value       = var.aws_region
}
