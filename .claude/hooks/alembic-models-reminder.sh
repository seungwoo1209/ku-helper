#!/usr/bin/env bash
#
# PostToolUse hook — SQLAlchemy 모델 변경 시 Alembic 마이그레이션 reminder.
#
# Edit/Write/MultiEdit 의 file_path 가 backend/app/domains/<도메인>/models.py
# 패턴이면 Claude 컨텍스트에 additionalContext 를 주입해 backend/claude.md
# Rules ("모델 변경 PR 에는 Alembic 마이그레이션을 포함한다. autogenerate
# 결과는 사람이 검토한 뒤 커밋한다") 를 상기시킨다.
#
# 봇 컨테이너(bot/app/db/models.py) 는 alembic 실행 권한이 없으므로
# 대상에서 의도적으로 제외한다 (bot/.claude/security.md 참고).

set -euo pipefail

file_path=$(jq -r '.tool_input.file_path // empty')

if [[ "$file_path" =~ backend/app/domains/[^/]+/models\.py$ ]]; then
  jq -nc --arg msg "SQLAlchemy 모델 변경 감지 — backend/claude.md Rules: (1) \`uv run alembic revision --autogenerate -m <msg>\` 로 Alembic 마이그레이션을 생성하고, (2) 생성된 alembic/versions/*.py 스크립트를 사람이 직접 검토·수정한 뒤 커밋한다. autogenerate 결과를 그대로 커밋하지 말 것." \
    '{hookSpecificOutput:{hookEventName:"PostToolUse",additionalContext:$msg}}'
fi
