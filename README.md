# KU Helper — 건국대 캠퍼스 알리미

디스코드 OAuth 로그인 한 번으로 학식 메뉴, 지하철 도착 시간, 도서관 좌석 현황을 Discord DM으로 자동 수신하는 캠퍼스 알림 시스템입니다.

> 전공심화프로젝트(3242) · 문승우(202111283) · 김진하(202214311)

---

## 주요 기능

| 분류 | 기능 |
|---|---|
| **인증** | Discord OAuth2 소셜 로그인 / 로그아웃 / 자동 토큰 갱신 |
| **교통** | 역·노선 지정 후 도착 N분 전 DM 알림, 정기 간격 반복 알림, 혼잡도 표시 |
| **점심** | 설정 시각에 학식 메뉴 + 주변 음식점 추천 DM 발송, 예산 필터, 오늘의 추천 하이라이트 |
| **도서관** | 열람실 잔여 좌석 임계값 도달 시 30초 이내 DM, 긴급 표시, 중복 방지 |
| **대시보드** | React 웹에서 알림 조건 추가·수정·삭제·ON/OFF 토글 |
| **이력** | 최근 30일 발송 이력 조회 |
| **신뢰성** | 크롤러 실패 시 관리자 DM 알림, DM 발송 실패 지수 백오프 재시도 |

---

## 아키텍처

```
브라우저 (React SPA)
    │  Discord OAuth2 로그인
    ▼
Nginx (HTTPS / 리버스 프록시 / 정적 파일)
    │
    ├──▶ FastAPI (API Server)
    │       - Discord OAuth 콜백, JWT 발급
    │       - 알림 설정 CRUD
    │       - 즉시 발송 요청 큐 INSERT
    │              │
    │           PostgreSQL ◀─────────────┐
    │              │                     │
    └──▶ Bot Container                   │
            APScheduler                 │
              └─ 주기 폴링 ──────────────┘
            asyncio.Queue
              └─ 발송 워커 ──▶ Discord API (DM)
            Crawlers
              ├─ 학식 (Playwright)
              └─ 음식점 (Naver Local Search API)
            Redis (크롤링 캐시 / 중복 방지 쿨다운)
```

두 컨테이너는 직접 통신하지 않으며 PostgreSQL을 매개로 연결됩니다.

---

## 기술 스택

| 영역 | 스택 |
|---|---|
| **Frontend** | React 18, Vite |
| **Backend** | Python 3.12, FastAPI 0.115+, SQLAlchemy 2.0 (async), Alembic, asyncpg |
| **Bot** | discord.py, APScheduler, Playwright, httpx |
| **DB / Cache** | PostgreSQL 16, Redis 7 |
| **인증** | Discord OAuth2 (`integration_type=1`), PyJWT (HS256) |
| **Infra** | Docker Compose, AWS EC2 + RDS + ElastiCache, Nginx, Terraform |
| **패키지 관리** | uv (backend/bot), npm (frontend) |

---

## 컴포넌트 구조

```
ku-helper/
├── backend/      # FastAPI API 서버
├── bot/          # Discord 봇 + 스케줄러 + 크롤러
├── frontend/     # React 18 웹 대시보드
├── infra/        # Terraform + Docker Compose 배포 구성
└── docs/         # 기능 명세, 아키텍처, ADR
```

각 컴포넌트의 상세 규칙은 해당 디렉터리의 `CLAUDE.md`를 참고하세요.

---

## 로컬 개발 시작하기

### 사전 요구사항

- Docker & Docker Compose
- Python 3.12+, `uv`
- Node.js 20+

### 백엔드

```bash
cd backend
cp .env.example .env          # 환경변수 설정
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

### 봇

```bash
cd bot
cp .env.example .env
uv sync
uv run python -m app.main
```

### 프론트엔드

```bash
cd frontend
npm install
npm run dev
```

### 전체 (Docker Compose)

```bash
docker compose up --build
```

---

## 환경변수

| 변수 | 설명 |
|---|---|
| `DATABASE_URL` | PostgreSQL 연결 문자열 |
| `REDIS_URL` | Redis 연결 문자열 |
| `JWT_SECRET` | JWT 서명 키 (32바이트 이상) |
| `DISCORD_CLIENT_ID` | Discord 애플리케이션 클라이언트 ID |
| `DISCORD_CLIENT_SECRET` | Discord 애플리케이션 클라이언트 시크릿 |
| `DISCORD_BOT_TOKEN` | Discord 봇 토큰 |
| `DISCORD_REDIRECT_URI` | OAuth 콜백 URL |
| `NAVER_CLIENT_ID` | 네이버 Local Search API 클라이언트 ID |
| `NAVER_CLIENT_SECRET` | 네이버 Local Search API 시크릿 |

---

## 테스트

```bash
# 백엔드
cd backend
uv run pytest

# 봇
cd bot
uv run pytest
```

---

## 문서

- [세부 기능 목록 (F-01~F-23)](docs/requirements/features.md)
- [내부 데이터 흐름](docs/architecture/data-flow.md)
- [기술 스택 선정 및 설계 결정 근거 (ADR)](docs/decisions/adr.md)
