# EC2 user-data 가 SSM Parameter Store 에서 fetch 하여 /etc/ku-helper/app.env 로 떨어뜨린다.
# 모든 파라미터는 /ku-helper/app/* 네임스페이스 (persistent IAM Role 의 ssm:GetParameter* 정책 범위).

locals {
  cache_endpoint = aws_elasticache_serverless_cache.main.endpoint[0].address

  app_config = {
    # 동작 모드
    ENVIRONMENT   = "production"
    LOG_LEVEL     = "INFO"
    USE_IAM_AUTH  = "true"
    AWS_REGION    = var.aws_region

    # DB (IAM 인증이라 password 미저장)
    DB_HOST       = aws_db_instance.main.address
    DB_PORT       = tostring(aws_db_instance.main.port)
    DB_NAME       = var.db_name
    DB_IAM_USER   = local.persistent.db_iam_user

    # Redis (IAM 인증)
    REDIS_HOST       = local.cache_endpoint
    REDIS_PORT       = tostring(aws_elasticache_serverless_cache.main.endpoint[0].port)
    REDIS_IAM_USER   = local.persistent.redis_iam_user
    REDIS_CACHE_NAME = aws_elasticache_serverless_cache.main.name
  }

  app_secrets = {
    JWT_SECRET                 = var.jwt_secret
    DISCORD_CLIENT_ID          = var.discord_client_id
    DISCORD_CLIENT_SECRET      = var.discord_client_secret
    DISCORD_BOT_TOKEN          = var.discord_bot_token
    SUBWAY_API_KEY             = var.subway_api_key
    NAVER_SEARCH_CLIENT_ID     = var.naver_search_client_id
    NAVER_SEARCH_CLIENT_SECRET = var.naver_search_client_secret
    LIBRARY_SEAT_URL           = var.library_seat_url
    ADMIN_DISCORD_IDS          = var.admin_discord_ids
  }
}

resource "aws_ssm_parameter" "app_config" {
  for_each = local.app_config

  name  = "/${var.project}/app/${each.key}"
  type  = "String"
  value = each.value

  tags = { Name = "/${var.project}/app/${each.key}" }
}

resource "aws_ssm_parameter" "app_secrets" {
  for_each = local.app_secrets

  name  = "/${var.project}/app/${each.key}"
  type  = "SecureString"
  value = each.value == "" ? "__empty__" : each.value

  tags = { Name = "/${var.project}/app/${each.key}" }
}

# GHCR PAT — EC2 가 docker login 시 사용. 별도 네임스페이스.
resource "aws_ssm_parameter" "ghcr_pat" {
  name  = "/${var.project}/ghcr/pat"
  type  = "SecureString"
  value = var.ghcr_pat

  tags = { Name = "/${var.project}/ghcr/pat" }
}
