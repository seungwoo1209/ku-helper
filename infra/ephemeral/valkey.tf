# default 사용자는 user_group 에 반드시 포함되어야 한다. Valkey 는 no-password-required 를
# 거부하므로 password 모드로 만들되 access_string 으로 모든 동작을 차단한다. 패스워드는
# random 으로 생성하고 어디에도 노출하지 않는다(사용 의도 없음).
resource "random_password" "valkey_default" {
  length  = 32
  special = false
}

resource "aws_elasticache_user" "default" {
  user_id       = "${var.project}-default-disabled"
  user_name     = "default"
  engine        = "valkey"
  access_string = "off ~keys* -@all"

  authentication_mode {
    type      = "password"
    passwords = [random_password.valkey_default.result]
  }
}

# IAM 인증 사용자는 user_id 와 user_name 이 동일해야 한다(ElastiCache 제약).
resource "aws_elasticache_user" "app" {
  user_id       = local.persistent.redis_iam_user
  user_name     = local.persistent.redis_iam_user
  engine        = "valkey"
  access_string = "on ~* +@all"

  authentication_mode {
    type = "iam"
  }
}

resource "aws_elasticache_user_group" "app" {
  user_group_id = "${var.project}-ug"
  engine        = "valkey"
  user_ids = [
    aws_elasticache_user.default.user_id,
    aws_elasticache_user.app.user_id,
  ]
}

resource "aws_elasticache_serverless_cache" "main" {
  engine = "valkey"
  name   = local.persistent.cache_name

  cache_usage_limits {
    data_storage {
      maximum = 1
      unit    = "GB"
    }
    ecpu_per_second {
      maximum = 1000
    }
  }

  subnet_ids         = aws_subnet.private[*].id
  security_group_ids = [aws_security_group.valkey.id]
  user_group_id      = aws_elasticache_user_group.app.user_group_id

  description = "ku-helper Valkey serverless — minimal cap"
}
