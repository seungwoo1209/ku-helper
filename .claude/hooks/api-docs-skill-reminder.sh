#!/usr/bin/env bash
#
# PostToolUse hook — backend router/schemas 변경 시 api-docs-coverage 스킬 호출
# 리마인더.
#
# Edit/Write/MultiEdit 의 file_path 가
# backend/app/domains/<도메인>/router.py 또는
# backend/app/domains/<도메인>/schemas.py 패턴이면 Claude 컨텍스트에
# additionalContext 를 주입해 메모리 규칙
# `feedback_invoke_skills_explicitly.md` 를 상기시킨다.
#
# 봇 컨테이너(bot/app/**) 는 api-docs-coverage 트리거 대상이 아니므로
# 패턴에서 의도적으로 제외한다.

set -euo pipefail

file_path=$(jq -r '.tool_input.file_path // empty')

if [[ "$file_path" =~ backend/app/domains/[^/]+/(router|schemas)\.py$ ]]; then
  jq -nc --arg msg "FastAPI router/schemas 변경 감지 — 메모리 규칙 \`feedback_invoke_skills_explicitly.md\` 에 따라 Skill 도구로 \`api-docs-coverage\` 스킬을 명시 호출해야 한다. 트리거: 새 라우트 핸들러, response_model/status_code 변경, 새 BaseModel 서브클래스, Pydantic 필드 추가·이름·타입 변경, 새 도메인 신설." \
    '{hookSpecificOutput:{hookEventName:"PostToolUse",additionalContext:$msg}}'
fi
