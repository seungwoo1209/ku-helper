resource "aws_elasticache_user" "default" {
  user_id       = "${var.project}-default-disabled"
  user_name     = "default"
  engine        = "valkey"
  access_string = "off ~keys* -@all"

  authentication_mode {
    type = "no-password-required"
  }
}

resource "aws_elasticache_user" "app" {
  user_id       = "${var.project}-app-user"
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
