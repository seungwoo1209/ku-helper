# EC2 의 refresh-env.sh 가 SSM Parameter Store 에서 fetch 하여 /etc/ku-helper/app.env 로 떨어뜨린다.
# 모든 파라미터는 /ku-helper/app/* 네임스페이스 (persistent IAM Role 의 ssm:GetParameter* 정책 범위).
#
# 시크릿 파라미터(app_secrets, ghcr_pat)는 이 모듈이 아니라 infra/persistent/ssm_secrets.tf 에 있다.
# teardown 으로 삭제되지 않아야 1회 수동 등록으로 값이 유지되기 때문이다. 여기서는 teardown 마다
# 재생성해도 무방한 비시크릿 설정만 관리한다.

locals {
  cache_endpoint = aws_elasticache_serverless_cache.main.endpoint[0].address

  # 비시크릿 동작 설정과 연결 정보. 시크릿이 아니므로 terraform 이 값까지 관리한다.
  app_config = {
    # 동작 모드
    ENVIRONMENT  = "production"
    LOG_LEVEL    = "INFO"
    USE_IAM_AUTH = "true"
    AWS_REGION   = var.aws_region

    # GitHub Container Registry 소유자 (refresh-env.sh 가 docker login 시 사용)
    GHCR_OWNER = var.github_owner

    # Discord OAuth 콜백 URL. backend config 의 discord_redirect_uri 는 기본값이 없는
    # 필수 필드라 반드시 주입해야 한다. 도메인은 persistent 의 ACM/ALB 도메인과 일치시킨다.
    DISCORD_REDIRECT_URI = "https://${local.persistent.domain_name}/api/v1/auth/discord/callback"

    # DB (IAM 인증이라 password 미저장)
    DB_HOST     = aws_db_instance.main.address
    DB_PORT     = tostring(aws_db_instance.main.port)
    DB_NAME     = var.db_name
    DB_IAM_USER = local.persistent.db_iam_user

    # Redis (IAM 인증)
    REDIS_HOST       = local.cache_endpoint
    REDIS_PORT       = tostring(aws_elasticache_serverless_cache.main.endpoint[0].port)
    REDIS_IAM_USER   = local.persistent.redis_iam_user
    REDIS_CACHE_NAME = aws_elasticache_serverless_cache.main.name
  }
}

resource "aws_ssm_parameter" "app_config" {
  for_each = local.app_config

  name  = "/${var.project}/app/${each.key}"
  type  = "String"
  value = each.value

  tags = { Name = "/${var.project}/app/${each.key}" }
}
