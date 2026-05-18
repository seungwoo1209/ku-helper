# CLAUDE.md

ku-helper는 디스코드 OAuth 로그인을 기반으로 학식·교통·도서관 알림을 Discord DM으로 전달하는 캠퍼스 알리미 시스템이다. 본 레포는 다음 컴포넌트로 구성된다.

- `backend/` — FastAPI API 서버 (자체 가이드: `backend/CLAUDE.md`)
- `bot/` — Discord Bot + 스케줄러 + 크롤러 (자체 가이드: `bot/CLAUDE.md`)
- `frontend/` — React 18 웹 대시보드
- `infra/` — Docker Compose / 배포 구성

## AI Agent Routing Triggers

- 시스템 전반 개요·아키텍처가 필요하면 `docs/README.md`
- 기능 명세(F-01~F-23)가 필요하면 `docs/requirements/features.md`
- 백엔드 비동기 처리·큐·데이터 파이프라인 흐름이 필요하면 `docs/architecture/data-flow.md`
- 기술 스택(FastAPI, React 등) 선정·설계 결정 근거가 필요하면 `docs/decisions/adr.md`
- 백엔드 도메인 규칙·코드 스타일·보안·테스팅은 `backend/CLAUDE.md` 및 `backend/.claude/*.md`
- 봇 도메인 규칙·아키텍처는 `bot/CLAUDE.md` 및 `bot/.claude/*.md`

## 시스템 문서 진입점

@docs/README.md
