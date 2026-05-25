# 애플리케이션 시크릿 SSM 파라미터.
#
# 이 모듈(persistent)은 spin-up/teardown 사이클로 삭제되지 않으므로, 시크릿을 여기에 두면
# 사람이 1회만 값을 등록해도 teardown 과 spin-up 을 반복하는 동안 값이 유지된다.
#
# terraform 은 placeholder 껍데기만 만들고 lifecycle.ignore_changes 로 이후 값 변경을 무시한다.
# 실제 시크릿 값은 사람이 1회 `aws ssm put-parameter --overwrite --type SecureString` 로 등록한다.
# 따라서 시크릿 평문이 terraform state 에도, GitHub 에도 남지 않는다. 등록 절차는 infra/roadmap.md 참고.

locals {
  app_secret_keys = toset([
    "JWT_SECRET",
    "DISCORD_CLIENT_ID",
    "DISCORD_CLIENT_SECRET",
    "DISCORD_BOT_TOKEN",
    "SUBWAY_API_KEY",
    "NAVER_SEARCH_CLIENT_ID",
    "NAVER_SEARCH_CLIENT_SECRET",
    "LIBRARY_SEAT_URL",
    "ADMIN_DISCORD_IDS",
  ])

  ssm_placeholder = "PLACEHOLDER_SET_VIA_CLI"
}

resource "aws_ssm_parameter" "app_secrets" {
  for_each = local.app_secret_keys

  name  = "/${var.project}/app/${each.value}"
  type  = "SecureString"
  value = local.ssm_placeholder

  lifecycle {
    ignore_changes = [value]
  }

  tags = { Name = "/${var.project}/app/${each.value}" }
}

# GitHub Container Registry PAT — EC2 가 docker login 시 사용.
resource "aws_ssm_parameter" "ghcr_pat" {
  name  = "/${var.project}/ghcr/pat"
  type  = "SecureString"
  value = local.ssm_placeholder

  lifecycle {
    ignore_changes = [value]
  }

  tags = { Name = "/${var.project}/ghcr/pat" }
}
