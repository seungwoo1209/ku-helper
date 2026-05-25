#!/usr/bin/env bash
#
# bootstrap-secrets-to-parameter-store.sh
#
# backend/.env 와 bot/.env 의 시크릿 값을 읽어 AWS SSM Parameter Store 의
# /ku-helper/app/* 와 /ku-helper/ghcr/pat 에 SecureString 으로 등록한다.
# 시크릿 파라미터의 껍데기(placeholder)는 infra/persistent 가 미리 만들어 두며,
# 이 스크립트가 실제 값을 채운다.
#
# 자격 증명은 장기 access key 가 아니라 AWS IAM Identity Center(SSO) 임시 토큰을 사용한다.
# --profile 인자(또는 AWS_PROFILE 환경변수)로 프로파일을 지정하면, 세션이 없거나 만료된
# 경우 aws sso login 을 자동 실행한다.
#
# JWT_SECRET 은 예외로, .env 에서 읽지 않고 매 실행 시 128비트 랜덤 값을 새로 생성하여
# SSM 에 등록함과 동시에 backend/.env 의 JWT_SECRET 도 같은 값으로 갱신한다.
#
# 사용법:
#   ./scripts/bootstrap-secrets-to-parameter-store.sh --profile my-sso-profile
#   ./scripts/bootstrap-secrets-to-parameter-store.sh --profile my-sso-profile --dry-run
#   GHCR_PAT=ghp_xxx ./scripts/bootstrap-secrets-to-parameter-store.sh --profile my-sso-profile
#
set -euo pipefail

# ───── 설정 ─────
PROJECT="ku-helper"
REGION="ap-northeast-2"
PROFILE="${AWS_PROFILE:-}"
DRY_RUN=0

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_ENV="$ROOT_DIR/backend/.env"
BOT_ENV="$ROOT_DIR/bot/.env"

put_ok=0
put_skip=0

# ───── 로그 헬퍼 (값은 절대 출력하지 않는다) ─────
info() { printf '\033[0;36m[info]\033[0m %s\n' "$*"; }
ok() { printf '\033[0;32m[ ok ]\033[0m %s\n' "$*"; }
warn() { printf '\033[0;33m[warn]\033[0m %s\n' "$*" >&2; }
err() { printf '\033[0;31m[fail]\033[0m %s\n' "$*" >&2; }

usage() {
  cat <<'USAGE'
사용법: bootstrap-secrets-to-parameter-store.sh [옵션]

옵션:
  --profile <name>   AWS SSO 프로파일 (미지정 시 AWS_PROFILE 환경변수 사용)
  --region <region>  AWS 리전 (기본: ap-northeast-2)
  --dry-run          실제 등록 없이 매핑과 출처만 출력
  --help             이 도움말 출력

환경변수:
  GHCR_PAT           GitHub Container Registry PAT. 없으면 대화형 입력을 요청한다.
USAGE
}

# ───── 옵션 파싱 ─────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile) PROFILE="${2:-}"; shift 2 ;;
    --region) REGION="${2:-}"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --help | -h) usage; exit 0 ;;
    *) err "알 수 없는 옵션: $1"; usage; exit 1 ;;
  esac
done

# ───── 사전 점검 ─────
command -v aws >/dev/null 2>&1 || { err "aws CLI 가 필요하다."; exit 1; }
command -v openssl >/dev/null 2>&1 || { err "openssl 이 필요하다."; exit 1; }
[[ -f "$BACKEND_ENV" ]] || { err "backend/.env 가 없다: $BACKEND_ENV"; exit 1; }
[[ -f "$BOT_ENV" ]] || { err "bot/.env 가 없다: $BOT_ENV"; exit 1; }

if [[ -z "$PROFILE" ]]; then
  err "AWS SSO 프로파일이 필요하다. --profile <name> 또는 AWS_PROFILE 환경변수를 설정하라."
  exit 1
fi

# ───── AWS SSO 세션 확보 ─────
ensure_sso_session() {
  if aws sts get-caller-identity --profile "$PROFILE" --region "$REGION" >/dev/null 2>&1; then
    return 0
  fi
  warn "유효한 세션이 없다. aws sso login 을 실행한다 (프로파일: $PROFILE)."
  aws sso login --profile "$PROFILE"
  aws sts get-caller-identity --profile "$PROFILE" --region "$REGION" >/dev/null 2>&1
}

if ! ensure_sso_session; then
  err "SSO 로그인 후에도 자격 검증에 실패했다. 프로파일 설정을 확인하라."
  exit 1
fi
ACCOUNT_ID="$(aws sts get-caller-identity --profile "$PROFILE" --region "$REGION" --query Account --output text)"
ok "AWS 자격 확인 완료 (계정: $ACCOUNT_ID, 리전: $REGION)"

# ───── .env 파서 (source 하지 않고 라인 파싱만) ─────
# KEY=VALUE 라인에서 값만 추출한다. 양끝의 큰따옴표/작은따옴표를 제거한다.
read_env_value() {
  local file="$1" key="$2" line value
  line="$(grep -E "^[[:space:]]*${key}=" "$file" | head -n1 || true)"
  [[ -z "$line" ]] && { printf ''; return 0; }
  value="${line#*=}"
  # 양끝 공백 제거
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  # 양끝 따옴표 제거
  if [[ "$value" == \"*\" ]]; then value="${value%\"}"; value="${value#\"}"; fi
  if [[ "$value" == \'*\' ]]; then value="${value%\'}"; value="${value#\'}"; fi
  printf '%s' "$value"
}

# ───── SSM 등록 헬퍼 ─────
# put_secret <ssm_name> <value> <required:0|1>
put_secret() {
  local name="$1" value="$2" required="$3"
  if [[ -z "$value" ]]; then
    if [[ "$required" == "1" ]]; then
      err "필수 시크릿이 비어 있다: $name"
      exit 1
    fi
    warn "값이 없어 건너뛴다 (placeholder 유지): $name"
    put_skip=$((put_skip + 1))
    return 0
  fi
  if [[ "$DRY_RUN" == "1" ]]; then
    info "[dry-run] would put: $name (길이 ${#value})"
    put_ok=$((put_ok + 1))
    return 0
  fi
  aws ssm put-parameter \
    --profile "$PROFILE" \
    --region "$REGION" \
    --name "$name" \
    --type SecureString \
    --overwrite \
    --value "$value" >/dev/null
  ok "등록: $name"
  put_ok=$((put_ok + 1))
}

# ───── JWT_SECRET: 매 실행 128비트 신규 생성 + backend/.env write-back ─────
handle_jwt_secret() {
  if [[ "$DRY_RUN" == "1" ]]; then
    info "[dry-run] JWT_SECRET: 128비트 신규 생성 + backend/.env write-back (생략)"
    info "[dry-run] would put: /$PROJECT/app/JWT_SECRET"
    put_ok=$((put_ok + 1))
    return 0
  fi

  local jwt_new
  jwt_new="$(openssl rand -hex 16)" # 16바이트 = 128비트, 32자 16진수

  # SSM 등록
  put_secret "/$PROJECT/app/JWT_SECRET" "$jwt_new" 1

  # backend/.env write-back (임시 파일 + mv 로 원자적 교체, 권한 보존)
  local tmp
  tmp="$(mktemp)"
  chmod 0600 "$tmp"
  if grep -qE '^[[:space:]]*JWT_SECRET=' "$BACKEND_ENV"; then
    # 기존 라인 치환. 값에 sed 특수문자가 없도록 hex 만 생성하므로 안전하다.
    sed "s|^[[:space:]]*JWT_SECRET=.*|JWT_SECRET=${jwt_new}|" "$BACKEND_ENV" >"$tmp"
  else
    cat "$BACKEND_ENV" >"$tmp"
    printf '\nJWT_SECRET=%s\n' "$jwt_new" >>"$tmp"
  fi
  mv "$tmp" "$BACKEND_ENV"
  chmod 0600 "$BACKEND_ENV"
  ok "backend/.env 의 JWT_SECRET 갱신 완료"
}

# ───── 값 수집 ─────
info "backend/.env 와 bot/.env 에서 시크릿을 읽는다."

DISCORD_CLIENT_ID="$(read_env_value "$BACKEND_ENV" DISCORD_CLIENT_ID)"
DISCORD_CLIENT_SECRET="$(read_env_value "$BACKEND_ENV" DISCORD_CLIENT_SECRET)"
DISCORD_BOT_TOKEN_BE="$(read_env_value "$BACKEND_ENV" DISCORD_BOT_TOKEN)"
DISCORD_BOT_TOKEN_BOT="$(read_env_value "$BOT_ENV" DISCORD_BOT_TOKEN)"

SUBWAY_API_KEY="$(read_env_value "$BOT_ENV" SUBWAY_API_KEY)"
NAVER_SEARCH_CLIENT_ID="$(read_env_value "$BOT_ENV" NAVER_SEARCH_CLIENT_ID)"
NAVER_SEARCH_CLIENT_SECRET="$(read_env_value "$BOT_ENV" NAVER_SEARCH_CLIENT_SECRET)"
ADMIN_DISCORD_IDS="$(read_env_value "$BOT_ENV" ADMIN_DISCORD_IDS)"

# 앱은 LIBRARY_SEAT_URL 을 읽지만 bot/.env 는 LIBRARY_URL 을 쓰므로 매핑한다.
LIBRARY_SEAT_URL="$(read_env_value "$BOT_ENV" LIBRARY_URL)"
[[ -z "$LIBRARY_SEAT_URL" ]] && LIBRARY_SEAT_URL="$(read_env_value "$BOT_ENV" LIBRARY_SEAT_URL)"

# DISCORD_BOT_TOKEN 은 backend 값을 기준으로 하고, bot 값과 다르면 경고한다.
DISCORD_BOT_TOKEN="$DISCORD_BOT_TOKEN_BE"
if [[ -n "$DISCORD_BOT_TOKEN_BOT" && "$DISCORD_BOT_TOKEN_BE" != "$DISCORD_BOT_TOKEN_BOT" ]]; then
  warn "backend/.env 와 bot/.env 의 DISCORD_BOT_TOKEN 이 다르다. backend 값을 등록한다."
fi
if [[ -z "$DISCORD_BOT_TOKEN" && -n "$DISCORD_BOT_TOKEN_BOT" ]]; then
  DISCORD_BOT_TOKEN="$DISCORD_BOT_TOKEN_BOT"
fi

# ───── GHCR PAT (환경변수 또는 대화형 입력) ─────
GHCR_PAT_VALUE="${GHCR_PAT:-}"
if [[ -z "$GHCR_PAT_VALUE" && "$DRY_RUN" != "1" ]]; then
  read -rs -p "GHCR PAT 입력 (read:packages, 비우면 skip): " GHCR_PAT_VALUE
  echo
fi

# ───── 등록 ─────
info "SSM Parameter Store 에 등록을 시작한다 (dry-run=$DRY_RUN)."

handle_jwt_secret

put_secret "/$PROJECT/app/DISCORD_CLIENT_ID"          "$DISCORD_CLIENT_ID"          1
put_secret "/$PROJECT/app/DISCORD_CLIENT_SECRET"      "$DISCORD_CLIENT_SECRET"      1
put_secret "/$PROJECT/app/DISCORD_BOT_TOKEN"          "$DISCORD_BOT_TOKEN"          1
put_secret "/$PROJECT/app/SUBWAY_API_KEY"             "$SUBWAY_API_KEY"             0
put_secret "/$PROJECT/app/NAVER_SEARCH_CLIENT_ID"     "$NAVER_SEARCH_CLIENT_ID"     0
put_secret "/$PROJECT/app/NAVER_SEARCH_CLIENT_SECRET" "$NAVER_SEARCH_CLIENT_SECRET" 0
put_secret "/$PROJECT/app/LIBRARY_SEAT_URL"           "$LIBRARY_SEAT_URL"           0
put_secret "/$PROJECT/app/ADMIN_DISCORD_IDS"          "$ADMIN_DISCORD_IDS"          0
put_secret "/$PROJECT/ghcr/pat"                       "$GHCR_PAT_VALUE"             0

# ───── 요약 ─────
echo
ok "완료: 등록 ${put_ok}건, 건너뜀 ${put_skip}건"
if [[ "$DRY_RUN" == "1" ]]; then
  info "dry-run 이므로 실제 등록과 backend/.env 갱신은 수행하지 않았다."
else
  info "다음 단계: deploy-backend.yml 또는 deploy-bot.yml rollout 을 실행하면 EC2 의"
  info "refresh-env.sh 가 새 값을 내려받아 컨테이너에 반영한다."
fi
