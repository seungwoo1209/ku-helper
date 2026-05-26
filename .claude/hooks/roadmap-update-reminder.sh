#!/usr/bin/env bash
#
# PreToolUse(Bash) hook — git commit 직전에 ROADMAP.md 갱신 필요성 검토 요청.
#
# bot/ 또는 backend/ 코드가 스테이징되었는데 해당 컴포넌트의 ROADMAP.md 가
# 동일 커밋에 포함되지 않은 경우, Claude 컨텍스트에 검토 요청을 주입한다.
# 차단(exit 2) 이 아니라 안내(additionalContext) — 변경 영향 판단은 Claude 가 한다.
# (frontend/·infra/·docs/ 는 ROADMAP.md 가 없으므로 감지 대상에서 제외.)

set -euo pipefail

command=$(jq -r '.tool_input.command // empty')

# git commit 만 매칭. `git commit-tree`, `git commit -` 변종은 제외할 필요 없음
# (commit 뒤가 공백·줄끝이어야 매칭).
if [[ ! "$command" =~ (^|[[:space:]\;\&\|\(])git[[:space:]]+commit($|[[:space:]]) ]]; then
  exit 0
fi

staged=$(git diff --cached --name-only 2>/dev/null || true)

if [[ -z "$staged" ]]; then
  exit 0
fi

scopes=()

# bot/ 코드 변경 (bot/ROADMAP.md, bot/.claude/ 제외) + bot/ROADMAP.md 미스테이징
bot_code=$(echo "$staged" | grep -E "^bot/" | grep -vE "^bot/(ROADMAP\.md$|\.claude/)" || true)
bot_roadmap=$(echo "$staged" | grep -xE "bot/ROADMAP\.md" || true)
if [[ -n "$bot_code" && -z "$bot_roadmap" ]]; then
  scopes+=("bot/ROADMAP.md")
fi

# backend/ 동일
backend_code=$(echo "$staged" | grep -E "^backend/" | grep -vE "^backend/(ROADMAP\.md$|\.claude/)" || true)
backend_roadmap=$(echo "$staged" | grep -xE "backend/ROADMAP\.md" || true)
if [[ -n "$backend_code" && -z "$backend_roadmap" ]]; then
  scopes+=("backend/ROADMAP.md")
fi

if [[ ${#scopes[@]} -eq 0 ]]; then
  exit 0
fi

scope_list=$(IFS=", "; echo "${scopes[*]}")

msg="git commit 직전 ROADMAP 갱신 검토 — 스테이징된 변경에 ${scope_list} 갱신이 빠져 있다. 다음 기준으로 판단하라: (1) 잔여 작업 목록·완료 마일스톤·인터페이스 합의·알려진 부채에 영향이 있는가? (2) '마지막 갱신' 라인을 새로 써야 하는가? 영향이 없으면(타이포·단순 리네임·인프라 미세 조정 등) 그대로 커밋 진행, 영향이 있으면 해당 ROADMAP.md 를 먼저 수정·git add 후 동일 커밋에 포함하라."

jq -nc --arg msg "$msg" \
  '{hookSpecificOutput:{hookEventName:"PreToolUse",additionalContext:$msg}}'
