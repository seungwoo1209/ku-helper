REPORT

# **진행 상황 정리**

## **애플리케이션 아키텍처 확정**

![][image2]

* **FastAPI**: 사용자 설정 CRUD, 인증, 알림 이력 조회 REST API 제공  
* **APScheduler**: FastAPI 프로세스와 분리된 별도 컨테이너로 실행 (스케일링 시 중복 실행 방지를 위해 단일 인스턴스 유지, Redis 락 활용)  
* **Celery Worker**: 크롤링 작업 및 Discord DM 발송 작업 실제 처리  
* **discord.py 봇**: Celery Worker가 호출하는 별도 프로세스로 상주, DM 전송 담당

## **기술 스택 확정**

프로젝트 전반에 사용할 기술 스택을 아래와 같이 확정하였다.

| 계층 | 기술 스택 | 버전/설명 |
| ----- | ----- | ----- |
| **프론트엔드** | React | React 18+. 반응형 웹 대시보드 구현. |
| **백엔드 API** | FastAPI | Python 3.11+ (FastAPI).RESTful API 서버. |
| **디스코드 봇** | [discord.py](http://discord.py) | [discord.py](http://discord.py) 2.0+. DM 임베드 메시지 발송, OAuth2 연동. |
| **데이터베이스** | PostgreSQL | PostgreSQL 15+.  JSONB 타입을 활용한 유연한 알림 설정 저장. |
| **인증** | Discord OAuth2 \+ JWT | OAuth2 Authorization Code Grant로 인증 후 JWT 토큰 발급. |
| **스케줄러** | APScheduler | 크롤링 주기 실행 및 정기 알림 스케줄링. |
| **메시지 큐** | Celery (Redis 기반) | 알림 발송 비동기 처리 및 Rate Limit 제어. |
| **캐시** | Redis | 공공 API 응답 캐싱, 세션 관리, 발송 큐 백엔드. |
| **CI/CD** | GitHub Actions | 코드 린트, 테스트, 빌드, 배포 자동화 파이프라인. |
| **컨테이너** | Docker / Docker Compose | 개발 환경 일관성 확보 및 배포 단위 컨테이너화. |
| **웹 서버/리버스 프록시** | Nginx | HTTPS 종단, 정적 파일 서빙, 리버스 프록시. |

## **역할 분담 확정**

변경된 인원 구성에 맞춰 2인 역할 분담 확정 및 구성원별 세부 역할 내용 논의 완료

| 역할 | 담당자 | 주요 책임 |
| ----- | ----- | ----- |
| **백엔드·인프라·봇** | 문승우 | FastAPI, PostgreSQL, Redis, Celery, APScheduler, discord.py 봇, Docker, Nginx, CI/CD, 공공 API/크롤러 연동 |
| **프론트엔드·데이터·통합 테스트** | 김진하 | React 대시보드, OAuth2 프론트 흐름, DB 스키마 설계 및 ERD 관리, 알림 이력 UI, 부하 테스트, 문서화 |

**공동 작업**: 주차별 DoD 리뷰, 통합 테스트, Discord Developer Portal 설정, 위험 대응

## **계획 확정**

주차별 세부 계획(1주차는 작업이 수가 많은 관계로 작업 목록 형태로 서술)  및 DoD 확정

### **1주차 — 기반 환경 구축 및 인증 파이프라인**

| \# | 작업 | 산출물 |
| ----- | ----- | ----- |
| 1-1 | 모노레포 구조 설정 (`/frontend`, `/backend`, `/bot`, `/infra`) | Git repo \+ README |
| 1-2 | Docker Compose 로컬 개발 환경 구성 (postgres, redis, api, frontend 최소) | `docker-compose.dev.yml` |
| 1-3 | FastAPI 프로젝트 스캐폴딩 \+ `/health` 엔드포인트 | `GET /api/health` 동작 |
| 1-4 | React 18 (Vite 권장) 프로젝트 생성, `/health` 호출 테스트 페이지 | 브라우저에서 백엔드 응답 확인 |
| 1-5 | Discord Developer Portal 애플리케이션 등록 (Bot \+ OAuth2 Client) | Client ID/Secret, Bot Token |
| 1-6 | **Discord OAuth2 Authorization Code Grant 구현** (FastAPI) | `/api/auth/discord/callback` |
| 1-7 | JWT 발급/검증 미들웨어 (PyJWT) | 보호된 라우트 테스트 |
| 1-8 | discord.py 봇 프로세스 기동, 특정 사용자에게 DM 발송 스모크 테스트 | "Hello World" DM 수신 확인 |
| 1-9 | **GitHub Actions CI/CD 파이프라인** | 아래 참고 |

**목표**: "로그인해서 내 디스코드 DM으로 Hello World가 오는 것"까지 완성**CI/CD 파이프라인 구성** (GitHub Actions):

* **CI (PR 시)**: `ruff` \+ `black` (Python 린트), `eslint` (Frontend), `pytest` (단위 테스트), Docker 이미지 빌드 검증  
* **CD (main 머지 시)**: Docker 이미지를 GHCR에 푸시 → 배포 서버에 SSH로 접속하여 `docker compose pull && up -d` 실행  
* 시크릿은 GitHub Secrets로 관리 (`DISCORD_CLIENT_SECRET`, `BOT_TOKEN`, `JWT_SECRET` 등)

##### **1주차 완료 기준(DoD):**

\[ \] 사용자가 웹 대시보드에서 "Discord 로그인" 버튼 클릭 → OAuth2 완료 → JWT 수신  
\[ \] 봇이 해당 사용자에게 테스트 DM 발송 성공  
\[ \] main 브랜치 머지 시 자동 배포 동작

### **2\~3주차 — 3개 서비스 수직 개발 (Vertical Slice)**

**전략**: 각 서비스를 "데이터 수집 → DB 저장 → 스케줄 트리거 → DM 발송 → 이력 기록 → 웹 UI 설정"까지 **End-to-End로 하나씩 완성**. 공통 모듈(스케줄러 인터페이스, 발송 큐, 임베드 템플릿)은 첫 번째 서비스에서 추출해 나머지에 재사용.

#### **2주차**

**\[Day 1-2\] 공통 알림 엔진 뼈대**

* `BaseNotifier` 추상 클래스 설계 (`fetch()`, `should_notify()`, `build_embed()`, `send()`)  
* Celery 태스크 `send_discord_dm(user_id, embed_dict)` 정의  
* APScheduler ↔ Celery 연결 (스케줄러는 큐에 작업만 적재)  
* Discord Rate Limit 대응: Celery 워커 동시성 제한 \+ 지수 백오프 재시도 (max\_retries=3)

**\[Day 3-4\] 서비스 ①: 점심 추천 알림** (가장 단순 → 파이프라인 검증용)

* 학식 크롤러 모듈 (`BeautifulSoup` \+ `httpx`), 학교 생협 페이지 파싱  
* Naver Local Search API 연동 (검색 쿼리: "건대입구 맛집")  
* Redis 캐시: 동일 일자 학식 데이터 TTL 12시간  
* 임베드 템플릿: 오늘의 학식 \+ 랜덤 추천 맛집 3곳  
* 웹 UI: 점심 알림 ON/OFF \+ 알림 시각 설정

**\[Day 5-7\] 서비스 ②: 교통 알림 (지하철)**

* 서울 열린데이터광장 `realtimeStationArrival` API 연동 (httpx 비동기 호출)  
* Redis 캐시: API 응답 TTL 20초 (Rate Limit 방어 \+ R-04 완화)  
* 두 가지 모드 구현:  
  * **정기 간격**: 매일 지정 시각 (예: 08:30)에 도착 정보 DM  
  * **도착 예상 기반**: 지정 역 지정 방향 N분 이내 열차 있을 때만 발송  
* 웹 UI: 호선/역/방향/알림 모드 선택 폼

#### **3주차**

**\[Day 1-4\] 서비스 ③: 도서관 좌석 임계값 알림**

* 학교 좌석 시스템 크롤러 (DOM 파싱 또는 내부 API 리버스 엔지니어링)  
* 크롤링 주기: APScheduler 30초 간격 (R-01 완화: 요청 간 1초 sleep, User-Agent 지정)  
* **중복 알림 방지 로직**:  
  * 동일 `config_id`에 대해 `cooldown_min`(기본 30분) 내 재발송 금지  
  * Redis Set 활용 (`notified:{config_id}` key with TTL)  
* 임계값 로직: `잔여석 ≤ threshold` 조건 최초 감지 시점에만 발송  
* 웹 UI: 열람실 선택 \+ 임계값 슬라이더 \+ 쿨다운 설정

**\[Day 5-6\] 웹 대시보드 통합**

* 3개 알림 유형을 한 화면에서 관리하는 대시보드 완성  
* 알림 이력 조회 페이지 (`notification_logs` 기반, 페이지네이션)  
* React Query로 서버 상태 관리, Tailwind CSS로 반응형 적용

**\[Day 7\] 통합 테스트**

* 3개 서비스 동시 활성화 상태에서 24시간 모니터링  
* 버그 수정 및 사용자 시나리오 테스트

##### **2\~3주차 완료 기준(DoD):**

\[ \] 3개 알림 유형 모두 웹에서 설정 → 실제 DM 수신까지 동작  
\[ \] 알림 이력이 DB에 기록되고 UI에서 조회 가능  
\[ \] 중복 발송이 발생하지 않음

### **4주차 — 신뢰성·성능 강화 및 론칭 준비**

#### **\[Day 1-2\] DM 발송 실패 재시도 및 장애 대응**

* Celery 지수 백오프 재시도 (1s → 2s → 4s, max 3회) 검증  
* 실패 시 `notification_logs.status = 'failed'` 기록 \+ 관리자 Discord 채널에 에러 알림  
* **크롤러 실패 감지**: 연속 3회 실패 시 관리자 DM 발송 (R-03 완화)  
* 공공 API 장애 시 30분 캐시 폴백 로직 구현 (R-04 완화)

#### **\[Day 3-4\] 서비스 신뢰성 체계**

* **Health Check 엔드포인트 확장**: `/health/db`, `/health/redis`, `/health/bot`  
* **구조화 로깅**: `structlog` 도입, JSON 로그 포맷  
* **모니터링**:  
  * 최소안: FastAPI 로그 \+ Celery Flower 대시보드  
  * 여유 있으면: Prometheus \+ Grafana (선택)  
* Sentry 연동 (무료 티어)로 예외 자동 수집

#### **\[Day 5-6\] 성능 최적화 및 부하 테스트**

* PostgreSQL 인덱스 점검 (`notification_logs.config_id`, `sent_at`)  
* **Locust**로 부하 테스트: 가상 사용자 100명 동시 접속 시 응답시간 측정  
* 병목 확인 후 캐시 전략 조정  
* Celery 워커 수 튜닝

#### **\[Day 7\] 문서화 및 론칭**

* API 문서 (FastAPI 자동 생성 OpenAPI)  
* README: 설치/배포/환경변수 가이드  
* 사용자 가이드 (스크린샷 포함)  
* **정식 배포** 및 초기 사용자 온보딩

##### **4주차 완료 기준(DoD)**:

\[ \] 임의로 Discord 봇을 내려도 재시도 후 복구 시 정상 발송  
\[ \] Locust 부하 테스트 결과 리포트 작성  
\[ \] README로 문서화, 다른 사람이 README만 통해 로컬 환경 구동 가능
